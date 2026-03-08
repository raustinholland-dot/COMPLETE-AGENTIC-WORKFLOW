# PRD — Clearwater Deal Intelligence Engine (Condensed)

**Phases 1–5 COMPLETE. Phase 6 NOT STARTED.**

---

## System Purpose
RAG-based AI automation on n8n for Austin Hollins (AE) at Clearwater Security & Compliance.
Ingests deal communications → scores P2V2C2 → generates outputs → answers deal questions via chat.

---

## Phase Status

| Phase | Status | Summary |
|---|---|---|
| 1: Ingestion | COMPLETE | PA/Outlook webhook → classify → chunk → embed → Qdrant |
| 2: Deal Health | COMPLETE | CW-02, 26 nodes, P2V2C2 + 22 artifacts, CAS, DAP, Opus 4.6 |
| 3: Output Gen | COMPLETE | Workflow 3b webhook entry + Workflow 3e intelligent generation |
| 4: Chat Agent | COMPLETE | Workflow 3a chat entry, 6 tools, RAG Q&A + draft generation |
| 5: AD Tracker + Calendar | COMPLETE | CW-05 AD Tracker, CW-06 Calendar Sync |
| 6: Salesforce Sync | NOT STARTED | Bi-directional sync, auto-push scores to SF opportunities |

---

## Phase 6 — Salesforce Sync (Requirements)

**Goal:** Push P2V2C2 scores and deal stage back to Salesforce after every CW-02 scoring run. Pull SF opportunity data into the deals table on a nightly schedule.

**Trigger:** CW-02 tail → HTTP POST to new CW-07: Salesforce Sync workflow.

**Outbound (n8n → SF):**
- Update Opportunity custom fields: Pain__c, Power__c, Vision__c, Value__c, Change__c, Control__c, P2V2C2_Total__c, CAS__c, DAP_Status__c
- Only update if score changed (compare to last SF push timestamp)

**Inbound (SF → n8n):**
- Nightly schedule trigger (11pm ET)
- Pull all active Opportunities via SOQL
- Upsert into `deals` table: deal_name, stage, close_date, deal_value_usd, forecast_category, deal_owner
- Create shell deal records for any new SF Opps not yet in `deals`

**Credentials needed:**
- Salesforce OAuth2 (Connected App): `SALESFORCE_CLIENT_ID`, `SALESFORCE_CLIENT_SECRET`, `SALESFORCE_INSTANCE_URL`
- Already in `.env` (blank values — fill before building)

**Key constraint:** Salesforce API = 15-second timeout on n8n HTTP nodes. Use bulk query + batch upsert pattern.

---

## CPS P2V2C2 Scoring Rubric (quick ref)

| Dim | 0 | 5 |
|---|---|---|
| Pain | No knowledge | ES agreed pain large enough to change |
| Power | No idea who is power | DAP steps on schedule |
| Vision | No idea of needs | ES painting vision to others |
| Value | Benefits unknown | DM agreed to financial terms |
| Change | No one committed | ES convinced DM they must change |
| Control | Buying process unknown | DAP complete |

Stages: Discover → Qualify → Prove → Negotiate → Close
Roles: PC / C / PES / ES / DM / DAP

---

## 22 Tracked Artifacts (CW-02 outputs)
pain_score, power_score, vision_score, value_score, change_score, control_score,
pe_sponsor_score, critical_activity_stage, champion_name, champion_title,
executive_sponsor_name, executive_sponsor_title, dap_exists, dap_agreed, dap_status,
dap_milestones_complete, dap_has_14_day_gap, dap_next_milestone, dap_next_milestone_date,
current_state_org/activities/technology, future_state_org/activities/technology,
key_stakeholder_success_criteria, risks, next_step, next_step_date,
call_summary, services_narrative, general_narrative
