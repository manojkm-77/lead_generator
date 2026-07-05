-- ═══════════════════════════════════════════════════════════════════════════════
-- BUYERHUNTER V2 — PostgreSQL DDL
-- Optimized for 10M+ rows. Partitioned indexes, partial indexes, proper FK chains.
-- ═══════════════════════════════════════════════════════════════════════════════

-- ── Custom Types ──────────────────────────────────────────────────────────────

CREATE TYPE legal_status AS ENUM (
    'active', 'dissolved', 'strike_off', 'liquidation',
    'dormant', 'under_insolvency', 'unknown'
);

CREATE TYPE company_tier AS ENUM (
    'enterprise', 'mid_market', 'small_business', 'micro', 'unknown'
);

CREATE TYPE contact_channel AS ENUM (
    'email', 'phone', 'whatsapp', 'linkedin', 'website_form'
);

CREATE TYPE contact_purpose AS ENUM (
    'official', 'sales', 'procurement', 'support', 'general', 'unknown'
);

CREATE TYPE job_status AS ENUM (
    'pending', 'queued', 'running', 'completed', 'failed',
    'cancelled', 'retrying', 'rate_limited'
);

CREATE TYPE job_priority AS ENUM (
    'critical', 'high', 'normal', 'low'
);

CREATE TYPE evidence_category AS ENUM (
    'scraped_direct', 'scraped_rendered', 'api_response',
    'government_registry', 'manual_entry', 'ai_inferred',
    'user_submitted', 'third_party'
);

-- ── Companies ────────────────────────────────────────────────────────────────

CREATE TABLE companies (
    id              BIGSERIAL PRIMARY KEY,
    canonical_name  TEXT NOT NULL,
    legal_name      TEXT,
    website_url     TEXT,

    -- Legal / registration
    gst_number      VARCHAR(15),
    cin_number      VARCHAR(21),
    iec_code        VARCHAR(10),
    fssai_number    VARCHAR(50),
    pan_number      VARCHAR(10),

    -- Classification
    industry        TEXT,
    sub_industry    TEXT,
    legal_status    legal_status NOT NULL DEFAULT 'unknown',
    company_tier    company_tier NOT NULL DEFAULT 'unknown',

    -- Scoring
    confidence      SMALLINT NOT NULL DEFAULT 0 CHECK (confidence BETWEEN 0 AND 100),
    buyer_score     SMALLINT NOT NULL DEFAULT 0 CHECK (buyer_score BETWEEN 0 AND 100),
    tier            company_tier NOT NULL DEFAULT 'unknown',

    -- Business type flags
    is_manufacturer BOOLEAN NOT NULL DEFAULT FALSE,
    is_importer     BOOLEAN NOT NULL DEFAULT FALSE,
    is_exporter     BOOLEAN NOT NULL DEFAULT FALSE,
    is_distributor  BOOLEAN NOT NULL DEFAULT FALSE,
    is_wholesaler   BOOLEAN NOT NULL DEFAULT FALSE,
    is_retailer     BOOLEAN NOT NULL DEFAULT FALSE,

    -- Physical presence
    hq_country      VARCHAR(5) NOT NULL DEFAULT 'IN',
    hq_state        TEXT,
    hq_city         TEXT,
    hq_district     TEXT,
    hq_pincode      VARCHAR(10),
    hq_address      TEXT,
    factory_address TEXT,
    warehouse_address TEXT,

    -- Geolocation
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,

    -- External identifiers
    google_place_id TEXT,
    linkedin_slug   TEXT,

    -- AI / enrichment metadata
    last_enriched_at TIMESTAMPTZ,
    last_scored_at   TIMESTAMPTZ,

    -- Provenance
    first_seen_source TEXT,
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Timestamps
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Performance indexes for 10M+ rows
CREATE INDEX idx_companies_canonical_name ON companies USING gin (canonical_name gin_trgm_ops);
CREATE INDEX idx_companies_gst ON companies (gst_number) WHERE gst_number IS NOT NULL;
CREATE INDEX idx_companies_cin ON companies (cin_number) WHERE cin_number IS NOT NULL;
CREATE INDEX idx_companies_industry ON companies (industry) WHERE industry IS NOT NULL;
CREATE INDEX idx_companies_state ON companies (hq_state) WHERE hq_state IS NOT NULL;
CREATE INDEX idx_companies_city ON companies (hq_city) WHERE hq_city IS NOT NULL;
CREATE INDEX idx_companies_buyer_score ON companies (buyer_score DESC) WHERE buyer_score > 0;
CREATE INDEX idx_companies_confidence ON companies (confidence DESC) WHERE confidence > 0;
CREATE INDEX idx_companies_tier ON companies (tier) WHERE tier != 'unknown';
CREATE INDEX idx_companies_website ON companies (website_url) WHERE website_url IS NOT NULL;
CREATE INDEX idx_companies_created ON companies (created_at DESC);

-- Partial index for high-value leads
CREATE INDEX idx_companies_high_value ON companies (buyer_score DESC, confidence DESC)
    WHERE buyer_score >= 70 AND confidence >= 50;

-- ── Contacts ─────────────────────────────────────────────────────────────────

CREATE TABLE contacts (
    id              BIGSERIAL PRIMARY KEY,
    company_id      BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- Person info
    person_name     TEXT,
    designation     TEXT,
    department      TEXT,

    -- Contact channel (one row per channel)
    channel         contact_channel NOT NULL,
    channel_value   TEXT NOT NULL,
    channel_purpose contact_purpose NOT NULL DEFAULT 'general',

    -- Quality
    confidence      SMALLINT NOT NULL DEFAULT 50 CHECK (confidence BETWEEN 0 AND 100),
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at     TIMESTAMPTZ,

    -- Provenance
    source_crawl_job_id BIGINT,
    evidence_ledger_id  BIGINT,

    -- Timestamps
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Lookup indexes
CREATE INDEX idx_contacts_company ON contacts (company_id);
CREATE INDEX idx_contacts_channel ON contacts (channel);
CREATE INDEX idx_contacts_channel_value ON contacts (channel_value) WHERE channel_value IS NOT NULL;
CREATE INDEX idx_contacts_department ON contacts (department) WHERE department IS NOT NULL;
CREATE INDEX idx_contacts_confidence ON contacts (confidence DESC);
CREATE UNIQUE INDEX idx_contacts_unique_channel ON contacts (company_id, channel, channel_value);
CREATE INDEX idx_contacts_verified ON contacts (is_verified) WHERE is_verified = TRUE;

-- ── Evidence Ledger ──────────────────────────────────────────────────────────

CREATE TABLE evidence_ledger (
    id              BIGSERIAL PRIMARY KEY,

    -- What was mutated
    entity_type     TEXT NOT NULL,          -- 'company', 'contact', 'lead'
    entity_id       BIGINT NOT NULL,
    field_name      TEXT NOT NULL,          -- 'buyer_score', 'phone', 'industry', etc.
    field_value     TEXT,                   -- the actual value observed

    -- Source provenance
    source_url      TEXT NOT NULL,
    source_domain   TEXT,                   -- extracted domain for grouping
    source_method   evidence_category NOT NULL DEFAULT 'scraped_direct',
    scraper_name    TEXT,                   -- 'indiamart', 'justdial', 'website_enricher', etc.

    -- HTTP provenance
    http_status     SMALLINT,
    http_method     VARCHAR(4) DEFAULT 'GET',
    response_hash   VARCHAR(64),            -- SHA-256 of raw response for dedup

    -- AI provenance (when source_method = 'ai_inferred')
    ai_model        TEXT,
    ai_prompt_hash  VARCHAR(64),
    ai_confidence   SMALLINT CHECK (ai_confidence BETWEEN 0 AND 100),

    -- Timestamps
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Evidence ledger indexes (append-heavy, query by entity)
CREATE INDEX idx_evidence_entity ON evidence_ledger (entity_type, entity_id);
CREATE INDEX idx_evidence_field ON evidence_ledger (entity_type, entity_id, field_name);
CREATE INDEX idx_evidence_source_domain ON evidence_ledger (source_domain) WHERE source_domain IS NOT NULL;
CREATE INDEX idx_evidence_scraper ON evidence_ledger (scraper_name) WHERE scraper_name IS NOT NULL;
CREATE INDEX idx_evidence_observed ON evidence_ledger (observed_at DESC);
CREATE INDEX idx_evidence_method ON evidence_ledger (source_method);

-- Partial index for AI-inferred evidence
CREATE INDEX idx_evidence_ai ON evidence_ledger (ai_model, ai_confidence DESC)
    WHERE source_method = 'ai_inferred';

-- ── Search Jobs ──────────────────────────────────────────────────────────────

CREATE TABLE search_jobs (
    id              BIGSERIAL PRIMARY KEY,

    -- Query
    query_string    TEXT NOT NULL,
    query_hash      VARCHAR(64),            -- normalized hash for dedup

    -- Source
    source          TEXT NOT NULL,          -- 'indiamart', 'justdial', 'google_maps', etc.
    source_url      TEXT,                   -- the actual search URL constructed

    -- Lifecycle
    status          job_status NOT NULL DEFAULT 'pending',
    priority        job_priority NOT NULL DEFAULT 'normal',
    retry_count     SMALLINT NOT NULL DEFAULT 0,
    max_retries     SMALLINT NOT NULL DEFAULT 3,
    max_pages       SMALLINT NOT NULL DEFAULT 5,

    -- Result tracking
    pages_crawled   INTEGER NOT NULL DEFAULT 0,
    companies_found INTEGER NOT NULL DEFAULT 0,
    contacts_found  INTEGER NOT NULL DEFAULT 0,
    errors          JSONB DEFAULT '[]'::jsonb,

    -- Geography
    target_state    TEXT,
    target_city     TEXT,
    target_country  VARCHAR(5) NOT NULL DEFAULT 'IN',

    -- Parent relationship (for sub-jobs from expansion)
    parent_job_id   BIGINT REFERENCES search_jobs(id) ON DELETE SET NULL,
    run_id          VARCHAR(64),            -- groups jobs from same pipeline run

    -- Scheduling
    scheduled_at    TIMESTAMPTZ,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,

    -- Timestamps
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Job queue indexes (optimized for dequeue pattern: pending + priority + created)
CREATE INDEX idx_jobs_pending ON search_jobs (priority, created_at)
    WHERE status IN ('pending', 'queued');
CREATE INDEX idx_jobs_running ON search_jobs (started_at)
    WHERE status = 'running';
CREATE INDEX idx_jobs_status ON search_jobs (status);
CREATE INDEX idx_jobs_source ON search_jobs (source);
CREATE INDEX idx_jobs_run ON search_jobs (run_id) WHERE run_id IS NOT NULL;
CREATE INDEX idx_jobs_parent ON search_jobs (parent_job_id) WHERE parent_job_id IS NOT NULL;
CREATE INDEX idx_jobs_query_hash ON search_jobs (query_hash) WHERE query_hash IS NOT NULL;
CREATE INDEX idx_jobs_created ON search_jobs (created_at DESC);
CREATE INDEX idx_jobs_retry ON search_jobs (retry_count, status)
    WHERE status = 'failed';

-- Unique constraint: no duplicate active jobs for same query+source
CREATE UNIQUE INDEX idx_jobs_no_dup_active ON search_jobs (query_hash, source)
    WHERE status IN ('pending', 'queued', 'running');

-- ── Trigger: auto-update updated_at ──────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_companies_updated
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_contacts_updated
    BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_jobs_updated
    BEFORE UPDATE ON search_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
