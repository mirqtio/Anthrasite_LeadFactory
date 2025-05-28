-- Create tables for deduplication functionality

-- Table to log dedupe operations
CREATE TABLE IF NOT EXISTS dedupe_log (
    id SERIAL PRIMARY KEY,
    primary_id INTEGER NOT NULL REFERENCES businesses(id),
    secondary_id INTEGER NOT NULL,
    merge_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Table for manual review queue
CREATE TABLE IF NOT EXISTS review_queue (
    id SERIAL PRIMARY KEY,
    business1_id INTEGER NOT NULL REFERENCES businesses(id),
    business2_id INTEGER NOT NULL REFERENCES businesses(id),
    reason TEXT NOT NULL,
    similarity_score FLOAT,
    reviewed BOOLEAN DEFAULT FALSE,
    review_decision VARCHAR(50), -- 'merge', 'keep_separate', 'needs_more_info'
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_dedupe_log_primary_id ON dedupe_log(primary_id);
CREATE INDEX IF NOT EXISTS idx_dedupe_log_secondary_id ON dedupe_log(secondary_id);
CREATE INDEX IF NOT EXISTS idx_dedupe_log_timestamp ON dedupe_log(merge_timestamp);

CREATE INDEX IF NOT EXISTS idx_review_queue_business1 ON review_queue(business1_id);
CREATE INDEX IF NOT EXISTS idx_review_queue_business2 ON review_queue(business2_id);
CREATE INDEX IF NOT EXISTS idx_review_queue_reviewed ON review_queue(reviewed);
CREATE INDEX IF NOT EXISTS idx_review_queue_created ON review_queue(created_at);

-- Add Levenshtein extension if not exists (for PostgreSQL)
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
