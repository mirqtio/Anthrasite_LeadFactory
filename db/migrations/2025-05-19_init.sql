-- Anthrasite Lead-Factory Phase 0
-- Initial Database Schema Migration
-- 2025-05-19

-- Enable WAL mode for better performance and durability
PRAGMA journal_mode = WAL;

-- Create zip_queue table for tracking which zip codes to process
CREATE TABLE IF NOT EXISTS zip_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zip TEXT NOT NULL,
    metro TEXT NOT NULL,
    done BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(zip)
);

-- Create verticals table for tracking business categories
CREATE TABLE IF NOT EXISTS verticals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    alias TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(alias)
);

-- Create businesses table for storing lead information
CREATE TABLE IF NOT EXISTS businesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT,
    zip TEXT NOT NULL,
    category TEXT NOT NULL,
    website TEXT,
    email TEXT,
    phone TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    score INTEGER DEFAULT 0,
    tier INTEGER DEFAULT 1,
    source TEXT NOT NULL,  -- 'yelp' or 'google'
    source_id TEXT,        -- ID from source platform
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create features table for storing tech stack and performance metrics
CREATE TABLE IF NOT EXISTS features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    tech_stack TEXT,       -- JSON array of technologies
    page_speed INTEGER,    -- Core Web Vitals score
    screenshot_url TEXT,   -- URL to screenshot (Tier 2+)
    semrush_json TEXT,     -- SEMrush Site Audit data (Tier 3 only)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

-- Create mockups table for storing generated mockups
CREATE TABLE IF NOT EXISTS mockups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    mockup_md TEXT,        -- Markdown content of mockup
    mockup_png TEXT,       -- URL to PNG in Supabase Storage
    prompt_used TEXT,      -- Prompt used to generate mockup
    model_used TEXT,       -- Model used (GPT-4o or Claude)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

-- Create emails table for tracking outreach
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    variant_id TEXT NOT NULL,  -- A/B test variant
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    sent_at TIMESTAMP,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'queued',  -- queued, sent, bounced, opened, replied
    sendgrid_id TEXT,
    ip_pool TEXT NOT NULL DEFAULT 'shared',  -- shared or dedicated
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

-- Create cost_tracking table for budget monitoring
CREATE TABLE IF NOT EXISTS cost_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,  -- api_name (yelp, google, semrush, etc.)
    operation TEXT NOT NULL,  -- operation type
    cost_cents INTEGER NOT NULL,
    tier INTEGER NOT NULL,
    business_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE SET NULL
);

-- Create a view for candidate duplicate pairs based on email
CREATE VIEW IF NOT EXISTS candidate_pairs_email AS
SELECT 
    b1.id as id1, 
    b2.id as id2,
    b1.email as email
FROM 
    businesses b1
JOIN 
    businesses b2 ON b1.email = b2.email AND b1.id < b2.id
WHERE 
    b1.active = TRUE AND b2.active = TRUE AND b1.email IS NOT NULL;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_businesses_zip ON businesses(zip);
CREATE INDEX IF NOT EXISTS idx_businesses_category ON businesses(category);
CREATE INDEX IF NOT EXISTS idx_businesses_email ON businesses(email);
CREATE INDEX IF NOT EXISTS idx_businesses_phone ON businesses(phone);
CREATE INDEX IF NOT EXISTS idx_businesses_active ON businesses(active);
CREATE INDEX IF NOT EXISTS idx_businesses_score ON businesses(score);
CREATE INDEX IF NOT EXISTS idx_features_business_id ON features(business_id);
CREATE INDEX IF NOT EXISTS idx_emails_business_id ON emails(business_id);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
CREATE INDEX IF NOT EXISTS idx_cost_tracking_service ON cost_tracking(service);
CREATE INDEX IF NOT EXISTS idx_cost_tracking_tier ON cost_tracking(tier);

-- Create trigger to update updated_at timestamp on businesses
CREATE TRIGGER IF NOT EXISTS update_businesses_timestamp 
AFTER UPDATE ON businesses
BEGIN
    UPDATE businesses SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Create trigger to update updated_at timestamp on features
CREATE TRIGGER IF NOT EXISTS update_features_timestamp 
AFTER UPDATE ON features
BEGIN
    UPDATE features SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Function to calculate Levenshtein distance for name+phone fuzzy matching
-- This will be implemented in Python code since SQLite doesn't natively support it
-- The view below will be used as a reference for the Python implementation

-- Create a view for high-score businesses ready for mockup generation
CREATE VIEW IF NOT EXISTS high_score_businesses AS
SELECT 
    b.id, 
    b.name, 
    b.website, 
    b.email, 
    b.score,
    b.tier,
    f.tech_stack
FROM 
    businesses b
LEFT JOIN 
    features f ON b.id = f.business_id
WHERE 
    b.active = TRUE 
    AND b.score > 50
    AND b.website IS NOT NULL
    AND f.tech_stack IS NOT NULL
ORDER BY 
    b.score DESC;

-- Create a view for email-ready businesses
CREATE VIEW IF NOT EXISTS email_ready_businesses AS
SELECT 
    b.id, 
    b.name, 
    b.email, 
    b.tier,
    m.mockup_png
FROM 
    businesses b
LEFT JOIN 
    mockups m ON b.id = m.business_id
WHERE 
    b.active = TRUE 
    AND b.email IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM emails e WHERE e.business_id = b.id)
    AND (b.tier = 1 OR (b.tier > 1 AND m.mockup_png IS NOT NULL));