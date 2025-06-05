-- Add city and state columns to businesses table
-- This migration adds city and state fields to properly store parsed address components

-- Add city column
ALTER TABLE businesses ADD COLUMN city TEXT;

-- Add state column
ALTER TABLE businesses ADD COLUMN state TEXT;

-- Create indexes for better query performance on city/state lookups
CREATE INDEX idx_businesses_city ON businesses(city);
CREATE INDEX idx_businesses_state ON businesses(state);
CREATE INDEX idx_businesses_city_state ON businesses(city, state);
