-- Migration: Email Delivery System Tables
-- Description: Create tables for email delivery tracking, workflows, and analytics
-- Version: 008
-- Date: 2024-01-15

-- Email delivery tracking table
CREATE TABLE IF NOT EXISTS email_deliveries (
    email_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    email_address VARCHAR(255) NOT NULL,
    template_name VARCHAR(100) NOT NULL,
    subject TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    sent_at TIMESTAMP NULL,
    delivered_at TIMESTAMP NULL,
    opened_at TIMESTAMP NULL,
    clicked_at TIMESTAMP NULL,
    bounce_reason TEXT NULL,
    metadata JSONB DEFAULT '{}',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email events tracking table
CREATE TABLE IF NOT EXISTS email_events (
    event_id SERIAL PRIMARY KEY,
    email_id VARCHAR(36) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    user_agent TEXT NULL,
    ip_address INET NULL,
    url TEXT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES email_deliveries(email_id) ON DELETE CASCADE
);

-- Workflow executions table
CREATE TABLE IF NOT EXISTS workflow_executions (
    execution_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    report_id VARCHAR(255) NOT NULL,
    purchase_id VARCHAR(255) NOT NULL,
    workflow_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    current_step VARCHAR(100) NULL,
    metadata JSONB DEFAULT '{}'
);

-- Workflow step executions table
CREATE TABLE IF NOT EXISTS workflow_step_executions (
    step_execution_id VARCHAR(36) PRIMARY KEY,
    execution_id VARCHAR(36) NOT NULL,
    step_id VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    scheduled_at TIMESTAMP NOT NULL,
    executed_at TIMESTAMP NULL,
    email_id VARCHAR(36) NULL,
    attempt_count INTEGER DEFAULT 0,
    error_message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (execution_id) REFERENCES workflow_executions(execution_id) ON DELETE CASCADE,
    FOREIGN KEY (email_id) REFERENCES email_deliveries(email_id) ON DELETE SET NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_email_deliveries_user_id ON email_deliveries(user_id);
CREATE INDEX IF NOT EXISTS idx_email_deliveries_status ON email_deliveries(status);
CREATE INDEX IF NOT EXISTS idx_email_deliveries_sent_at ON email_deliveries(sent_at);
CREATE INDEX IF NOT EXISTS idx_email_deliveries_template ON email_deliveries(template_name);

CREATE INDEX IF NOT EXISTS idx_email_events_email_id ON email_events(email_id);
CREATE INDEX IF NOT EXISTS idx_email_events_type ON email_events(event_type);
CREATE INDEX IF NOT EXISTS idx_email_events_timestamp ON email_events(timestamp);

CREATE INDEX IF NOT EXISTS idx_workflow_executions_user_id ON workflow_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow_name ON workflow_executions(workflow_name);

CREATE INDEX IF NOT EXISTS idx_workflow_step_executions_execution_id ON workflow_step_executions(execution_id);
CREATE INDEX IF NOT EXISTS idx_workflow_step_executions_status ON workflow_step_executions(status);
CREATE INDEX IF NOT EXISTS idx_workflow_step_executions_scheduled_at ON workflow_step_executions(scheduled_at);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_email_deliveries_updated_at
    BEFORE UPDATE ON email_deliveries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Email template configurations table (optional)
CREATE TABLE IF NOT EXISTS email_templates (
    template_id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    subject_template TEXT NOT NULL,
    html_template TEXT NOT NULL,
    text_template TEXT NULL,
    category VARCHAR(50) DEFAULT 'general',
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER update_email_templates_updated_at
    BEFORE UPDATE ON email_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default email templates
INSERT INTO email_templates (name, subject_template, html_template, text_template, category) VALUES
('report_delivery',
 'Your {{ report_title }} is ready!',
 '<h1>Your Report is Ready!</h1><p>Dear {{ user_name }},</p><p>Your {{ report_title }} has been generated and is ready for viewing.</p><a href="{{ report_link }}">View Report</a>',
 'Your Report is Ready!\n\nDear {{ user_name }},\n\nYour {{ report_title }} has been generated and is ready for viewing.\n\nView Report: {{ report_link }}',
 'delivery'),

('report_reminder',
 'Don''t forget: Your {{ report_title }} is waiting',
 '<h1>Your Report is Still Waiting</h1><p>Dear {{ user_name }},</p><p>You haven''t accessed your {{ report_title }} yet. Don''t miss out on valuable insights!</p><a href="{{ report_link }}">Access Now</a>',
 'Your Report is Still Waiting\n\nDear {{ user_name }},\n\nYou haven''t accessed your {{ report_title }} yet. Don''t miss out on valuable insights!\n\nAccess Now: {{ report_link }}',
 'reminder'),

('agency_followup',
 'Ready to connect with a growth agency?',
 '<h1>Take Your Growth to the Next Level</h1><p>Dear {{ user_name }},</p><p>Based on your {{ report_title }}, we can connect you with expert agencies to accelerate your growth.</p><a href="{{ agency_cta_link }}">Connect with an Agency</a>',
 'Take Your Growth to the Next Level\n\nDear {{ user_name }},\n\nBased on your {{ report_title }}, we can connect you with expert agencies to accelerate your growth.\n\nConnect with an Agency: {{ agency_cta_link }}',
 'followup')
ON CONFLICT (name) DO NOTHING;

-- Email analytics view for easy reporting
CREATE OR REPLACE VIEW email_analytics AS
SELECT
    DATE_TRUNC('day', ed.sent_at) as date,
    ed.template_name,
    COUNT(*) as total_sent,
    COUNT(CASE WHEN ed.status = 'delivered' THEN 1 END) as delivered,
    COUNT(CASE WHEN ed.status = 'opened' THEN 1 END) as opened,
    COUNT(CASE WHEN ed.status = 'clicked' THEN 1 END) as clicked,
    COUNT(CASE WHEN ed.status = 'bounced' THEN 1 END) as bounced,
    COUNT(CASE WHEN ed.status = 'failed' THEN 1 END) as failed,
    ROUND(
        COUNT(CASE WHEN ed.status = 'delivered' THEN 1 END)::numeric /
        NULLIF(COUNT(*), 0) * 100, 2
    ) as delivery_rate,
    ROUND(
        COUNT(CASE WHEN ed.status = 'opened' THEN 1 END)::numeric /
        NULLIF(COUNT(*), 0) * 100, 2
    ) as open_rate,
    ROUND(
        COUNT(CASE WHEN ed.status = 'clicked' THEN 1 END)::numeric /
        NULLIF(COUNT(*), 0) * 100, 2
    ) as click_rate
FROM email_deliveries ed
WHERE ed.sent_at IS NOT NULL
GROUP BY DATE_TRUNC('day', ed.sent_at), ed.template_name
ORDER BY date DESC, ed.template_name;

-- Workflow analytics view
CREATE OR REPLACE VIEW workflow_analytics AS
SELECT
    DATE_TRUNC('day', we.created_at) as date,
    we.workflow_name,
    COUNT(*) as total_workflows,
    COUNT(CASE WHEN we.status = 'completed' THEN 1 END) as completed,
    COUNT(CASE WHEN we.status = 'active' THEN 1 END) as active,
    COUNT(CASE WHEN we.status = 'failed' THEN 1 END) as failed,
    COUNT(CASE WHEN we.status = 'cancelled' THEN 1 END) as cancelled,
    ROUND(
        COUNT(CASE WHEN we.status = 'completed' THEN 1 END)::numeric /
        NULLIF(COUNT(*), 0) * 100, 2
    ) as completion_rate,
    AVG(
        CASE WHEN we.completed_at IS NOT NULL AND we.started_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (we.completed_at - we.started_at)) / 3600
        END
    ) as avg_duration_hours
FROM workflow_executions we
GROUP BY DATE_TRUNC('day', we.created_at), we.workflow_name
ORDER BY date DESC, we.workflow_name;

-- Comments for documentation
COMMENT ON TABLE email_deliveries IS 'Tracks email delivery status and metadata';
COMMENT ON TABLE email_events IS 'Stores email tracking events from SendGrid webhooks';
COMMENT ON TABLE workflow_executions IS 'Manages automated email workflow executions';
COMMENT ON TABLE workflow_step_executions IS 'Tracks individual workflow step executions';
COMMENT ON TABLE email_templates IS 'Stores email template configurations';
COMMENT ON VIEW email_analytics IS 'Provides aggregated email performance metrics';
COMMENT ON VIEW workflow_analytics IS 'Provides aggregated workflow performance metrics';
