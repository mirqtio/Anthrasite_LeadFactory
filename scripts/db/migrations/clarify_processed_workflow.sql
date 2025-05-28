-- Migration: Clarify processed workflow and business lifecycle
-- This addresses the confusion around processed=false while emails are being sent

-- Step 1: Add comprehensive comments to clarify the business lifecycle
COMMENT ON COLUMN businesses.status IS 'Business lead status: pending (new lead), contacted (email sent), qualified (responded positively), converted (became customer), rejected (not interested)';
COMMENT ON COLUMN businesses.processed IS 'Whether business has completed the full lead qualification workflow (email sent + response evaluated)';

-- Step 2: Add new status values to better track the workflow
ALTER TABLE businesses DROP CONSTRAINT IF EXISTS chk_business_status;
ALTER TABLE businesses ADD CONSTRAINT chk_business_status
CHECK (status IN ('pending', 'contacted', 'qualified', 'converted', 'rejected', 'unqualified'));

-- Step 3: Create a proper workflow state machine
-- Current issue: emails sent to processed=false businesses
-- Solution: processed should only be true AFTER the full workflow is complete

-- Step 4: Add workflow tracking fields
ALTER TABLE businesses ADD COLUMN first_contact_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE businesses ADD COLUMN last_contact_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE businesses ADD COLUMN contact_attempts INTEGER DEFAULT 0;
ALTER TABLE businesses ADD COLUMN qualification_notes TEXT;
ALTER TABLE businesses ADD COLUMN qualified_at TIMESTAMP WITH TIME ZONE;

-- Step 5: Create indexes for workflow queries
CREATE INDEX idx_businesses_status ON businesses(status);
CREATE INDEX idx_businesses_processed ON businesses(processed);
CREATE INDEX idx_businesses_first_contact ON businesses(first_contact_at);

-- Step 6: Create function to update business workflow status
CREATE OR REPLACE FUNCTION update_business_workflow(
    p_business_id INTEGER,
    p_event_type TEXT,
    p_notes TEXT DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    current_status TEXT;
    updated BOOLEAN := FALSE;
BEGIN
    -- Get current status
    SELECT status INTO current_status FROM businesses WHERE id = p_business_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Update based on event type
    CASE p_event_type
        WHEN 'email_sent' THEN
            UPDATE businesses SET
                status = CASE WHEN status = 'pending' THEN 'contacted' ELSE status END,
                first_contact_at = COALESCE(first_contact_at, CURRENT_TIMESTAMP),
                last_contact_at = CURRENT_TIMESTAMP,
                contact_attempts = contact_attempts + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = p_business_id;

        WHEN 'positive_response' THEN
            UPDATE businesses SET
                status = 'qualified',
                qualified_at = CURRENT_TIMESTAMP,
                qualification_notes = p_notes,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = p_business_id;

        WHEN 'negative_response' THEN
            UPDATE businesses SET
                status = 'rejected',
                processed = TRUE, -- Mark as processed since we have final answer
                qualification_notes = p_notes,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = p_business_id;

        WHEN 'converted' THEN
            UPDATE businesses SET
                status = 'converted',
                processed = TRUE, -- Mark as processed since they became customer
                qualification_notes = p_notes,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = p_business_id;

        WHEN 'no_response_final' THEN
            UPDATE businesses SET
                status = 'unqualified',
                processed = TRUE, -- Mark as processed since we've exhausted attempts
                qualification_notes = COALESCE(p_notes, 'No response after multiple contact attempts'),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = p_business_id;

        ELSE
            RETURN FALSE;
    END CASE;

    GET DIAGNOSTICS updated = ROW_COUNT;
    RETURN updated > 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_business_workflow IS 'Updates business workflow status based on lead qualification events';

-- Step 7: Create view for workflow analytics
CREATE OR REPLACE VIEW business_workflow_metrics AS
SELECT
    status,
    processed,
    COUNT(*) as business_count,
    COUNT(first_contact_at) as contacted_count,
    AVG(contact_attempts) as avg_contact_attempts,
    COUNT(qualified_at) as qualified_count,
    ROUND(COUNT(qualified_at) * 100.0 / NULLIF(COUNT(first_contact_at), 0), 2) as qualification_rate
FROM businesses
GROUP BY status, processed
ORDER BY
    CASE status
        WHEN 'pending' THEN 1
        WHEN 'contacted' THEN 2
        WHEN 'qualified' THEN 3
        WHEN 'converted' THEN 4
        WHEN 'rejected' THEN 5
        WHEN 'unqualified' THEN 6
    END;

COMMENT ON VIEW business_workflow_metrics IS 'Business lead workflow performance metrics and conversion rates';

-- Step 8: Update existing data to fix current inconsistencies
-- Businesses with emails should be marked as 'contacted' not 'pending'
UPDATE businesses
SET
    status = 'contacted',
    first_contact_at = (
        SELECT MIN(sent_at)
        FROM emails e
        WHERE e.business_id = businesses.id
        AND e.status = 'sent'
    ),
    last_contact_at = (
        SELECT MAX(sent_at)
        FROM emails e
        WHERE e.business_id = businesses.id
        AND e.status = 'sent'
    ),
    contact_attempts = (
        SELECT COUNT(*)
        FROM emails e
        WHERE e.business_id = businesses.id
        AND e.status = 'sent'
    )
WHERE status = 'pending'
AND id IN (
    SELECT DISTINCT business_id
    FROM emails
    WHERE status = 'sent'
);

-- Step 9: Add trigger to automatically update workflow on email send
CREATE OR REPLACE FUNCTION trigger_update_business_on_email()
RETURNS TRIGGER AS $$
BEGIN
    -- When an email is marked as sent, update business workflow
    IF NEW.status = 'sent' AND (OLD.status IS NULL OR OLD.status != 'sent') THEN
        PERFORM update_business_workflow(NEW.business_id, 'email_sent');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_business_on_email_sent
    AFTER UPDATE OF status ON emails
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_business_on_email();

COMMENT ON TRIGGER trg_update_business_on_email_sent ON emails IS 'Automatically updates business workflow when emails are sent';
