-- Initialize the schema for E2E testing
-- Basic structure matching the application's expected schema

-- Businesses table to store lead information
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
    vertical TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    processed BOOLEAN DEFAULT FALSE
);

-- Emails table to track email delivery
CREATE TABLE IF NOT EXISTS emails (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES businesses(id),
    to_email TEXT NOT NULL,
    template TEXT NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    sendgrid_message_id TEXT,
    sendgrid_response_code INTEGER
);

-- LLM logs for AI operations
CREATE TABLE IF NOT EXISTS llm_logs (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES businesses(id),
    operation TEXT NOT NULL,
    prompt TEXT,
    completion TEXT,
    tokens INTEGER,
    cost FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ZIP code queue for business scraping
CREATE TABLE IF NOT EXISTS zip_queue (
    id SERIAL PRIMARY KEY,
    zip TEXT NOT NULL UNIQUE,
    city TEXT,
    state TEXT,
    processed BOOLEAN DEFAULT FALSE,
    last_processed TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Verticals table for business categories
CREATE TABLE IF NOT EXISTS verticals (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Assets table to track generated screenshots and mockups
CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES businesses(id),
    asset_type TEXT NOT NULL, -- 'screenshot', 'mockup', etc.
    file_path TEXT NOT NULL,
    url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_businesses_status ON businesses(status);
CREATE INDEX IF NOT EXISTS idx_businesses_processed ON businesses(processed);
CREATE INDEX IF NOT EXISTS idx_zip_queue_processed ON zip_queue(processed);
CREATE INDEX IF NOT EXISTS idx_emails_business_id ON emails(business_id);
CREATE INDEX IF NOT EXISTS idx_assets_business_id ON assets(business_id);
