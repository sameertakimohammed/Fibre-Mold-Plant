const fs = require('fs')
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, TableOfContents, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageNumber, PageBreak, VerticalAlign,
} = require('docx')

const AMBER = 'C47F12'
const INK = '1A1A1A'
const MUT = '5D6875'
const HEADFILL = '222A33'
const ZEBRA = 'F4F6F8'
const CW = 9360 // content width US Letter, 1in margins

// ---------- helpers ----------
const T = (text, opts = {}) => new TextRun({ text, ...opts })
const P = (children, opts = {}) =>
  new Paragraph({ children: Array.isArray(children) ? children : [T(children)], spacing: { after: 120, line: 276 }, ...opts })
const H1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [T(text)] })
const H2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [T(text)] })
const H3 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [T(text)] })
const bullet = (children, level = 0) =>
  new Paragraph({ numbering: { reference: 'b', level }, spacing: { after: 60, line: 270 },
    children: Array.isArray(children) ? children : [T(children)] })
const num = (children) =>
  new Paragraph({ numbering: { reference: 'n', level: 0 }, spacing: { after: 80, line: 270 },
    children: Array.isArray(children) ? children : [T(children)] })

function table(headers, rows, widths) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' }
  const borders = { top: border, bottom: border, left: border, right: border,
    insideHorizontal: border, insideVertical: border }
  const headRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => new TableCell({
      borders, width: { size: widths[i], type: WidthType.DXA },
      shading: { fill: HEADFILL, type: ShadingType.CLEAR },
      margins: { top: 70, bottom: 70, left: 110, right: 110 },
      verticalAlign: VerticalAlign.CENTER,
      children: [new Paragraph({ children: [T(h, { bold: true, color: 'FFFFFF', size: 19 })] })],
    })),
  })
  const bodyRows = rows.map((r, ri) => new TableRow({
    children: r.map((c, i) => new TableCell({
      borders, width: { size: widths[i], type: WidthType.DXA },
      shading: { fill: ri % 2 ? ZEBRA : 'FFFFFF', type: ShadingType.CLEAR },
      margins: { top: 60, bottom: 60, left: 110, right: 110 },
      verticalAlign: VerticalAlign.CENTER,
      children: [new Paragraph({ children: typeof c === 'string'
        ? [T(c, { size: 19 })]
        : c.map(part => typeof part === 'string' ? T(part, { size: 19 }) : part) })],
    })),
  }))
  return new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: widths, rows: [headRow, ...bodyRows] })
}

const spacer = () => new Paragraph({ children: [T('')], spacing: { after: 60 } })

// ---------- content ----------
const children = []

// Title page
children.push(
  new Paragraph({ spacing: { before: 2600, after: 0 }, children: [T('FIBRE MOLD PLANT', { bold: true, size: 30, color: AMBER })] }),
  new Paragraph({ spacing: { after: 360 }, children: [T('GOLDEN MANUFACTURERS · RECYCLING DEPARTMENT', { size: 18, color: MUT })] }),
  new Paragraph({ spacing: { after: 120 }, children: [T('Production Dashboard', { bold: true, size: 52, color: INK })] }),
  new Paragraph({ spacing: { after: 480 }, children: [T('System Knowledge Base & Live Machine Integration Guide', { size: 28, color: INK })] }),
  new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: AMBER, space: 6 } }, children: [T('')] }),
  new Paragraph({ spacing: { before: 240 }, children: [T('Version 1.0', { size: 20, color: MUT })] }),
  new Paragraph({ children: [T('Issued: 17 June 2026', { size: 20, color: MUT })] }),
  new Paragraph({ children: [T('Audience: Plant management, dashboard administrators, automation integrator', { size: 20, color: MUT })] }),
  new Paragraph({ children: [new PageBreak()] }),
)

// TOC
children.push(
  new Paragraph({ children: [T('Contents', { bold: true, size: 30, color: INK })], spacing: { after: 160 } }),
  new TableOfContents('Contents', { hyperlink: true, headingStyleRange: '1-2' }),
  new Paragraph({ children: [new PageBreak()] }),
)

// ===== PART A =====
children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [T('Part A — System Knowledge Base')] }))
children.push(P([T('This part documents the dashboard application as it exists today: what it does, how it is built, how data flows through it, and how to run and maintain it. Part B covers the planned live-machine integration.')]))

children.push(H2('1. Overview'))
children.push(P('The Fibre Mold Plant Dashboard is a web application that turns the plant’s daily operating records into live dashboards, so management can see production, fuel, downtime, deliveries and stock at a glance instead of reading through spreadsheets.'))
children.push(P([T('It replaces the previous workflow of monthly Excel files ', {}), T('(Fiber Mold Tracker, Bale Daily, Deliveries Record, Fuel Dip Record, Month-End Stock)', { italics: true }), T(' with a shared database that the whole team enters into and views from any PC or tablet on the plant network.')]))
children.push(P('Key points:', { spacing: { after: 60 } }))
children.push(bullet('One shared database — everyone sees the same up-to-date numbers.'))
children.push(bullet('Role-based access — operators log data; managers and admins get full control.'))
children.push(bullet('All analytics are computed on the server, so every page and the exported report agree.'))
children.push(bullet('Runs on the plant’s own PC (offline-capable on the local network); no cloud dependency required.'))

children.push(H2('2. System architecture'))
children.push(P('The system has three layers. The browser shows the dashboards; the backend serves data and does all the calculations; the database stores the records.'))
children.push(P([T('Data flow:  ', { bold: true }), T('Browser (React dashboard)  →  Backend API (FastAPI)  →  Database (PostgreSQL in production, or SQLite for local use)  →  back to the browser as charts and tables.')]))
children.push(table(
  ['Layer', 'Technology', 'Responsibility'],
  [
    ['Frontend', 'React + Vite, Chart.js', 'The user interface: pages, charts, forms, login. Talks to the backend over /api.'],
    ['Backend', 'FastAPI (Python), SQLAlchemy', 'Authentication, business rules, all KPI calculations, CRUD, report generation.'],
    ['Database', 'PostgreSQL / SQLite', 'Stores production shifts, deliveries, bales, fuel dips, monthly stock, users.'],
    ['Auth', 'JWT tokens', 'Login returns a token stored in the browser and sent on every request.'],
  ],
  [1500, 2400, 5460],
))
children.push(P([T('Single-server deployment: ', { bold: true }), T('in production the built frontend is served by the same backend process, so the whole app runs from one address on the plant network.')]))

children.push(H2('3. Roles & access'))
children.push(P('Every user has one of four roles. Each higher role includes everything below it. The interface hides controls a user is not allowed to use, and the backend enforces the same rules so the limits cannot be bypassed.'))
children.push(table(
  ['Role', 'Can do'],
  [
    ['Operator', 'Log production shifts and other daily records; view all dashboards.'],
    ['Supervisor', 'Everything an operator can, plus edit existing records and delete deliveries.'],
    ['Manager', 'Everything a supervisor can, plus delete production shifts.'],
    ['Admin', 'Full control, including managing user accounts and roles (Team & Access page).'],
  ],
  [1700, 7660],
))
children.push(P([T('First login: ', { bold: true }), T('a new user is given a temporary password and is required to set their own on first sign-in (My Account page).')]))

children.push(H2('4. Application features (by page)'))
children.push(P('The left sidebar groups pages into Analytics, Operations and Settings. Every analytics page has a Month / Range period selector in the top-right.'))
children.push(table(
  ['Page', 'What it shows / does'],
  [
    ['Overview', 'Headline KPIs with trend arrows and mini-trends, a “Needs Attention” panel of auto-flagged issues, daily output with an average line, product mix, shift performance, and a one-click report export.'],
    ['Production', 'Output by product type over time, hot-press utilisation, line-speed trend, and a searchable shift log with edit (supervisor+) and delete (manager+).'],
    ['Fuel & Energy', 'Daily diesel use, fuel efficiency (L per 1,000 trays), a cost estimator, plus a fuel-dip entry form and log.'],
    ['Downtime', 'Total lost time, downtime by cause (classified from shift notes), downtime % by shift, daily trend, and longest stoppages.'],
    ['Deliveries', 'Produced-vs-delivered comparison, deliveries by customer, a delivery log, and a “Record a Delivery” form.'],
    ['Stock & Bales', 'Bale-receipt entry + log and the month-end stock balances (editable by supervisor+).'],
    ['Log Shift', 'The main end-of-shift data entry form (output, hot presses, fuel, hours, downtime, notes).'],
    ['My Account', 'Change password.'],
    ['Team & Access', 'Admin-only: create users, set roles, enable/disable and delete accounts.'],
  ],
  [1700, 7660],
))

children.push(H2('5. Data model'))
children.push(P('The database holds one table per record type. Numeric fields default to zero; dates are stored per record.'))
children.push(H3('Production shift (one row per date + shift)'))
children.push(P('A unique constraint on (date, shift) prevents two entries for the same shift on the same day; the API returns a clear error if a duplicate is attempted.'))
children.push(bullet('Identity: date, shift (Day / Afternoon / Night).'))
children.push(bullet('Output: total trays, and per product type — 30’s Small/Large, 20’s Normal, 12’s Normal/Half-Face/Full-Face, 4’s and 2’s Cup Holder.'))
children.push(bullet('Machines: hot presses HP1–HP6 (trays each).'))
children.push(bullet('Utilities & rate: labelling, water meter, carton bales, line speed.'))
children.push(bullet('Fuel: opening, closing, used.'))
children.push(bullet('Hours & downtime: production hours, downtime minutes, scheduled hours, cleaning / mold-change / other minutes, trays re-pulped.'))
children.push(bullet('Notes and audit fields (who entered it, when).'))
children.push(H3('Other tables'))
children.push(table(
  ['Table', 'Key fields'],
  [
    ['Delivery', 'date, customer, 30’s, 12’s normal, 12’s full-face, pallets, comment.'],
    ['Bale receipt', 'date, GRN number, weight (kg), quantity.'],
    ['Fuel dip', 'date, shift, opening dip, closing dip, actual usage, diesel received, note.'],
    ['Monthly stock', 'period (YYYY-MM), diesel end-of-month, product balances, pallets wrapped, bales used / purchased, labels used.'],
    ['User', 'username, full name, role, active flag, hashed password.'],
  ],
  [1900, 7460],
))

children.push(H2('6. Analytics & KPI definitions'))
children.push(P('All figures are calculated on the server from the selected period’s shifts and deliveries, so every page and the report agree. The main definitions:'))
children.push(table(
  ['KPI', 'Definition'],
  [
    ['Total trays', 'Sum of shift quantity over the period.'],
    ['Active days', 'Distinct dates with output greater than zero.'],
    ['Average / day', 'Total trays ÷ active days.'],
    ['Fuel efficiency', 'Total diesel ÷ total trays × 1,000 (litres per 1,000 trays — lower is better).'],
    ['Downtime rate', 'Total downtime minutes ÷ 60 ÷ scheduled hours × 100 (% of scheduled time lost).'],
    ['Reject rate', 'Trays re-pulped ÷ total trays × 100.'],
    ['Trend deltas', 'Each KPI is compared against the previous equal-length period; arrows show the change (direction-aware — e.g. lower fuel use is good).'],
  ],
  [2100, 7260],
))
children.push(P([T('Needs Attention: ', { bold: true }), T('the server scans the period and raises flags such as days that lost 4+ hours, an overall downtime rate above the watch line, days with poor fuel efficiency, low-output days, and a high reject rate — plus a positive “best day” highlight.')]))

children.push(H2('7. Reports & export'))
children.push(P('The Overview page has an Export button that downloads an Excel workbook for the selected period with three sheets: a Summary of all KPIs, a Shift Detail sheet (every shift row), and a Deliveries sheet. The file is generated on the server and respects the chosen month or date range.'))

children.push(H2('8. Deployment & operations'))
children.push(H3('Local use (development / a single PC, no setup)'))
children.push(P('Uses a built-in SQLite database file — no separate database to install.'))
children.push(num('Backend: create a Python virtual environment, install requirements, and start it pointing at a SQLite file. On first start it creates the admin user and imports the May data automatically.'))
children.push(num('Frontend: install dependencies and run the dev server; it proxies to the backend.'))
children.push(num('Open the app in a browser and sign in as admin (then change the password).'))
children.push(H3('Plant deployment (recommended)'))
children.push(P('Uses Docker Compose to run the frontend build, the backend, and a PostgreSQL database together, served from one address on the plant network.'))
children.push(num('Install Docker on the plant PC.'))
children.push(num('Copy the example environment file and set real secrets (database password, security key, admin password).'))
children.push(num('Start with Docker Compose; open the app at the PC’s address from any device on the network.'))
children.push(P([T('Future months: ', { bold: true }), T('an Excel importer can load new monthly files; day-to-day data is entered through the forms.')]))

children.push(H2('9. Security'))
children.push(bullet('Passwords are stored hashed, never in plain text.'))
children.push(bullet('Access is controlled by JWT tokens and enforced by role on the server.'))
children.push(bullet('Secrets (security key, database password, admin password) come from environment settings and must be changed before real deployment.'))
children.push(bullet('Network access (CORS) is open for local-network use; tighten it if the app is ever exposed beyond the plant.'))

children.push(H2('10. Backup & maintenance'))
children.push(bullet([T('Back up the database regularly. ', { bold: true }), T('For PostgreSQL use a scheduled dump; for SQLite copy the database file. Keep off-site copies.')]))
children.push(bullet('Before changing the data structure once real data exists, introduce database migrations (Alembic) rather than recreating tables.'))
children.push(bullet('Keep the plant PC’s clock synced so timestamps are accurate.'))
children.push(bullet('Rotate the admin password and any shared accounts periodically.'))

children.push(H2('11. Troubleshooting (quick reference)'))
children.push(table(
  ['Symptom', 'Likely cause / action'],
  [
    ['“A shift already exists” error', 'A shift for that date+shift is already logged. Edit the existing one instead.'],
    ['Login fails after correct password', 'Token expired or backend restarted — sign in again.'],
    ['Dashboards show no data', 'No records for the selected period — check the Month/Range selector.'],
    ['Page can’t reach the server', 'Backend not running or wrong address — check the service on the plant PC.'],
  ],
  [3200, 6160],
))

// ===== PART B =====
children.push(new Paragraph({ children: [new PageBreak()] }))
children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [T('Part B — Live Machine Integration Guide')] }))
children.push(P([T('Status: ', { bold: true }), T('design for review — no integration code has been written yet. This part is intended for plant management and the automation integrator / electrician.')]))

children.push(H2('12. Goal & scope'))
children.push(P('Bring live machine data into the dashboard so it updates itself instead of relying only on end-of-shift entry. Based on the site assessment, the machine has an HMI/SCADA screen and the one clearly digital signal available now is the line run/stop state.'))
children.push(table(
  ['Data', 'Source today', 'Plan'],
  [
    ['Machine run / stop', 'HMI/SCADA (digital)', 'Automate first — drives automatic uptime % and downtime.'],
    ['Production / press counts', 'Counted by hand', 'Stay manual; automate later if a digital counter exists.'],
    ['Fuel tank level', 'Manual dip', 'Stay manual; automate later if a level transmitter is added.'],
    ['Water meter', 'Read by hand', 'Stay manual; automate later if a pulse/flow output exists.'],
    ['Downtime reason', 'Operator note', 'Stay manual — operator labels an auto-detected stop.'],
    ['Deliveries, bales, stock', 'Manual forms', 'Stay manual (human / paperwork data).'],
  ],
  [2600, 2700, 4060],
))
children.push(P([T('Principle: ', { bold: true }), T('automate what the machine already exposes; keep everything else on the entry forms. “All data live” realistically means run/stop now, more signals later as they become digital. The first win — automatic uptime/downtime — removes the most error-prone manual task while operators still add the short reason for each stop.')]))

children.push(H2('13. Target architecture'))
children.push(P('A small, read-only collector service runs on the plant PC. It watches the run/stop signal and sends each confirmed change to the existing backend over an outbound, secured connection. The backend stores it in two new tables, and the dashboard shows live status and automatic downtime. The PLC and HMI are never written to.'))
children.push(P([T('Flow:  ', { bold: true }), T('PLC → HMI/SCADA  →(read-only)→  Collector service (plant PC)  →(HTTPS, outbound only, buffered)→  Backend ingest API  →  Machine tables  →  Dashboard.')]))
children.push(P([T('Why a separate collector ', { bold: true }), T('(rather than the web server polling directly): it keeps industrial drivers off the web server, survives network/backend outages via a local buffer, talks outbound-only so no inbound holes are opened toward the PLC, and lets the protocol be swapped without touching the dashboard.')]))

children.push(H2('14. Integration options (ranked)'))
children.push(P('The exact route depends on what the HMI/PLC supports — to be confirmed by the integrator from the discovery checklist (section 21). Best-fit first:'))
children.push(table(
  ['Option', 'How', 'Best when', 'Needs'],
  [
    ['A · SCADA log / historian', 'Read the database or CSV the SCADA already logs to (read-only).', 'The SCADA already records run/stop or alarms.', 'DB type, connection string / file path, read-only user.'],
    ['B · OPC UA', 'Subscribe to the run/stop tag on the PLC/SCADA OPC UA server.', 'Modern PLCs (e.g. Siemens S7-1200/1500) or modern SCADA.', 'Endpoint URL, security/cert, the run/stop NodeId.'],
    ['C · Modbus TCP', 'Poll a coil/register for the run bit.', 'Delta, Omron, many drives; lightweight setups.', 'IP + port (usually 502), unit ID, register address.'],
    ['D · Vendor-native', 'Direct driver: Siemens S7, Allen-Bradley, Mitsubishi, Omron.', 'A–C not available.', 'PLC IP, rack/slot or path, the tag/address.'],
    ['E · Edge gateway → MQTT', 'A gateway publishes tags; collector subscribes.', 'Later expansion to many signals.', 'Gateway + broker setup.'],
  ],
  [1700, 2900, 2480, 2280],
))
children.push(P([T('Likely path: ', { bold: true }), T('with an HMI/SCADA present, Option A (its log database) or Option B (OPC UA) are the front-runners.')]))

children.push(H2('15. The collector service'))
children.push(bullet([T('What it is: ', { bold: true }), T('a small Python program installed as an auto-starting Windows service on the plant PC, with a single config file.')]))
children.push(bullet([T('Loop: ', { bold: true }), T('read/subscribe the run/stop source → debounce (only act after the state is stable for a few seconds, to ignore flicker) → on a confirmed change, create a timestamped event → send it to the backend → send a heartbeat every ~30 s so the dashboard can show “live”.')]))
children.push(bullet([T('Store-and-forward: ', { bold: true }), T('if the backend or network is down, events queue locally and flush when the link returns — no data lost.')]))
children.push(bullet([T('Read-only & safe: ', { bold: true }), T('it never writes to the PLC; connections are read/subscribe only; outbound HTTPS only.')]))

children.push(H2('16. Data model additions'))
children.push(P('Two new tables, alongside the existing ones (manual data untouched):'))
children.push(bullet([T('Machine status ', { bold: true }), T('— current snapshot: state (running/stopped/unknown), since (when it entered that state), last-seen (drives a “link healthy / stale” badge).')]))
children.push(bullet([T('Machine events ', { bold: true }), T('— an append-only log of confirmed transitions: timestamp, run-start / run-stop, duration, shift, and reason / reason-category (filled in later by the operator).')]))
children.push(P('From these the server derives running time, stopped time, uptime %, number of stops, and average stop length — per day, shift and period — exactly like the existing KPIs. The machine tells us when and how long; the operator tells us why.'))

children.push(H2('17. Ingest API (new, secured)'))
children.push(table(
  ['Endpoint', 'Purpose'],
  [
    ['POST /api/ingest/machine/event', 'Collector posts a confirmed run/stop transition.'],
    ['POST /api/ingest/machine/heartbeat', 'Collector posts current state + timestamp.'],
    ['GET /api/machine/status', 'Dashboard reads current state + today’s uptime.'],
    ['PATCH /api/machine/events/{id}', 'Operator/supervisor adds the reason to a stop.'],
  ],
  [3700, 5660],
))
children.push(P([T('Security: ', { bold: true }), T('a dedicated, revocable device API key (separate from user logins), scoped to the ingest endpoints. Each event carries a collector-generated ID so retries after a network blip don’t double-count.')]))

children.push(H2('18. Automatic downtime logic'))
children.push(bullet([T('Micro-stops: ', { bold: true }), T('very short stops (below a configurable threshold) can be ignored or flagged separately, so jogging the line doesn’t register as downtime.')]))
children.push(bullet([T('Shift attribution: ', { bold: true }), T('each stop is assigned to the Day/Afternoon/Night shift by its timestamp; stops crossing a boundary are split.')]))
children.push(bullet([T('Reason workflow: ', { bold: true }), T('an auto-detected stop appears as “stop — reason needed”; the operator picks a reason from the existing categories. This is the only manual step left for downtime.')]))
children.push(bullet([T('Reconciliation: ', { bold: true }), T('if both an auto stop and a manual entry exist for the same window, the dashboard prefers the machine figure and flags the difference for review.')]))

children.push(H2('19. Dashboard changes'))
children.push(bullet('A live status pill in the header: green “Running · 02:14”, red “Stopped · 18 min”, or grey “Link stale”.'))
children.push(bullet('A new machine-measured Uptime % KPI alongside the existing Downtime KPI.'))
children.push(bullet('A “Stops needing a reason” list on the Downtime page, plus an auto-vs-manual comparison.'))
children.push(bullet('Everything else continues to use the manual forms.'))

children.push(H2('20. Security & safety'))
children.push(bullet([T('Read-only to the machine ', { bold: true }), T('— no writes to the PLC, ever. This is a monitoring link.')]))
children.push(bullet([T('Network isolation ', { bold: true }), T('— collector on the plant/OT network; outbound HTTPS only to the backend; no inbound ports opened toward the PLC; ideally a separate VLAN with a one-way firewall rule.')]))
children.push(bullet([T('Least privilege ', { bold: true }), T('— a read-only DB user (Option A) or a read-only OPC UA / Modbus account.')]))
children.push(bullet([T('Fail-safe ', { bold: true }), T('— if the collector or link dies, the dashboard shows “stale” and manual entry still works; the machine is never affected by the dashboard being down.')]))
children.push(bullet([T('Change control ', { bold: true }), T('— all wiring and network changes done by the plant electrician / integrator.')]))

children.push(H2('21. Discovery checklist (what we need)'))
children.push(P('Please gather the following — this is what unblocks building the real connection:'))
children.push(num('HMI brand & model (bezel, boot screen, or sticker) and a photo.'))
children.push(num('PLC brand & model in the cabinet (electrician) and a photo of the sticker.'))
children.push(num('Network: does the PLC or HMI have an Ethernet port with a cable? Is there a switch in the cabinet? What is its IP?'))
children.push(num('Existing logging: does the SCADA write to a database or CSV? If so, which (SQL Server / MySQL / SQLite / CSV)?'))
children.push(num('The run/stop tag: the tag name / NodeId / register address that means “line running”, and its data type.'))
children.push(num('Who commissioned/maintains it (machine supplier or local contractor) — they can provide a tag list and enable read-only access.'))
children.push(num('Confirmation that the plant PC can reach the machine network, or what firewall/VLAN rule is needed.'))
children.push(num('Confirmation that the PLC/HMI and plant PC clocks are time-synced (NTP).'))

children.push(H2('22. Phased rollout'))
children.push(table(
  ['Phase', 'What', 'Needs'],
  [
    ['0 · Discovery', 'Fill the checklist (section 21); pick the protocol route.', 'Integrator / electrician.'],
    ['1 · Pipeline + simulator', 'Build the collector, ingest API, machine tables and live-status UI; test end-to-end against a machine simulator.', 'Nothing from the plant — fully testable in-office.'],
    ['2 · Connect run/stop', 'Point the collector at the real tag; validate uptime/downtime vs reality for a week.', 'Connection details from section 21.'],
    ['3 · Reason workflow', 'Operators label auto-detected stops; reconcile with manual logs.', 'Operator buy-in.'],
    ['4 · Expand (optional)', 'Add production counts / fuel level / water meter if/when they become digital.', 'New sensors / transmitters.'],
  ],
  [1900, 4760, 2700],
))
children.push(P([T('Recommended: ', { bold: true }), T('start Phase 1 now — it needs nothing from the floor and de-risks everything — so the day connection details arrive, only the real driver is swapped in.')]))

children.push(H2('23. Future expansion'))
children.push(P('If a digital production counter, fuel-level transmitter, or pulse water meter is added later, each becomes another tag in the same collector config and another reading type in the same pipeline — no re-architecture. The manual forms for those simply become the fallback/override.'))

// Glossary
children.push(new Paragraph({ children: [new PageBreak()] }))
children.push(H1('Appendix — Glossary'))
children.push(table(
  ['Term', 'Meaning'],
  [
    ['PLC', 'Programmable Logic Controller — the controller running the machine logic.'],
    ['HMI / SCADA', 'The operator screen / software that shows and logs machine state.'],
    ['OPC UA', 'A standard, secure industrial protocol for reading tags.'],
    ['Modbus TCP', 'A simple, widespread industrial protocol over Ethernet.'],
    ['Tag', 'A named value in the PLC/SCADA (e.g. “Line.Running”).'],
    ['Historian', 'A database the SCADA uses to log values over time.'],
    ['Store-and-forward', 'Buffering data locally during an outage and sending it later.'],
    ['KPI', 'Key Performance Indicator — a headline metric (e.g. uptime %).'],
    ['JWT', 'A signed token that proves a user is logged in.'],
    ['NTP', 'Network Time Protocol — keeps clocks synced across devices.'],
  ],
  [2200, 7160],
))

// ---------- document ----------
const doc = new Document({
  creator: 'Golden Manufacturers',
  title: 'Fibre Mold Plant Dashboard — Knowledge Base & Machine Integration Guide',
  styles: {
    default: { document: { run: { font: 'Arial', size: 21, color: INK } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 30, bold: true, color: INK, font: 'Arial' },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: AMBER, space: 4 } } } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 25, bold: true, color: INK, font: 'Arial' },
        paragraph: { spacing: { before: 260, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 22, bold: true, color: '333333', font: 'Arial' },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: 'b', levels: [
        { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 540, hanging: 260 } } } },
        { level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1080, hanging: 260 } } } },
      ] },
      { reference: 'n', levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 540, hanging: 300 } } } },
      ] },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({
      alignment: AlignmentType.RIGHT,
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'DDDDDD', space: 4 } },
      children: [T('Fibre Mold Plant Dashboard — Knowledge Base', { size: 16, color: MUT })],
    })] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      tabStops: [{ type: 'right', position: CW }],
      border: { top: { style: BorderStyle.SINGLE, size: 4, color: 'DDDDDD', space: 4 } },
      children: [
        T('Golden Manufacturers · Confidential', { size: 16, color: MUT }),
        T('\tPage ', { size: 16, color: MUT }),
        new TextRun({ children: [PageNumber.CURRENT], size: 16, color: MUT }),
        T(' of ', { size: 16, color: MUT }),
        new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: MUT }),
      ],
    })] }) },
    children,
  }],
})

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(process.argv[2] || 'out.docx', buf)
  console.log('written', (process.argv[2] || 'out.docx'), buf.length, 'bytes')
})
