-- Migration: Add source tracking columns to businesses table
-- Date: 2025-05-27
-- Purpose: Enable metrics collection and source attribution for deduplication

-- Add source and source_id columns to businesses table
ALTER TABLE businesses
ADD COLUMN source TEXT,
ADD COLUMN source_id TEXT;

-- Add index on source for performance
CREATE INDEX idx_businesses_source ON businesses(source);

-- Add index on source_id for lookups
CREATE INDEX idx_businesses_source_id ON businesses(source_id);

-- Add comments for documentation
COMMENT ON COLUMN businesses.source IS 'Data source: yelp, google, manual, etc.';
COMMENT ON COLUMN businesses.source_id IS 'External ID from the source system (e.g., Yelp business ID, Google Place ID)';

-- Update existing businesses to have source = 'unknown' for historical data
UPDATE businesses
SET source = 'unknown'
WHERE source IS NULL;

-- Add constraint to ensure source is not null for new records
ALTER TABLE businesses
ALTER COLUMN source SET DEFAULT 'manual';
