-- ─────────────────────────────────────────────────────────────────────────────
-- Clearwater Deal Intelligence Engine — Deals Table Seed
-- Generated from DDA Intake Report-2026-02-27
-- 26 active deals for Austin Hollins
-- ─────────────────────────────────────────────────────────────────────────────

\c clearwater_deals;

INSERT INTO deals (deal_id, company_name, sender_domains, salesforce_opp_id, salesforce_stage, deal_stage, deal_value_usd, close_date, forecast_category, deal_owner, is_active)
VALUES

-- Advanced Dermatology
('cw_advanceddermatology_2026',
 'Advanced Dermatology',
 ARRAY['advanceddermatologypc.com'],
 '006Nv00000JddWT', 'Discover', 'discover',
 0.00, '2026-06-30', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- American Medical Staffing
('cw_americanmedicalstaffing_2026',
 'American Medical Staffing',
 ARRAY['americanmedicalstaffing.com'],
 '006Nv00000TepUg', 'Negotiate | 4A: Revise DAP w/steps to close', 'negotiate',
 17510.00, '2026-03-17', 'commit', 'austin.holland@clearwatersecurity.com', true),

-- Atlas Clinical Research
('cw_atlasclinicalresearch_2026',
 'Atlas Clinical Research',
 ARRAY['atlas-clinical.com'],
 '006Nv00000P8sZZ', 'Qualify | 2A: Validate current State, Pain, Change', 'qualify',
 58285.00, '2026-04-29', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- Dedicated Sleep
('cw_dedicatedsleep_2026',
 'Dedicated Sleep',
 ARRAY['dedicatedsleep.net'],
 '006Nv00000RWnqs', 'Prove | 3A: Determine Proof Criteria, Co-create', 'prove',
 137850.00, '2026-03-25', 'upside', 'austin.holland@clearwatersecurity.com', true),

-- Ephicacy - ClearAdvantage
('cw_ephicacy_clearadvantage_2026',
 'Ephicacy',
 ARRAY['ephicacy.com'],
 '006Nv00000T447a', 'Discover | 1VO: Champion willing to change', 'discover',
 6500.00, '2026-03-27', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- Ephicacy - SOW #5 Tabletop
('cw_ephicacy_ttx_2026',
 'Ephicacy',
 ARRAY['ephicacy.com'],
 '006Nv00000Sav2r', 'Qualify | 2B: Set expectations for process', 'qualify',
 18375.00, '2026-04-09', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- Exer Urgent Care
('cw_exerurgentcare_2026',
 'Exer Urgent Care',
 ARRAY['exerurgentcare.com'],
 '006Nv00000KPzfx', 'Prove | 3VO: ES agreed to business proposal', 'prove',
 187975.00, '2026-03-18', 'commit', 'austin.holland@clearwatersecurity.com', true),

-- Family Resource Home Care - Network Architecture
('cw_familyresourcehomecare_netarch_2026',
 'Family Resource Home Care',
 ARRAY['familyresourcehomecare.com'],
 '006Nv00000V5oNY', 'Qualify | 2D: Define buying process & prepare DAP', 'qualify',
 64736.00, '2026-04-18', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- Family Resource Home Care - SOW#3 RA/Pen Test
('cw_familyresourcehomecare_sow3_2026',
 'Family Resource Home Care',
 ARRAY['familyresourcehomecare.com'],
 '006Nv00000TOqXs', 'Negotiate | 4C: Exchange red-lines', 'negotiate',
 61495.00, '2026-03-10', 'commit', 'austin.holland@clearwatersecurity.com', true),

-- Family Resource Home Care - SOW#4 CSA
('cw_familyresourcehomecare_sow4_2026',
 'Family Resource Home Care',
 ARRAY['familyresourcehomecare.com'],
 '006Nv00000QWizq', 'Negotiate | 4B: Present MSA/SOW', 'negotiate',
 63215.00, '2026-04-15', 'commit', 'austin.holland@clearwatersecurity.com', true),

-- Fella Health
('cw_fellahealth_2026',
 'Fella Health',
 ARRAY['fellahealth.com', 'joinfella.com'],
 '006Nv00000VspQK', 'Discover | 1D: Champion shares situation', 'discover',
 20000.00, '2026-05-01', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- MedElite
('cw_medelite_2026',
 'MedElite',
 ARRAY['medelitegrp.com'],
 '006Nv00000RMy6C', 'Prove | 3B: Document Approach', 'prove',
 15000.00, '2026-04-18', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- Minaris - CRM Program Development
('cw_minaris_crm_2026',
 'Minaris',
 ARRAY['minaris.com'],
 '006Nv00000MnecM', 'Prove | 3A: Determine Proof Criteria, Co-create', 'prove',
 197835.00, '2026-04-08', 'upside', 'austin.holland@clearwatersecurity.com', true),

-- Minaris Regenerative Medicine - GDPR
('cw_minaris_gdpr_2026',
 'Minaris Regenerative Medicine',
 ARRAY['minaris.com'],
 '006Nv00000QO1Lm', 'Qualify | 2D: Define buying process & prepare DAP', 'qualify',
 23800.00, '2026-04-22', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- Mississippi State University
('cw_mississippistate_2026',
 'Mississippi State University',
 ARRAY['procurement.msstate.edu', 'msstate.edu'],
 '006Nv00000QAZOv', 'Prove | 3A: Determine Proof Criteria, Co-create', 'prove',
 135010.00, '2026-03-13', 'upside', 'austin.holland@clearwatersecurity.com', true),

-- PANTHERx Rare
('cw_pantherxrare_2026',
 'PANTHERx Rare',
 ARRAY['pantherxrare.com'],
 '006Nv00000W2KrT', 'Prove | 3C: Validation Meeting: Present AD', 'prove',
 51465.00, '2026-03-20', 'upside', 'austin.holland@clearwatersecurity.com', true),

-- Paradigm Health
('cw_paradigmhealth_2026',
 'Paradigm Health',
 ARRAY['myparadigmhealth.com'],
 '006Nv00000VIR9t', 'Prove | 3C: Validation Meeting: Present AD', 'prove',
 39005.00, '2026-04-16', 'commit', 'austin.holland@clearwatersecurity.com', true),

-- Partnership HealthPlan of California
('cw_partnershiphp_2026',
 'Partnership HealthPlan of California',
 ARRAY['partnershiphp.org'],
 '006Nv00000UlBoQ', 'Prove | 3VO: ES agreed to business proposal', 'prove',
 121046.00, '2026-04-09', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- Primary Health Partners Oklahoma
('cw_primaryhealthpartners_2026',
 'Primary Health Partners Oklahoma',
 ARRAY['primary-healthpartners.com'],
 '006Nv00000V9b9r', 'Prove | 3A: Determine Proof Criteria, Co-create', 'prove',
 65950.00, '2026-04-15', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- Pyramids Pharmacy
('cw_pyramidspharmacy_2026',
 'Pyramids Pharmacy',
 ARRAY['pyramidspharmacy.com'],
 '006Nv00000UXLkS', 'Close | 5VO: Contracts signed', 'close',
 10500.00, '2026-03-20', 'commit', 'austin.holland@clearwatersecurity.com', true),

-- RISE Services
('cw_riseservices_2026',
 'RISE Services',
 ARRAY['riseservicesinc.org'],
 '006Nv00000Ju5je', 'Prove | 3A: Determine Proof Criteria, Co-create', 'prove',
 85636.00, '2026-04-15', 'upside', 'austin.holland@clearwatersecurity.com', true),

-- Royal Community Support
('cw_royalcommunitysupport_2026',
 'Royal Community Support',
 ARRAY['royalcsnj.com'],
 '006Nv00000W9sgN', 'Qualify | 2VO: ES bought into DAP', 'qualify',
 51465.00, '2026-04-15', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- SCA Pharma
('cw_scapharma_2026',
 'SCA Pharma',
 ARRAY['scapharma.com'],
 '006Nv00000OkWQW', 'Qualify', 'qualify',
 105950.00, '2026-06-18', 'pipeline', 'austin.holland@clearwatersecurity.com', true),

-- St. Croix Hospice
('cw_stcroixhospice_2026',
 'St. Croix Hospice',
 ARRAY['stcroixhospice.com'],
 '006Nv00000Ukb9n', 'Negotiate | 4C: Exchange red-lines', 'negotiate',
 24000.00, '2026-02-27', 'commit', 'austin.holland@clearwatersecurity.com', true),

-- Trustwell Living
('cw_trustwellliving_2026',
 'Trustwell Living',
 ARRAY['trustwellliving.com'],
 '006Nv00000Ulc3l', 'Prove | 3A: Determine Proof Criteria, Co-create', 'prove',
 40000.00, '2026-04-10', 'pipeline', 'austin.holland@clearwatersecurity.com', true)

-- Velentium removed from seed — ingested via live pipeline for clean end-to-end testing

ON CONFLICT (deal_id) DO UPDATE SET
    salesforce_stage  = EXCLUDED.salesforce_stage,
    deal_stage        = EXCLUDED.deal_stage,
    deal_value_usd    = EXCLUDED.deal_value_usd,
    close_date        = EXCLUDED.close_date,
    forecast_category = EXCLUDED.forecast_category,
    updated_at        = NOW();
