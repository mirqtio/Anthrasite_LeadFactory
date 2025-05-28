-- Migration: Add JSON response storage for API data
-- This stores raw API responses for debugging, data recovery, and future analysis

-- Add columns to store raw JSON responses from APIs
ALTER TABLE businesses
ADD COLUMN yelp_response_json JSONB,
ADD COLUMN google_response_json JSONB;

-- Add indexes for JSON querying performance
CREATE INDEX idx_businesses_yelp_json ON businesses USING GIN (yelp_response_json);
CREATE INDEX idx_businesses_google_json ON businesses USING GIN (google_response_json);

-- Add comments for documentation
COMMENT ON COLUMN businesses.yelp_response_json IS 'Raw JSON response from Yelp API for this business';
COMMENT ON COLUMN businesses.google_response_json IS 'Raw JSON response from Google Places API for this business';
