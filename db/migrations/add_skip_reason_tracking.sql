-- Add skip_reason tracking for businesses that don't meet thresholds
-- This helps track why businesses were skipped in the pipeline

-- Add skip_reason column to processing_status table
ALTER TABLE processing_status 
ADD COLUMN IF NOT EXISTS skip_reason TEXT;

-- Create index for finding skipped businesses
CREATE INDEX IF NOT EXISTS idx_processing_status_skip_reason 
ON processing_status(stage, status) 
WHERE skip_reason IS NOT NULL;

-- Add audit_score column to businesses table for quick filtering
ALTER TABLE businesses
ADD COLUMN IF NOT EXISTS audit_score INTEGER DEFAULT NULL;

-- Create index for score-based queries
CREATE INDEX IF NOT EXISTS idx_businesses_audit_score 
ON businesses(audit_score) 
WHERE audit_score IS NOT NULL;

-- Update function to sync scores from stage_results to businesses table
CREATE OR REPLACE FUNCTION sync_audit_scores() RETURNS void AS $$
BEGIN
    UPDATE businesses b
    SET audit_score = (sr.results->>'score')::int
    FROM stage_results sr
    WHERE b.id = sr.business_id 
    AND sr.stage = 'score'
    AND sr.results ? 'score';
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update audit_score when stage_results is updated
CREATE OR REPLACE FUNCTION update_audit_score_trigger() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.stage = 'score' AND NEW.results ? 'score' THEN
        UPDATE businesses 
        SET audit_score = (NEW.results->>'score')::int
        WHERE id = NEW.business_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_audit_score_on_stage_results ON stage_results;
CREATE TRIGGER update_audit_score_on_stage_results
AFTER INSERT OR UPDATE ON stage_results
FOR EACH ROW
EXECUTE FUNCTION update_audit_score_trigger();

-- Run initial sync of existing scores
SELECT sync_audit_scores();

-- Add comment explaining the fields
COMMENT ON COLUMN processing_status.skip_reason IS 'Reason why this business was skipped at this stage (e.g., "Score below audit threshold: 45 < 60")';
COMMENT ON COLUMN businesses.audit_score IS 'Cached audit score from scoring stage for quick filtering';