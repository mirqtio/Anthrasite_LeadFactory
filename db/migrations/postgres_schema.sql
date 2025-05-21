-- Anthrasite Lead-Factory: PostgreSQL Schema
-- This file contains the schema for the PostgreSQL database.

-- Businesses table
CREATE TABLE IF NOT EXISTS businesses (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    category TEXT,
    source TEXT,
    source_id TEXT,
    status TEXT DEFAULT 'pending',
    score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Features table
CREATE TABLE IF NOT EXISTS features (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
    tech_stack JSONB,
    social_profiles JSONB,
    business_type TEXT,
    employee_count INTEGER,
    annual_revenue NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Mockups table
CREATE TABLE IF NOT EXISTS mockups (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
    image_url TEXT,
    html_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Emails table
CREATE TABLE IF NOT EXISTS emails (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
    subject TEXT,
    body_html TEXT,
    body_text TEXT,
    status TEXT DEFAULT 'pending',
    sent_at TIMESTAMP,
    message_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Candidate duplicate pairs table
CREATE TABLE IF NOT EXISTS candidate_duplicate_pairs (
    id SERIAL PRIMARY KEY,
    business_id_1 INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
    business_id_2 INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
    similarity_score NUMERIC,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_pair UNIQUE (business_id_1, business_id_2)
);

-- Business merges table
CREATE TABLE IF NOT EXISTS business_merges (
    id SERIAL PRIMARY KEY,
    source_business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
    target_business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
    merged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Zip queue table
CREATE TABLE IF NOT EXISTS zip_queue (
    id SERIAL PRIMARY KEY,
    zip TEXT NOT NULL UNIQUE,
    priority INTEGER DEFAULT 0,
    done BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Verticals table
CREATE TABLE IF NOT EXISTS verticals (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cost tracking table
CREATE TABLE IF NOT EXISTS cost_tracking (
    id SERIAL PRIMARY KEY,
    service TEXT NOT NULL,
    cost NUMERIC NOT NULL,
    date DATE NOT NULL,
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email metrics table
CREATE TABLE IF NOT EXISTS email_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    sent INTEGER DEFAULT 0,
    delivered INTEGER DEFAULT 0,
    opened INTEGER DEFAULT 0,
    clicked INTEGER DEFAULT 0,
    bounced INTEGER DEFAULT 0,
    spam_reports INTEGER DEFAULT 0,
    unsubscribes INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Unsubscribes table for CAN-SPAM compliance
CREATE TABLE IF NOT EXISTS unsubscribes (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    reason TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_businesses_name ON businesses(name);
CREATE INDEX IF NOT EXISTS idx_businesses_zip ON businesses(zip);
CREATE INDEX IF NOT EXISTS idx_businesses_status ON businesses(status);
CREATE INDEX IF NOT EXISTS idx_businesses_score ON businesses(score);
CREATE INDEX IF NOT EXISTS idx_features_business_id ON features(business_id);
CREATE INDEX IF NOT EXISTS idx_mockups_business_id ON mockups(business_id);
CREATE INDEX IF NOT EXISTS idx_emails_business_id ON emails(business_id);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
CREATE INDEX IF NOT EXISTS idx_candidate_duplicate_pairs_status ON candidate_duplicate_pairs(status);
CREATE INDEX IF NOT EXISTS idx_zip_queue_done ON zip_queue(done);
CREATE INDEX IF NOT EXISTS idx_cost_tracking_service ON cost_tracking(service);
CREATE INDEX IF NOT EXISTS idx_cost_tracking_date ON cost_tracking(date);
CREATE INDEX IF NOT EXISTS idx_email_metrics_date ON email_metrics(date);
CREATE INDEX IF NOT EXISTS idx_unsubscribes_email ON unsubscribes(email);
