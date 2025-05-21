-- Anthrasite Lead-Factory: Unsubscribe Table Migration
-- This migration adds the unsubscribes table for CAN-SPAM compliance.

-- Create unsubscribes table
CREATE TABLE IF NOT EXISTS unsubscribes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    reason TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_unsubscribes_email ON unsubscribes(email);
