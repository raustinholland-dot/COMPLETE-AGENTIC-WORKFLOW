-- ─────────────────────────────────────────────────────────────────────────────
-- Clearwater Deal Intelligence Engine — PostgreSQL Schema
-- Run automatically on first docker compose up
-- ─────────────────────────────────────────────────────────────────────────────

-- Create databases for n8n and Metabase
CREATE DATABASE n8n;
CREATE DATABASE metabase;

-- Switch to deals database (created by POSTGRES_DB env var)
\c clearwater_deals;

-- ─────────────────────────────────────────────────────────────────────────────
-- DEALS — Master deal registry, maps deal slugs to Salesforce opportunities
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deals (
    id                  SERIAL PRIMARY KEY,
    deal_id             VARCHAR(128) UNIQUE NOT NULL,   -- e.g. "clearwater_acmehospital_2025"
    company_name        VARCHAR(255) NOT NULL,
    sender_domains      TEXT[],                          -- ["acmehospital.org", "acme.com"]
    salesforce_opp_id   VARCHAR(64),                    -- e.g. "006Dn000001abc"
    salesforce_stage    VARCHAR(128),                   -- e.g. "Prove | 3B: Document Approach"
    deal_stage          VARCHAR(64),                    -- discover/qualify/prove/negotiate/close
    deal_value_usd      NUMERIC(12,2),
    close_date          DATE,
    forecast_category   VARCHAR(32),                    -- pipeline/upside/commit
    deal_owner          VARCHAR(255),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    is_active           BOOLEAN DEFAULT TRUE
);

-- ─────────────────────────────────────────────────────────────────────────────
-- INGESTION_LOG — Tracks every document ingested, prevents deduplication
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_log (
    id                  SERIAL PRIMARY KEY,
    message_id          VARCHAR(255) UNIQUE NOT NULL,   -- Gmail message ID
    deal_id             VARCHAR(128),                   -- FK to deals.deal_id
    attribution_confidence VARCHAR(16) DEFAULT 'low',  -- high/medium/low
    attribution_status  VARCHAR(32) DEFAULT 'pending', -- confirmed/pending/rejected
    sender_email        VARCHAR(255),
    sender_domain       VARCHAR(128),
    subject             TEXT,
    doc_type            VARCHAR(64),                    -- email/call_transcript/pdf/pptx/csv/other
    attachment_count    INTEGER DEFAULT 0,
    chunk_count         INTEGER DEFAULT 0,
    qdrant_namespace    VARCHAR(128),
    ingested_at         TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at        TIMESTAMPTZ,
    confirmed_by        VARCHAR(128) DEFAULT 'austin'
);

CREATE INDEX IF NOT EXISTS idx_ingestion_log_deal_id ON ingestion_log(deal_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_log_status ON ingestion_log(attribution_status);

-- ─────────────────────────────────────────────────────────────────────────────
-- DEAL_HEALTH — P2V2C2 scores over time (every ingestion triggers a re-score)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deal_health (
    id                      SERIAL PRIMARY KEY,
    deal_id                 VARCHAR(128) NOT NULL,
    scored_at               TIMESTAMPTZ DEFAULT NOW(),
    trigger_message_id      VARCHAR(255),               -- which ingestion triggered this score

    -- CPS Stage
    salesforce_stage        VARCHAR(128),               -- "Prove | 3B: Document Approach"
    deal_stage              VARCHAR(64),                -- discover/qualify/prove/negotiate/close
    critical_activity_stage VARCHAR(128),               -- e.g. "3B: Document Approach"

    -- P2V2C2 Scores (0-5 each)
    pain_score              SMALLINT CHECK (pain_score BETWEEN 0 AND 5),
    pain_justification      TEXT,
    pain_evidence_source    VARCHAR(255),               -- doc type + date

    power_score             SMALLINT CHECK (power_score BETWEEN 0 AND 5),
    power_justification     TEXT,
    power_evidence_source   VARCHAR(255),

    vision_score            SMALLINT CHECK (vision_score BETWEEN 0 AND 5),
    vision_justification    TEXT,
    vision_evidence_source  VARCHAR(255),

    value_score             SMALLINT CHECK (value_score BETWEEN 0 AND 5),
    value_justification     TEXT,
    value_evidence_source   VARCHAR(255),

    change_score            SMALLINT CHECK (change_score BETWEEN 0 AND 5),
    change_justification    TEXT,
    change_evidence_source  VARCHAR(255),

    control_score           SMALLINT CHECK (control_score BETWEEN 0 AND 5),
    control_justification   TEXT,
    control_evidence_source VARCHAR(255),

    p2v2c2_total            SMALLINT GENERATED ALWAYS AS
                                (pain_score + power_score + vision_score +
                                 value_score + change_score + control_score) STORED,

    -- Executive Sponsor Score
    pe_sponsor_score        SMALLINT CHECK (pe_sponsor_score BETWEEN 0 AND 5),
    pe_sponsor_justification TEXT,

    -- DAP
    dap_exists              BOOLEAN DEFAULT FALSE,
    dap_agreed              BOOLEAN DEFAULT FALSE,
    dap_status              VARCHAR(64),            -- 'Confirmed by client' OR 'Internal Draft'
    dap_milestones_total    SMALLINT DEFAULT 14,
    dap_milestones_complete SMALLINT DEFAULT 0,
    dap_has_14_day_gap      BOOLEAN DEFAULT FALSE,
    dap_next_milestone      TEXT,
    dap_next_milestone_date DATE,
    dap_timeline            JSONB,                  -- Array of 14 milestone objects
    dap_summary             TEXT,

    -- Deal Context
    close_date              DATE,
    days_in_stage           INTEGER,
    forecast_category       VARCHAR(32),

    -- Current & Future State
    current_state_org       TEXT,
    current_state_activities TEXT,
    current_state_technology TEXT,
    future_state_org        TEXT,
    future_state_activities TEXT,
    future_state_technology TEXT,

    -- Stakeholders
    champion_name           VARCHAR(255),
    champion_title          VARCHAR(255),
    pes_name                VARCHAR(255),   -- Potential Executive Sponsor (not yet chosen Clearwater)
    pes_title               VARCHAR(255),
    executive_sponsor_name  VARCHAR(255),   -- Confirmed ES (has chosen Clearwater)
    executive_sponsor_title VARCHAR(255),
    key_stakeholder_success_criteria TEXT,

    -- Risks & Actions
    risks                   TEXT[],
    next_step               TEXT,
    next_step_date          DATE,

    -- Summaries
    call_summary            TEXT,
    highlights              TEXT[],
    action_items_prospect   TEXT[],
    action_items_internal   TEXT[],
    internal_actions        TEXT[],
    services_narrative      TEXT,
    general_narrative       TEXT,
    internal_team_update    TEXT,   -- Two-paragraph mandate, no bullets

    -- Trend
    trend_direction         VARCHAR(16),    -- improving/stable/declining
    score_vs_previous       SMALLINT        -- delta from last scored_at
);

CREATE INDEX IF NOT EXISTS idx_deal_health_deal_id ON deal_health(deal_id);
CREATE INDEX IF NOT EXISTS idx_deal_health_scored_at ON deal_health(scored_at);
CREATE INDEX IF NOT EXISTS idx_deal_health_total ON deal_health(p2v2c2_total);

-- ─────────────────────────────────────────────────────────────────────────────
-- OUTPUTS_LOG — Tracks every AI-generated output per deal/contact
-- Ensures Output Generation Agent remembers what it has already sent
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS outputs_log (
    id                  SERIAL PRIMARY KEY,
    deal_id             VARCHAR(128) NOT NULL,
    output_type         VARCHAR(64) NOT NULL,   -- follow_up_email/pre_call_planner/internal_update
                                                -- /approach_pdf/exec_ppt/circle_back/meeting_confirm
    recipient_email     VARCHAR(255),           -- external (prospect) or internal
    recipient_name      VARCHAR(255),
    subject             VARCHAR(512),
    content_summary     TEXT,                   -- 2-3 sentence summary of what was sent
    full_content        TEXT,                   -- full text of email or file path for PDF/PPT
    file_path           VARCHAR(512),           -- for PDF/PPT outputs
    sent_at             TIMESTAMPTZ DEFAULT NOW(),
    triggered_by        VARCHAR(128),           -- 'chat_agent' / 'scheduled' / 'auto'
    gmail_message_id    VARCHAR(255),           -- Gmail send confirmation ID
    status              VARCHAR(32) DEFAULT 'sent'  -- sent/draft/failed
);

CREATE INDEX IF NOT EXISTS idx_outputs_deal_id ON outputs_log(deal_id);
CREATE INDEX IF NOT EXISTS idx_outputs_recipient ON outputs_log(recipient_email);
CREATE INDEX IF NOT EXISTS idx_outputs_type ON outputs_log(output_type);

-- ─────────────────────────────────────────────────────────────────────────────
-- ATTRIBUTION_QUEUE — Holds low-confidence deal attributions for confirmation
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS attribution_queue (
    id                  SERIAL PRIMARY KEY,
    message_id          VARCHAR(255) UNIQUE NOT NULL,
    sender_email        VARCHAR(255),
    sender_domain       VARCHAR(128),
    subject             TEXT,
    email_date          TIMESTAMPTZ,
    ai_guess_deal_id    VARCHAR(128),
    ai_guess_company    VARCHAR(255),
    ai_confidence       NUMERIC(4,3),           -- 0.000 to 1.000
    alt_deals           JSONB,                  -- [{deal_id, company_name, confidence}]
    doc_type            VARCHAR(64),
    queued_at           TIMESTAMPTZ DEFAULT NOW(),
    resolved_at         TIMESTAMPTZ,
    resolved_deal_id    VARCHAR(128),
    resolution          VARCHAR(32) DEFAULT 'pending'  -- pending/confirmed/rejected/new_deal
);

-- ─────────────────────────────────────────────────────────────────────────────
-- DEAL_STAKEHOLDERS — Stakeholder role progression per deal over time
-- One row per stakeholder per scoring run. Role can change run-to-run.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deal_stakeholders (
    id                  SERIAL PRIMARY KEY,
    deal_id             VARCHAR(128) NOT NULL,
    scoring_run_id      INTEGER,                -- FK to deal_health.id (nullable until inserted)
    scored_at           TIMESTAMPTZ DEFAULT NOW(),

    name                VARCHAR(255) NOT NULL,
    title               VARCHAR(255),
    email               VARCHAR(255),
    company             VARCHAR(255),

    -- CPS role assigned as of this scoring run
    cps_role            VARCHAR(16) NOT NULL    -- PC / C / PES / ES / DM / UDM / PE_SPONSOR / OTHER
                        CHECK (cps_role IN ('PC','C','PES','ES','DM','UDM','PE_SPONSOR','OTHER')),

    -- What evidence supports this role assignment
    role_evidence       TEXT,

    -- Has this person been met / engaged directly by Austin?
    directly_engaged    BOOLEAN DEFAULT FALSE,

    -- Key success criteria / personal motivation for this stakeholder
    success_criteria    TEXT
);

CREATE INDEX IF NOT EXISTS idx_stakeholders_deal_id ON deal_stakeholders(deal_id);
CREATE INDEX IF NOT EXISTS idx_stakeholders_scored_at ON deal_stakeholders(scored_at);
CREATE INDEX IF NOT EXISTS idx_stakeholders_role ON deal_stakeholders(cps_role);

-- ─────────────────────────────────────────────────────────────────────────────
-- CALENDAR_EVENTS — Phase 1: Mirror of Google Calendar
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS calendar_events (
    id                  SERIAL PRIMARY KEY,
    google_event_id     VARCHAR(255) UNIQUE NOT NULL,
    title               TEXT,
    description         TEXT,
    start_time          TIMESTAMPTZ,
    end_time            TIMESTAMPTZ,
    attendees           TEXT[],
    location            TEXT,
    deal_id             VARCHAR(128),           -- linked deal if identified
    meeting_type        VARCHAR(64),            -- discovery/qualify/prove/debrief/internal/other
    agenda_sent         BOOLEAN DEFAULT FALSE,
    agenda_sent_at      TIMESTAMPTZ,
    synced_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calendar_deal_id ON calendar_events(deal_id);
CREATE INDEX IF NOT EXISTS idx_calendar_start ON calendar_events(start_time);

-- ─────────────────────────────────────────────────────────────────────────────
-- AGENT_MEMORY — Persistent cross-session memory per deal (used by n8n agents)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS n8n_chat_histories (
    id              SERIAL PRIMARY KEY,
    session_id      VARCHAR(255) NOT NULL,
    message         JSONB NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_session_id ON n8n_chat_histories(session_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- CLEARWATER_SERVICES — Authoritative service/workstream catalog (37 entries)
-- Single source of truth injected into Agent 2 Opus prompt at run time
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clearwater_services (
    id              SERIAL PRIMARY KEY,
    service_slug    VARCHAR(80) UNIQUE NOT NULL,    -- e.g. 'risk_analysis', 'managed_azure_cloud'
    service_name    VARCHAR(200) NOT NULL,
    practice_area   VARCHAR(100),                   -- e.g. 'Risk Management', 'Managed Security'
    pricing_contact VARCHAR(50) DEFAULT 'carter',   -- 'carter' | 'steve_akers' | 'standard'
    delivery_lead   VARCHAR(200),                   -- name inferred from scoping docs
    description     TEXT,
    client_problem  TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_services_practice ON clearwater_services(practice_area);
CREATE INDEX IF NOT EXISTS idx_services_active ON clearwater_services(is_active);

-- ─────────────────────────────────────────────────────────────────────────────
-- CLEARWATER_STAFF — Employee roster for DC assignment (~214 employees)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clearwater_staff (
    id              SERIAL PRIMARY KEY,
    full_name       VARCHAR(200) NOT NULL,
    email           VARCHAR(200),
    title           VARCHAR(200),
    department      VARCHAR(100),   -- 'Delivery', 'Sales', 'Leadership', 'Operations', 'Marketing', etc.
    practice_area   VARCHAR(100),   -- maps to clearwater_services.practice_area
    is_delivery     BOOLEAN DEFAULT FALSE,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_staff_name ON clearwater_staff(full_name);
CREATE INDEX IF NOT EXISTS idx_staff_delivery ON clearwater_staff(is_delivery);
CREATE INDEX IF NOT EXISTS idx_staff_practice ON clearwater_staff(practice_area);

-- ─────────────────────────────────────────────────────────────────────────────
-- APPROACH_DOC — Living AD record per deal (one row per deal, upserted)
-- Key objectives NOT stored here — read from latest deal_health row (single source of truth)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS approach_doc (
    id                      SERIAL PRIMARY KEY,
    deal_id                 VARCHAR(100) UNIQUE NOT NULL REFERENCES deals(deal_id),
    -- Pricing
    pricing_requested       BOOLEAN DEFAULT FALSE,
    pricing_requested_at    TIMESTAMPTZ,
    pricing_contact         VARCHAR(50),             -- 'carter' | 'steve_akers'
    pricing_notes           TEXT,
    -- DC Assignment
    dc_principal_name       VARCHAR(200),
    dc_consultant_name      VARCHAR(200),
    dc_assigned_at          TIMESTAMPTZ,
    -- AD status
    ad_version              VARCHAR(50),             -- e.g. 'v1', 'draft', 'presented'
    ad_presented_at         TIMESTAMPTZ,
    -- Metadata
    last_updated_at         TIMESTAMPTZ DEFAULT NOW(),
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approach_doc_deal ON approach_doc(deal_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- DEAL_WORKSTREAMS — Per-deal workstream tracking (one row per deal+workstream)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deal_workstreams (
    id                  SERIAL PRIMARY KEY,
    deal_id             VARCHAR(100) NOT NULL REFERENCES deals(deal_id),
    service_slug        VARCHAR(80) NOT NULL REFERENCES clearwater_services(service_slug),
    confidence          VARCHAR(20) DEFAULT 'inferred',         -- 'inferred' | 'confirmed' | 'rejected'
    scoping_status      VARCHAR(30) DEFAULT 'missing',          -- 'missing' | 'partial' | 'complete'
    scoping_notes       TEXT,
    pricing_status      VARCHAR(30) DEFAULT 'not_requested',    -- 'not_requested' | 'requested' | 'received'
    dc_assigned_name    VARCHAR(200),
    dc_role             VARCHAR(50),                             -- 'principal' | 'consultant'
    first_inferred_at   TIMESTAMPTZ DEFAULT NOW(),
    last_updated_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(deal_id, service_slug)
);

CREATE INDEX IF NOT EXISTS idx_workstreams_deal ON deal_workstreams(deal_id);
CREATE INDEX IF NOT EXISTS idx_workstreams_service ON deal_workstreams(service_slug);
CREATE INDEX IF NOT EXISTS idx_workstreams_pricing ON deal_workstreams(pricing_status);

-- ─────────────────────────────────────────────────────────────────────────────
-- Deals table additions (for hold management)
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE deals ADD COLUMN IF NOT EXISTS hold_until DATE;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS hold_reason TEXT;

-- ─────────────────────────────────────────────────────────────────────────────
-- Deal_health table additions (Phase 5: key objectives + workstream inference)
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE deal_health ADD COLUMN IF NOT EXISTS last_activity_date DATE;
ALTER TABLE deal_health ADD COLUMN IF NOT EXISTS key_objectives_strategic TEXT;
ALTER TABLE deal_health ADD COLUMN IF NOT EXISTS key_objectives_security TEXT;
ALTER TABLE deal_health ADD COLUMN IF NOT EXISTS key_objectives_compliance TEXT;
ALTER TABLE deal_health ADD COLUMN IF NOT EXISTS inferred_workstreams JSONB;     -- array of service_slugs
ALTER TABLE deal_health ADD COLUMN IF NOT EXISTS delivery_staff_on_call JSONB;  -- array of {name, email}

-- ─────────────────────────────────────────────────────────────────────────────
-- Helpful views for Metabase dashboard
-- ─────────────────────────────────────────────────────────────────────────────

-- Latest health score per deal
CREATE OR REPLACE VIEW v_deal_health_latest AS
SELECT DISTINCT ON (deal_id)
    dh.*,
    d.company_name,
    d.salesforce_opp_id,
    d.deal_value_usd,
    d.forecast_category AS deal_forecast
FROM deal_health dh
JOIN deals d ON d.deal_id = dh.deal_id
ORDER BY deal_id, scored_at DESC;

-- Deal health trend (last 30 days)
CREATE OR REPLACE VIEW v_deal_health_trend AS
SELECT
    dh.deal_id,
    d.company_name,
    dh.scored_at::DATE AS score_date,
    dh.p2v2c2_total,
    dh.pain_score, dh.power_score, dh.vision_score,
    dh.value_score, dh.change_score, dh.control_score,
    dh.deal_stage,
    dh.trend_direction
FROM deal_health dh
JOIN deals d ON d.deal_id = dh.deal_id
WHERE dh.scored_at > NOW() - INTERVAL '30 days'
ORDER BY dh.deal_id, dh.scored_at;

-- Latest stakeholder roles per deal (most recent scoring run)
CREATE OR REPLACE VIEW v_deal_stakeholders_latest AS
SELECT DISTINCT ON (deal_id, name)
    deal_id, name, title, email, company, cps_role, role_evidence,
    directly_engaged, success_criteria, scored_at
FROM deal_stakeholders
ORDER BY deal_id, name, scored_at DESC;

-- Pipeline summary
CREATE OR REPLACE VIEW v_pipeline_summary AS
SELECT
    d.deal_stage,
    d.forecast_category,
    COUNT(*) AS deal_count,
    SUM(d.deal_value_usd) AS total_value,
    ROUND(AVG(dh.p2v2c2_total), 1) AS avg_p2v2c2,
    COUNT(CASE WHEN dh.trend_direction = 'declining' THEN 1 END) AS declining_deals
FROM deals d
LEFT JOIN v_deal_health_latest dh ON dh.deal_id = d.deal_id
WHERE d.is_active = TRUE
GROUP BY d.deal_stage, d.forecast_category
ORDER BY d.deal_stage;
