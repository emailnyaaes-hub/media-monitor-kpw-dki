-- Skema PostgreSQL untuk produksi.
-- MVP berjalan di SQLite dengan tabel yang sama.
-- Timestamp disimpan dalam WIB tanpa zona waktu.

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    full_name VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL CHECK (role IN ('admin', 'analis', 'pimpinan')),
    password_hash VARCHAR(128) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE issues (
    id SERIAL PRIMARY KEY,
    code VARCHAR(32) UNIQUE NOT NULL,
    title VARCHAR(300) NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    category VARCHAR(64) NOT NULL,
    stance VARCHAR(16) NOT NULL CHECK (stance IN ('upside', 'netral', 'downside')),
    sentiment VARCHAR(16) NOT NULL CHECK (sentiment IN ('positif', 'netral', 'negatif')),
    risk_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    policy_relevance DOUBLE PRECISION NOT NULL DEFAULT 0,
    spread_velocity DOUBLE PRECISION NOT NULL DEFAULT 0,
    impact_level VARCHAR(16) NOT NULL DEFAULT 'sedang',
    status VARCHAR(32) NOT NULL DEFAULT 'baru',
    pic VARCHAR(80) NOT NULL DEFAULT '',
    analyst_note TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMP NOT NULL,
    ai_what TEXT NOT NULL DEFAULT '',
    ai_who TEXT NOT NULL DEFAULT '',
    ai_sentiment TEXT NOT NULL DEFAULT '',
    ai_impact TEXT NOT NULL DEFAULT '',
    ai_recommendation TEXT NOT NULL DEFAULT '',
    policy_tags TEXT NOT NULL DEFAULT '[]',
    is_critical BOOLEAN NOT NULL DEFAULT FALSE,
    is_kpw BOOLEAN NOT NULL DEFAULT FALSE,
    spike_detected BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE mentions (
    id SERIAL PRIMARY KEY,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    source_name VARCHAR(120) NOT NULL,
    source_tier INTEGER NOT NULL DEFAULT 2,
    platform VARCHAR(32) NOT NULL,
    url VARCHAR(400) NOT NULL DEFAULT '',
    author_name VARCHAR(120) NOT NULL DEFAULT '',
    author_handle VARCHAR(120) NOT NULL DEFAULT '',
    published_at TIMESTAMP NOT NULL,
    title VARCHAR(400) NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    language VARCHAR(8) NOT NULL DEFAULT 'id',
    likes INTEGER NOT NULL DEFAULT 0,
    shares INTEGER NOT NULL DEFAULT 0,
    comments INTEGER NOT NULL DEFAULT 0,
    reach_estimate INTEGER NOT NULL DEFAULT 0,
    keyword_matches TEXT NOT NULL DEFAULT '[]',
    sentiment VARCHAR(16) NOT NULL,
    sentiment_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    stance VARCHAR(16) NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    rationale TEXT NOT NULL DEFAULT '',
    category VARCHAR(64) NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    policy_relevance DOUBLE PRECISION NOT NULL DEFAULT 0,
    policy_tags TEXT NOT NULL DEFAULT '[]',
    spread_velocity DOUBLE PRECISION NOT NULL DEFAULT 0,
    impact_level VARCHAR(16) NOT NULL DEFAULT 'sedang',
    credibility INTEGER NOT NULL DEFAULT 60,
    has_public_figure BOOLEAN NOT NULL DEFAULT FALSE,
    needs_verification BOOLEAN NOT NULL DEFAULT FALSE,
    verification_note TEXT NOT NULL DEFAULT '',
    is_kpw BOOLEAN NOT NULL DEFAULT FALSE,
    location VARCHAR(64) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'baru',
    pic VARCHAR(80) NOT NULL DEFAULT '',
    analyst_note TEXT NOT NULL DEFAULT '',
    human_corrected BOOLEAN NOT NULL DEFAULT FALSE,
    quotes_bi BOOLEAN NOT NULL DEFAULT FALSE,
    issue_id INTEGER REFERENCES issues(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_mentions_published_at ON mentions (published_at);
CREATE INDEX ix_mentions_category ON mentions (category);
CREATE INDEX ix_mentions_issue ON mentions (issue_id);

CREATE TABLE blocked_sources (
    id SERIAL PRIMARY KEY,
    kind VARCHAR(16) NOT NULL,
    value VARCHAR(200) NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (kind, value)
);

CREATE TABLE keywords (
    id SERIAL PRIMARY KEY,
    term VARCHAR(160) NOT NULL,
    category VARCHAR(64) NOT NULL,
    mode VARCHAR(16) NOT NULL CHECK (mode IN ('inklusi', 'eksklusi')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (term, mode)
);

CREATE TABLE saved_queries (
    id SERIAL PRIMARY KEY,
    name VARCHAR(160) NOT NULL,
    expression TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE alert_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    rule_type VARCHAR(64) NOT NULL,
    threshold DOUBLE PRECISION NOT NULL DEFAULT 0,
    window_hours INTEGER NOT NULL DEFAULT 24,
    severity VARCHAR(16) NOT NULL,
    keyword VARCHAR(160) NOT NULL DEFAULT '',
    channel VARCHAR(32) NOT NULL DEFAULT 'dashboard',
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES alert_rules(id),
    title VARCHAR(240) NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    severity VARCHAR(16) NOT NULL,
    triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    issue_id INTEGER REFERENCES issues(id)
);

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    actor VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    entity_id VARCHAR(32) NOT NULL,
    old_value TEXT NOT NULL DEFAULT '',
    new_value TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE channel_posts (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(32) NOT NULL,
    title VARCHAR(300) NOT NULL,
    published_at TIMESTAMP NOT NULL,
    reach INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    comments INTEGER NOT NULL DEFAULT 0,
    shares INTEGER NOT NULL DEFAULT 0,
    engagement_rate DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE TABLE connector_runs (
    id SERIAL PRIMARY KEY,
    connector VARCHAR(120) NOT NULL,
    status VARCHAR(32) NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    found INTEGER NOT NULL DEFAULT 0,
    added INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_connector_runs_connector ON connector_runs (connector);

CREATE TABLE app_meta (
    key VARCHAR(64) PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE advices (
    id SERIAL PRIMARY KEY,
    stable_key VARCHAR(160) NOT NULL UNIQUE,
    kind VARCHAR(32) NOT NULL,
    title VARCHAR(300) NOT NULL,
    situation TEXT NOT NULL DEFAULT '',
    who TEXT NOT NULL DEFAULT '',
    recommendation TEXT NOT NULL DEFAULT '',
    channel VARCHAR(160) NOT NULL DEFAULT '',
    urgency VARCHAR(16) NOT NULL DEFAULT 'rendah',
    reason TEXT NOT NULL DEFAULT '',
    impact_follow TEXT NOT NULL DEFAULT '',
    impact_ignore TEXT NOT NULL DEFAULT '',
    alternatives TEXT NOT NULL DEFAULT '[]',
    confidence VARCHAR(16) NOT NULL DEFAULT 'rendah',
    source_count INTEGER NOT NULL DEFAULT 0,
    source_diversity INTEGER NOT NULL DEFAULT 0,
    evidence TEXT NOT NULL DEFAULT '[]',
    facts TEXT NOT NULL DEFAULT '[]',
    inferences TEXT NOT NULL DEFAULT '[]',
    public_voice TEXT NOT NULL DEFAULT '',
    unit VARCHAR(160) NOT NULL DEFAULT 'Kehumasan',
    draft_points TEXT NOT NULL DEFAULT '',
    draft_edited BOOLEAN NOT NULL DEFAULT FALSE,
    needs_verification BOOLEAN NOT NULL DEFAULT FALSE,
    insufficient BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(32) NOT NULL DEFAULT 'baru',
    analyst_note TEXT NOT NULL DEFAULT '',
    useful BOOLEAN,
    feedback_reason TEXT NOT NULL DEFAULT '',
    issue_id INTEGER REFERENCES issues(id),
    category VARCHAR(64) NOT NULL DEFAULT '',
    policy_topic VARCHAR(80) NOT NULL DEFAULT '',
    model_name VARCHAR(80) NOT NULL DEFAULT '',
    prompt_version VARCHAR(32) NOT NULL DEFAULT '',
    evidence_hash VARCHAR(64) NOT NULL DEFAULT '',
    change_note TEXT NOT NULL DEFAULT '',
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE advice_revisions (
    id SERIAL PRIMARY KEY,
    advice_id INTEGER NOT NULL REFERENCES advices(id),
    status VARCHAR(32) NOT NULL,
    urgency VARCHAR(16) NOT NULL DEFAULT '',
    source_count INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_advice_revisions_advice ON advice_revisions (advice_id);

