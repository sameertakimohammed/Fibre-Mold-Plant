# Fibre Mold Plant — Production Dashboard User Training Guide

**Golden Manufacturers · Recycling Department**
For team leaders to train operators, supervisors and managers.

This guide explains how to use the Fibre Mold Plant dashboard for day-to-day work: logging shifts, recording deliveries and materials, reading the production dashboards, and generating reports. It is written so a supervisor or manager can walk new users through the system step by step.

> **For the trainer:** add your plant's real screenshots in the marked spots (📷) before handing this to staff — it makes training much faster.

---

## 1. What the system is

The dashboard is the single place where the plant's daily production is recorded and reviewed. At the end of every shift the operator enters the shift's figures; those numbers then flow automatically into the dashboards (output, fuel, downtime, deliveries) and into the reports management uses. If the figures are entered accurately and on time, every chart and report is correct — so **accurate shift logging is the most important habit to build**.

- **Where to find it:** open a web browser and go to **https://fibremold.gml.com.fj**
- Works on a PC, laptop, tablet or phone (the layout adapts to the screen).
- You can even log a shift when the internet is down — see **5.6 (Offline)**.

---

## 2. Logging in & finding your way around

### 2.1 Signing in
1. Open the address above in your browser.
2. Enter your **username** and **password** (your supervisor/admin creates these for you).
3. The first time you log in, you'll be asked to **set a new password** (at least 8 characters).

📷 *Screenshot: the login screen*

> **Security:** after 5 wrong password attempts the account locks for 15 minutes, then unlocks itself. If you're locked out, wait or ask an admin.

### 2.2 The screen layout
- **Left sidebar** — the menu, grouped as Analytics, Operations, Reports and Settings.
- **Top bar** — sync status (offline/online), the light/dark theme toggle, and the notifications bell.
- **Bottom-left** — your name and role, and the **Sign out** button.
- On a phone/tablet, tap the **☰** menu button to open the sidebar.

📷 *Screenshot: the full dashboard with the sidebar labelled*

---

## 3. Roles & what each person can do

What you can see and do depends on your role. The dashboard hides buttons you don't have access to.

| Role | Can do |
|---|---|
| **Operator** | Log production shifts. View the dashboards. |
| **Supervisor** | Everything an operator can, plus: edit recent records, and record deliveries, fuel dips, bale receipts and month-end stock. |
| **Manager** | Full analytics & reports access (review and download). Set KPI targets. |
| **Admin** | Full control, including creating users and assigning roles, the audit trail, and backup status. |

> **Note:** roles are set by your admin under **Team & Access**. If you can't do something you think you should, check your role with your supervisor.

---

## 4. Choosing the time period

Most analytics screens have a **period control** in the top-right. It opens on the **current month** automatically, so when a new month starts the dashboards show the new month straight away.

- **Month** — click the calendar control and pick any month/year.
- **Range** — switch to Range to choose a custom start and end date.

📷 *Screenshot: the Month / Range period control on the Overview page*

---

## 5. Logging a production shift (the core daily task)

This is the most important task. Do it at the **end of every shift**, from the figures recorded on the floor.

### 5.1 Open the form
1. In the sidebar, under **Operations**, click **Log Shift**.
2. Pick the **Date** and the **Shift** (Day / Afternoon / Night).

📷 *Screenshot: the Log Shift form*

### 5.2 Fill in the figures
The form is grouped into sections — enter what applies; leave anything you don't have as **0**.

| Section | What to enter |
|---|---|
| **Output** | Total Trays (Qty) and the breakdown by product: 30's Small/Large, 20's, 12's Normal/Half/Full Face, 4's & 2's cups. |
| **Hot Presses** | Trays pressed on each machine, HP1–HP6. |
| **Fuel · Water · Speed** | Diesel opening/closing/used (litres), water meter, line speed, carton bales. |
| **Hours & Downtime** | Production hours, scheduled hours, total downtime (min), and the breakdown: cleaning, mold change, other; plus trays re-pulped. |
| **Notes** | A short comment — especially the **reason for any downtime** (e.g. "mold washing", "pump repair"). |

> **Why it matters:** the downtime reason in Notes is used to classify downtime causes on the Downtime page and in reports. A few clear words ("mold change", "cleaning", "maintenance") make those charts meaningful.

### 5.3 Helpful warnings
As you type, the form may show amber warnings such as *"Product types add up to X but Total Trays is Y"* or *"Fuel Used doesn't match Opening − Closing"*. These are reminders to double-check a likely typo — they **do not block you**. If the numbers are genuinely correct, you can still save.

### 5.4 Save
1. Click **Save Shift**.
2. A confirmation appears and the figures immediately update every dashboard.

> **Note:** each date+shift can only be logged once. If you try to log the same shift twice you'll get a message — edit the existing one instead (see section 7).

### 5.5 If you make a mistake
See **section 7** — supervisors can edit a shift and managers can delete one.

### 5.6 Working offline
If the internet drops, you can still log the shift: it is saved on the device and the top bar shows a **"saved offline"** status. When the connection returns, it **syncs automatically** — you don't have to re-enter it.

📷 *Screenshot: the offline/sync indicator in the top bar*

---

## 6. Recording deliveries, fuel & materials (supervisor+)

These screens have a **"Record …"** button that opens a short form. Fill it in and save; the figures update the relevant dashboard immediately.

| Screen (sidebar) | What you record |
|---|---|
| **Deliveries** | Each customer dispatch: date, customer, 30's, 12's (normal/full face), pallets, comment. |
| **Fuel & Energy** | Tank dip readings: date, shift, opening/closing dip, actual usage, diesel received, note. |
| **Stock & Bales** | Bale receipts (date, GRN #, weight, quantity) and the month-end stock balances. |

> **Note:** fuel and bale forms also show gentle warnings if a number looks inconsistent (e.g. dip usage vs opening − closing + received).

---

## 7. Correcting a record

Every log table (shifts, deliveries, fuel dips, bales) has **Edit / Delete** buttons on each row, shown according to your role:

- **Edit a record** — supervisor and above. Click **Edit**, change the values, **Save Changes**.
- **Delete a record** — manager and above for shifts and month-end stock; supervisor and above for deliveries, fuel dips and bales.
- Deletions are **"soft"** — the record is removed from view and totals, and the action is recorded in the audit trail.

📷 *Screenshot: a log table showing the Edit and Delete buttons*

---

## 8. Reading the dashboards

### 8.1 Overview
The headline of the plant for the selected period: **total trays, average per day, fuel burned & efficiency, downtime, and reject (re-pulp) rate**. Cards show the trend vs the previous period, and — when targets are set — a small bar showing how you're tracking against target. The **"Needs Attention"** panel automatically flags heavy-downtime days, poor fuel days, low-output days and high reject rates. For the current month a **projected month-end output** is shown.

- **Setting targets (manager+):** click **◎ Targets** on the Overview to set goals for avg/day, fuel efficiency, downtime % and reject %.

📷 *Screenshot: the Overview KPI cards and Needs Attention panel*

### 8.2 Production / Fuel / Downtime / Deliveries

| Page | What it shows |
|---|---|
| **Production** | Daily output, product mix over time, hot-press utilisation, line speed, and a searchable shift log. |
| **Fuel & Energy** | Daily diesel use, efficiency (litres per 1,000 trays), a cost estimator, and the dip log. |
| **Downtime** | Lost hours, downtime by cause (from the shift notes), worst stoppages, and daily downtime trend. |
| **Deliveries** | Produced vs delivered, top customers by volume, and the delivery log. |
| **Stock & Bales** | Bale receipts and the month-end stock balances. |

### 8.3 Notifications
The **bell** in the top bar shows automatic alerts (e.g. a heavy-downtime day). Click it to read and dismiss them.

---

## 9. Generating reports

1. Open **Reports** in the sidebar.
2. Choose a cadence — **Daily, Weekly or Monthly** — and pick the date/month from the calendar.
3. Preview the figures on screen, then download in the format you need.

| Format | Best for |
|---|---|
| **Excel (.xlsx)** | Working with the raw figures; includes summary, shift detail and deliveries sheets. |
| **PDF** | A clean printable report. |
| **CSV** | Importing the raw shift rows into another spreadsheet/tool. |
| **PowerPoint deck** | Management review: pick a **From** and **To** month — you get per-month detail slides plus overall trend-comparison slides. |
| **Month End Report** | The plant's stock & materials month-end summary (Excel or PDF). |

> **Optional:** if the AI assistant is switched on, reports can also include an AI-written summary and improvement plan, and a "Plant Manager's Commentary" on the Reports page.

📷 *Screenshot: the Reports page with the format buttons*

---

## 10. Administrator tasks

- **Team & Access** — create users, set their role, deactivate someone who leaves, reset access.
- **Audit Trail** — a tamper-evident record of every change (who did what, when), with a **Verify** button.
- **Database Backups** (on My Account, admins only) — shows the age and size of the latest nightly backup so you know the data is safe.

> **Best practice:** give each person their own login — never share accounts. It keeps the audit trail meaningful and lets you set the right role per person.

---

## 11. Your account & preferences

- **My Account** — change your password at any time.
- **Theme** — use the toggle in the top bar to switch between light and dark.
- **Sign out** — bottom-left of the sidebar, especially on shared computers.

---

## 12. Good working practices

- Log each shift **at the end of the shift**, from the recorded floor figures — don't leave it to the next day.
- Always write the **downtime reason** in Notes; it drives the downtime analysis.
- **Check amber warnings** before saving — they catch most typos.
- **One login per person**; sign out on shared PCs.
- Managers: review the Overview **"Needs Attention"** panel daily and the **Month End** report monthly.

---

## 13. Troubleshooting & FAQ

| Question / problem | What to do |
|---|---|
| I'm locked out after wrong passwords | Wait 15 minutes (it auto-unlocks) or ask an admin. |
| I forgot my password | An admin can reset it under Team & Access. |
| "A shift for this date already exists" | It's already logged — open Production and **Edit** that shift instead. |
| A dashboard shows no data | Check the **period** (top-right) — it may be on a month with no entries. Pick the right month. |
| I logged a shift but the internet was down | It's saved on the device and **syncs automatically** when you reconnect (see 5.6). |
| A page shows an error | Refresh the page (Ctrl+Shift+R). If it persists, note what you clicked and tell your admin. |
| I can't see the Edit/Record buttons | Your role may not allow it — check with your supervisor. |

---

## 14. Glossary

| Term | Meaning |
|---|---|
| Tray / 30's, 12's | The moulded products; 30's and 12's are tray/carton sizes (Normal, Half Face, Full Face). |
| Shift | Day, Afternoon or Night production period. |
| Downtime | Time the line was stopped, in minutes; classified by cause from the notes. |
| Re-pulp / reject rate | Trays sent back to be re-pulped, as a % of output — lower is better. |
| Fuel efficiency | Litres of diesel per 1,000 trays — lower is better. |
| Bale / GRN | A bale of raw waste paper; GRN = Goods Received Note number. |
| Month-end stock | Closing balances of diesel, products, pallets, labels and bales for the month. |
| Target | A management goal a KPI is compared against on the Overview. |

---

## 15. Quick reference — by role

**Operator — daily**
- Log Shift at end of shift → fill figures → check warnings → **Save**.

**Supervisor — daily / as needed**
- Log shifts; record Deliveries, Fuel dips, Bales; edit recent records; correct mistakes.

**Manager — review**
- Review Overview & Needs Attention; set Targets; download Reports / Month End / PowerPoint.

**Admin — setup**
- Create users & roles (Team & Access); check Audit Trail and Backups.

---

*Fibre Mold Plant dashboard — user training guide. Customise with your plant's screenshots before distribution.*
