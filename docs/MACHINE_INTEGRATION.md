# Live Machine Integration — Architecture & Plan

**Project:** Fibre Mold Plant Dashboard · Golden Manufacturers
**Status:** Design for review (no code yet)
**Audience:** Plant management + automation integrator / electrician
**Last updated:** 2026-06-17

---

## 1. Goal & scope

Bring **live machine data** into the existing dashboard so it updates itself instead
of relying only on end-of-shift manual entry.

Based on the current site assessment:

| Data | Source today | Plan |
|---|---|---|
| **Machine run / stop** | HMI/SCADA (digital) | **Automate (Phase 1)** — drives automatic uptime % and downtime |
| Production / press counts | Counted by hand | Stay manual *(automate later if a digital counter exists)* |
| Fuel tank level | Manual dip | Stay manual *(automate later if a level transmitter is added)* |
| Water meter | Read by hand | Stay manual *(automate later if pulse/flow output exists)* |
| Downtime **reason** | Operator note | Stay manual — operator labels an auto-detected stop |
| Deliveries, bale receipts, month-end stock | Manual forms | Stay manual (human/paperwork data) |

> **Key principle:** automate what the machine already exposes; keep everything else on
> the entry forms already built. "All data live" realistically means *run/stop now,
> more signals later as they become digital.*

The first deliverable — **automatic uptime/downtime from the run/stop signal** — removes
the most error-prone manual task (logging downtime minutes) while operators still add the
short *reason* for each stop.

---

## 2. Current system (recap)

```
Browser (React dashboard)  ──/api──>  FastAPI backend  ──SQL──>  Postgres / SQLite
                                       (analytics, auth, CRUD)
```

All data is entered through forms or imported from Excel. We will **add a third input
path** (the machine) that writes into the *same* backend and database, so the dashboards,
reports, and analytics keep working unchanged.

---

## 3. Target architecture

```
  ┌─────────────────────── PLANT FLOOR ───────────────────────┐
  │                                                            │
  │   PLC  ──►  HMI / SCADA            (existing, untouched)   │
  │    │            │                                          │
  │    │ read-only  │ read-only                                │
  │    ▼            ▼                                          │
  │   ┌──────────────────────────┐                            │
  │   │   COLLECTOR SERVICE        │  (new, runs on plant PC)  │
  │   │   • polls run/stop tag     │                            │
  │   │   • debounces transitions  │                            │
  │   │   • store-and-forward buffer│                           │
  │   └──────────────┬─────────────┘                           │
  └──────────────────┼─────────────────────────────────────────┘
                     │  HTTPS POST (outbound only, API key)
                     ▼
            ┌────────────────────┐        ┌──────────────────┐
            │  FastAPI backend   │ ─SQL─► │  Database         │
            │  /api/ingest/...   │        │  machine_events   │
            │  (existing app)    │        │  machine_status   │
            └─────────┬──────────┘        └──────────────────┘
                      │ /api
                      ▼
            React dashboard  → Live status, uptime %, auto downtime + reason
```

**Why a separate collector service (not the backend polling directly):**
- Keeps industrial-protocol drivers off the web server.
- Survives network/backend outages via a local **store-and-forward** buffer.
- Can sit on the same isolated machine network and talk *outbound only* to the backend —
  no inbound holes in the plant network.
- Swappable: change the protocol driver without touching the dashboard.

---

## 4. How we tap the machine — options (ranked)

We won't know the exact route until the discovery checklist comes back. These are the
candidates, best-fit first. **The integrator picks based on what the HMI/PLC supports.**

### Option A — Read the SCADA historian / log (often easiest)
Many HMI/SCADA packages already log to a database or CSV (SQL Server, MySQL, SQLite, or
files). If yours does, the collector just **reads that store read-only** — no PLC access
needed, no protocol risk.
- *Best when:* the SCADA already records run/stop or alarms.
- *Need:* DB type, connection string / file path, table & column for run state, a
  read-only DB user.

### Option B — OPC UA from the PLC/SCADA (best for tags)
Modern PLCs and SCADA expose an **OPC UA server**. The collector subscribes to the
run/stop tag and gets change events in real time. Clean, secure, standard.
- *Best when:* Siemens S7-1500/1200, modern AVEVA/Ignition, or any OPC-UA-capable gear.
- *Need:* OPC UA endpoint URL, security/certificate, the run/stop **NodeId**.

### Option C — Modbus TCP (simple, very common)
If the PLC exposes Modbus TCP, the collector polls a coil/register for the run bit.
- *Best when:* Delta, Omron, many drives/controllers; lightweight setups.
- *Need:* IP + port (usually 502), unit ID, the coil/register address for run state.

### Option D — Vendor-native driver
Direct protocol if A–C aren't available:
- Siemens S7 (`python-snap7`), Allen-Bradley (`pylogix`/EtherNet-IP), Mitsubishi (MC
  protocol), Omron (FINS).
- *Need:* PLC IP, rack/slot or path, the tag/address for run state.

### Option E — Edge gateway → MQTT (future-proof)
If they later add an IoT/edge gateway, it can publish tags over MQTT and the collector
subscribes. Good when expanding to many signals.

> **Likely path for you:** with an HMI/SCADA present, **Option A (its log DB)** or
> **Option B (OPC UA)** are the front-runners. The discovery checklist resolves which.

---

## 5. The collector service (spec)

- **Language/runtime:** Python (matches the backend; rich industrial libraries).
- **Form:** a small long-running process, installed as a **Windows Service** on the plant
  PC (auto-start, auto-restart). Single config file.
- **Config (`collector.toml`):** backend URL, device API key, protocol + connection
  details, **tag map** (which address = run state), poll interval, debounce settings.
- **Loop:**
  1. Poll/subscribe the run/stop source.
  2. **Debounce** — only emit a transition after the state is stable for *N* seconds
     (ignores flicker).
  3. On a confirmed RUN→STOP or STOP→RUN, create an **event** with a timestamp.
  4. POST the event to the backend ingest endpoint.
  5. Heartbeat every ~30 s with current state (so the dashboard can show "live" + detect
     a dead link).
- **Resilience — store-and-forward:** if the backend/network is down, events queue in a
  local file/SQLite and flush when the link returns. **No data loss** on outages.
- **Read-only & safe:** the collector **never writes to the PLC**. Connections are
  read/subscribe only. Outbound HTTPS only.
- **Time:** events stamped from a single trusted clock; plant PC kept time-synced (NTP)
  so machine time and dashboard time agree.

---

## 6. Data model additions (backend)

Two new tables, alongside the existing ones (manual data is untouched):

**`machine_status`** — current snapshot (one row, upserted by the heartbeat)
- `state` (running / stopped / unknown), `since` (when it entered this state),
  `last_seen` (last heartbeat → drives a "link healthy / stale" badge), `source`.

**`machine_events`** — append-only log of confirmed transitions
- `ts`, `event` (run_start / run_stop), `duration_s` (filled on the closing event),
  `shift` (derived from time-of-day), `reason` (nullable — operator fills in later),
  `reason_category` (Cleaning / Mold change / Maintenance / Other), `source`.

From these we derive, per day/shift/period: **running time, stopped time, uptime %, number
of stops, mean time between stops, mean stop length** — all server-side in the analytics
endpoint, exactly like the existing KPIs.

> These **complement** the manual downtime: the machine tells us *when* and *how long*;
> the operator tells us *why*. The current manual downtime fields remain as a fallback and
> for the reason text.

---

## 7. Backend ingest API (new, secured)

- `POST /api/ingest/machine/event` — collector posts a confirmed transition.
- `POST /api/ingest/machine/heartbeat` — collector posts current state + timestamp.
- `GET  /api/machine/status` — dashboard reads current state + uptime today.
- `PATCH /api/machine/events/{id}` — operator/supervisor adds the reason to a stop.

**Auth:** a dedicated **device API key** (separate from user logins, revocable), sent as a
header. Scope limited to the ingest endpoints only. **Idempotency:** each event carries a
collector-generated ID so retries after a network blip don't double-count.

---

## 8. Automatic downtime logic (how it stays trustworthy)

- **Debounce / micro-stops:** very short stops (< a configurable threshold, e.g. 60 s) can
  be ignored or flagged separately so jogging the line doesn't spam "downtime."
- **Shift attribution:** each stop is assigned to the Day/Afternoon/Night shift by its
  timestamp; stops spanning a shift boundary are split.
- **Reason workflow:** an auto-detected stop appears on the dashboard as **"stop — reason
  needed."** The operator/supervisor clicks it and picks a reason (reusing the existing
  cause categories). This is the only manual step left for downtime.
- **Reconciliation:** if both an auto stop and a manual downtime entry exist for the same
  window, the dashboard prefers the machine figure and flags the discrepancy for review.

---

## 9. Dashboard changes (frontend)

- **Live status pill** in the header/topbar: green "Running · 02:14" / red "Stopped ·
  18 min" / grey "Link stale" (from `last_seen`).
- **New KPI:** **Uptime %** (machine-measured) next to the existing Downtime KPI.
- **Downtime page:** a **"Stops needing a reason"** list + auto vs manual comparison.
- Everything else (production, fuel, deliveries, stock) keeps using the manual forms.

---

## 10. Security & safety requirements

- **Read-only to the machine** — no writes to the PLC, ever. This is a monitoring link.
- **Network isolation** — collector on the plant/OT network; **outbound HTTPS only** to
  the backend; no inbound ports opened toward the PLC. Ideally a separate VLAN with a
  one-way firewall rule.
- **Least privilege** — read-only DB user (Option A) or a read-only OPC UA/Modbus account.
- **Credentials** — device API key and any DB/OPC credentials stored in the collector
  config with file permissions locked down; rotatable.
- **Fail-safe** — if the collector or link dies, the dashboard shows "stale," and manual
  entry still works. The machine is never affected by the dashboard being down.
- **Change control** — all wiring/network changes done by the plant electrician/integrator.

---

## 11. What we need from the integrator (blocking items)

1. **Protocol route:** does the SCADA log to a DB/CSV (Option A), or should we use OPC UA
   (B) / Modbus (C) / a native driver (D)?
2. **Connection details:** IP + port (and DB connection string, or OPC UA endpoint, or
   Modbus unit ID) — plus a **read-only** account.
3. **The run/stop tag:** exact tag name / NodeId / register address that means "line
   running," and its data type.
4. **Network:** confirm the plant PC can reach the machine network, or what firewall/VLAN
   rule is required (outbound from collector to backend).
5. **Time sync:** confirm PLC/HMI and plant PC clocks are NTP-synced.

---

## 12. Phased rollout

| Phase | What | Needs |
|---|---|---|
| **0 · Discovery** | Fill the checklist (§11); pick the protocol route | Integrator/electrician |
| **1 · Pipeline + simulator** | Build collector skeleton, ingest API, `machine_*` tables, live status UI; test end-to-end against a **machine simulator** | Nothing from the plant — fully testable in-office |
| **2 · Connect run/stop** | Point the collector at the real tag (chosen protocol); validate uptime/downtime vs reality for a week | Connection details from §11 |
| **3 · Reason workflow** | Operators label auto-detected stops; reconcile with manual logs | Operator buy-in |
| **4 · Expand (optional)** | Add production counts / fuel level / water meter **if/when** they become digital | New sensors/transmitters |

**Recommended:** start Phase 1 now (it needs nothing from the floor and de-risks
everything), so the day connection details arrive we only swap in the real driver.

---

## 13. Future expansion

If a digital production counter, fuel-level transmitter, or pulse water meter is added
later, each becomes another tag in the same collector config and another reading type in
the same ingest pipeline — **no re-architecture**. The manual forms for those simply become
the fallback/override.

---

## Appendix — glossary
- **PLC** — the controller running the machine logic.
- **HMI/SCADA** — the operator screen/software showing and logging machine state.
- **OPC UA** — a standard, secure industrial protocol for reading tags.
- **Modbus TCP** — a simple, widespread industrial protocol over Ethernet.
- **Tag** — a named value in the PLC/SCADA (e.g. `Line.Running`).
- **Historian** — a database the SCADA uses to log values over time.
- **Store-and-forward** — buffering data locally during an outage, sending it later.
