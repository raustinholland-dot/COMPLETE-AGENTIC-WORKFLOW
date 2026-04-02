# Input → Output Map
*Ground truth dataset for building Johnny's skill prompts.*
*Populated session by session. Each row = one real input Austin labeled.*

---

## How to Read This

- **Condition** — what must be true for the output to fire. Empty = always fires.
- **Output** — exact file path + description of the write.
- **Draft** — if an email/Telegram message gets sent, noted here.

---

## April 1, 2026

### INPUT-001
**Time:** 8:32 AM CT
**Type:** Inbound email (forwarded newsletter)
**From:** Richmond Donnelly
**Subject:** FW: 2026 Behavioral Health Workforce Outlook / CapGrow at ANCOR Connect
**Summary:** Richmond forwarding CapGrow newsletter. Notes Austin met Dene (CapGrow, behavioral health RE) at Sessions last fall. She had dinner with David in Miami. ANCOR Connect is April 21-23, Boston, Booth #511.

| # | Output | File | Condition |
|---|--------|------|-----------|
| 1 | Create ANCOR Connect event file (research: dates, location, cost, vertical fit) | `ops/events/conferences/ancor-connect-2026.md` | Always |
| 2 | Add ANCOR Connect to Horizon table | `ops/events/index.md` | Always |
| 3 | Create contact entry for Dene (CapGrow, behavioral health RE, met at Sessions, Miami dinner w/ David) | `reference/deal-contacts.md` | Only if no existing record found |
| 4 | Scan all deal files for Dene/CapGrow mentions, note findings in her contact entry | `deals/*/deal-state.md` → `reference/deal-contacts.md` | Only if contact entry created |
| 5 | Add task: reach out to Dene before ANCOR Connect | `ops/tasks/index.md` | Only if prior relationship record exists |
| 6 | Note Austin replied to Richmond re: ANCOR Connect | `memory/2026-04-01.md` | Always |
| 7 | Draft reply to Richmond: confirms remembers Dene, shares event intel, suggests worthwhile to attend, flags wanting to discuss | **Email draft → Telegram** | Always |

---

<!-- Next inputs go here -->
