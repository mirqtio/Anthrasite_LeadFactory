-- Migration: Add JSON retention policy to businesses table
-- Date: 2025-06-05
-- Purpose: Track when Yelp/Google JSON responses should be purged for PII compliance

-- Add retention expiry column with 90-day default
ALTER TABLE businesses 
ADD COLUMN IF NOT EXISTS json_retention_expires_at TIMESTAMP WITH TIME ZONE 
DEFAULT (CURRENT_TIMESTAMP + INTERVAL '90 days');

-- Update existing records to have retention date 90 days from now
-- This gives us time to implement the cleanup process
UPDATE businesses 
SET json_retention_expires_at = CURRENT_TIMESTAMP + INTERVAL '90 days'
WHERE (yelp_response_json IS NOT NULL OR google_response_json IS NOT NULL)
AND json_retention_expires_at IS NULL;

-- Create index for efficient cleanup queries
CREATE INDEX IF NOT EXISTS idx_businesses_json_retention 
ON businesses(json_retention_expires_at) 
WHERE json_retention_expires_at IS NOT NULL;

-- Add comment explaining the field
COMMENT ON COLUMN businesses.json_retention_expires_at IS 
'Timestamp when JSON response data should be purged for PII compliance. NULL means already purged.';