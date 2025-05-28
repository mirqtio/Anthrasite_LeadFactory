-- Migration: Enhance email tracking with delivery metrics and webhook support
-- This enables comprehensive email campaign analytics beyond just "sent" status

-- Step 1: Add new email status values
-- Current: sent, failed
-- New: delivered, bounced, opened, clicked, unsubscribed

-- Step 2: Add webhook tracking fields
ALTER TABLE emails ADD COLUMN delivered_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE emails ADD COLUMN bounced_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE emails ADD COLUMN opened_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE emails ADD COLUMN clicked_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE emails ADD COLUMN unsubscribed_at TIMESTAMP WITH TIME ZONE;

-- Step 3: Add bounce and engagement details
ALTER TABLE emails ADD COLUMN bounce_reason TEXT;
ALTER TABLE emails ADD COLUMN bounce_type VARCHAR(50); -- hard, soft, spam, etc.
ALTER TABLE emails ADD COLUMN click_count INTEGER DEFAULT 0;
ALTER TABLE emails ADD COLUMN open_count INTEGER DEFAULT 0;

-- Step 4: Add SendGrid webhook tracking
ALTER TABLE emails ADD COLUMN webhook_events JSONB; -- Store all webhook events
ALTER TABLE emails ADD COLUMN last_webhook_at TIMESTAMP WITH TIME ZONE;

-- Step 5: Create indexes for performance
CREATE INDEX idx_emails_status ON emails(status);
CREATE INDEX idx_emails_delivered_at ON emails(delivered_at);
CREATE INDEX idx_emails_opened_at ON emails(opened_at);
CREATE INDEX idx_emails_clicked_at ON emails(clicked_at);
CREATE INDEX idx_emails_webhook_events ON emails USING GIN(webhook_events);

-- Step 6: Add constraints for data integrity
ALTER TABLE emails ADD CONSTRAINT chk_email_status
CHECK (status IN ('pending', 'sent', 'delivered', 'bounced', 'opened', 'clicked', 'failed', 'unsubscribed'));

ALTER TABLE emails ADD CONSTRAINT chk_bounce_type
CHECK (bounce_type IS NULL OR bounce_type IN ('hard', 'soft', 'spam', 'reputation', 'content'));

-- Step 7: Add helpful comments
COMMENT ON COLUMN emails.delivered_at IS 'When email was successfully delivered to recipient inbox';
COMMENT ON COLUMN emails.bounced_at IS 'When email bounced (failed delivery)';
COMMENT ON COLUMN emails.opened_at IS 'When email was first opened by recipient';
COMMENT ON COLUMN emails.clicked_at IS 'When email links were first clicked by recipient';
COMMENT ON COLUMN emails.bounce_reason IS 'Detailed reason for email bounce from provider';
COMMENT ON COLUMN emails.webhook_events IS 'JSON array of all webhook events from SendGrid';
COMMENT ON COLUMN emails.click_count IS 'Total number of link clicks in this email';
COMMENT ON COLUMN emails.open_count IS 'Total number of times email was opened';

-- Step 8: Create view for email campaign analytics
CREATE OR REPLACE VIEW email_campaign_metrics AS
SELECT
    DATE_TRUNC('day', sent_at) as campaign_date,
    COUNT(*) as total_sent,
    COUNT(delivered_at) as delivered,
    COUNT(bounced_at) as bounced,
    COUNT(opened_at) as opened,
    COUNT(clicked_at) as clicked,
    COUNT(unsubscribed_at) as unsubscribed,
    ROUND(COUNT(delivered_at) * 100.0 / NULLIF(COUNT(*), 0), 2) as delivery_rate,
    ROUND(COUNT(opened_at) * 100.0 / NULLIF(COUNT(delivered_at), 0), 2) as open_rate,
    ROUND(COUNT(clicked_at) * 100.0 / NULLIF(COUNT(delivered_at), 0), 2) as click_rate,
    ROUND(COUNT(bounced_at) * 100.0 / NULLIF(COUNT(*), 0), 2) as bounce_rate
FROM emails
WHERE sent_at IS NOT NULL
GROUP BY DATE_TRUNC('day', sent_at)
ORDER BY campaign_date DESC;

COMMENT ON VIEW email_campaign_metrics IS 'Daily email campaign performance metrics with delivery, open, and click rates';

-- Step 9: Create function to update email status from webhooks
CREATE OR REPLACE FUNCTION update_email_from_webhook(
    p_sendgrid_message_id TEXT,
    p_event_type TEXT,
    p_timestamp TIMESTAMP WITH TIME ZONE,
    p_event_data JSONB DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    email_record RECORD;
    updated BOOLEAN := FALSE;
BEGIN
    -- Find email by SendGrid message ID
    SELECT id, webhook_events INTO email_record
    FROM emails
    WHERE sendgrid_message_id = p_sendgrid_message_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Update based on event type
    CASE p_event_type
        WHEN 'delivered' THEN
            UPDATE emails SET
                status = 'delivered',
                delivered_at = p_timestamp,
                last_webhook_at = CURRENT_TIMESTAMP
            WHERE id = email_record.id AND delivered_at IS NULL;

        WHEN 'bounce' THEN
            UPDATE emails SET
                status = 'bounced',
                bounced_at = p_timestamp,
                bounce_reason = p_event_data->>'reason',
                bounce_type = p_event_data->>'type',
                last_webhook_at = CURRENT_TIMESTAMP
            WHERE id = email_record.id AND bounced_at IS NULL;

        WHEN 'open' THEN
            UPDATE emails SET
                status = CASE WHEN status IN ('sent', 'delivered') THEN 'opened' ELSE status END,
                opened_at = COALESCE(opened_at, p_timestamp),
                open_count = open_count + 1,
                last_webhook_at = CURRENT_TIMESTAMP
            WHERE id = email_record.id;

        WHEN 'click' THEN
            UPDATE emails SET
                status = 'clicked',
                clicked_at = COALESCE(clicked_at, p_timestamp),
                click_count = click_count + 1,
                last_webhook_at = CURRENT_TIMESTAMP
            WHERE id = email_record.id;

        WHEN 'unsubscribe' THEN
            UPDATE emails SET
                status = 'unsubscribed',
                unsubscribed_at = p_timestamp,
                last_webhook_at = CURRENT_TIMESTAMP
            WHERE id = email_record.id AND unsubscribed_at IS NULL;

        ELSE
            -- Unknown event type, just update webhook data
            NULL;
    END CASE;

    -- Always append webhook event to events array
    UPDATE emails SET
        webhook_events = COALESCE(webhook_events, '[]'::jsonb) ||
                        jsonb_build_object(
                            'event', p_event_type,
                            'timestamp', p_timestamp,
                            'data', p_event_data
                        )
    WHERE id = email_record.id;

    GET DIAGNOSTICS updated = ROW_COUNT;
    RETURN updated > 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_email_from_webhook IS 'Updates email status and metrics based on SendGrid webhook events';
