-- Anthrasite Lead-Factory: Raw HTML Storage Migration
-- Add raw_html_storage table and update businesses table with html_path column

-- Create raw_html_storage table
CREATE TABLE IF NOT EXISTS raw_html_storage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    html_path TEXT NOT NULL,
    original_url TEXT NOT NULL,
    compression_ratio REAL,
    content_hash TEXT,
    size_bytes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    retention_expires_at TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

-- Add html_path column to businesses table if it doesn't exist
ALTER TABLE businesses ADD COLUMN html_path TEXT;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_raw_html_business_id ON raw_html_storage(business_id);
CREATE INDEX IF NOT EXISTS idx_raw_html_retention_expires ON raw_html_storage(retention_expires_at);
CREATE INDEX IF NOT EXISTS idx_businesses_html_path ON businesses(html_path);
