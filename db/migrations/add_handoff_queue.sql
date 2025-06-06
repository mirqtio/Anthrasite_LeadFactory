-- Feature 5 Extension: TR-4 Bulk Qualify for Handoff
-- Add handoff queue tables for sales team lead management

-- Handoff qualification criteria table
CREATE TABLE IF NOT EXISTS handoff_qualification_criteria (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    min_score INTEGER DEFAULT 0,
    max_score INTEGER,
    required_fields JSONB DEFAULT '[]',  -- List of required business fields
    engagement_requirements JSONB DEFAULT '{}',  -- Engagement tracking requirements
    custom_rules JSONB DEFAULT '{}',  -- Custom qualification rules
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Handoff queue table
CREATE TABLE IF NOT EXISTS handoff_queue (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
    qualification_criteria_id INTEGER REFERENCES handoff_qualification_criteria(id),
    status TEXT DEFAULT 'qualified',  -- qualified, assigned, contacted, closed, rejected
    priority INTEGER DEFAULT 50,  -- 1-100 priority score
    qualification_score INTEGER DEFAULT 0,
    qualification_details JSONB DEFAULT '{}',  -- Detailed qualification analysis
    assigned_to TEXT,  -- Sales rep identifier
    assigned_at TIMESTAMP,
    contacted_at TIMESTAMP,
    closed_at TIMESTAMP,
    closure_reason TEXT,
    notes TEXT,
    engagement_summary JSONB DEFAULT '{}',  -- Summary from engagement analytics
    source_campaign_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Handoff queue history for tracking changes
CREATE TABLE IF NOT EXISTS handoff_queue_history (
    id SERIAL PRIMARY KEY,
    handoff_queue_id INTEGER REFERENCES handoff_queue(id) ON DELETE CASCADE,
    old_status TEXT,
    new_status TEXT,
    old_assigned_to TEXT,
    new_assigned_to TEXT,
    changed_by TEXT,
    change_reason TEXT,
    change_details JSONB DEFAULT '{}',
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bulk qualification operations for audit trail
CREATE TABLE IF NOT EXISTS bulk_qualification_operations (
    id SERIAL PRIMARY KEY,
    operation_id TEXT UNIQUE NOT NULL,
    operation_type TEXT NOT NULL,  -- qualify, reject, assign, etc.
    criteria_id INTEGER REFERENCES handoff_qualification_criteria(id),
    business_ids INTEGER[],  -- Array of business IDs processed
    total_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    operation_details JSONB DEFAULT '{}',
    performed_by TEXT,
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT DEFAULT 'in_progress'  -- in_progress, completed, failed
);

-- Sales team member configuration
CREATE TABLE IF NOT EXISTS sales_team_members (
    id SERIAL PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT DEFAULT 'sales_rep',  -- sales_rep, sales_manager, team_lead
    specialties JSONB DEFAULT '[]',  -- Business categories/verticals they specialize in
    max_capacity INTEGER DEFAULT 50,  -- Maximum concurrent leads
    current_capacity INTEGER DEFAULT 0,  -- Current assigned leads
    is_active BOOLEAN DEFAULT TRUE,
    timezone TEXT DEFAULT 'UTC',
    working_hours JSONB DEFAULT '{"start": "09:00", "end": "17:00"}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_handoff_queue_status ON handoff_queue(status);
CREATE INDEX IF NOT EXISTS idx_handoff_queue_priority ON handoff_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_handoff_queue_business_id ON handoff_queue(business_id);
CREATE INDEX IF NOT EXISTS idx_handoff_queue_assigned_to ON handoff_queue(assigned_to);
CREATE INDEX IF NOT EXISTS idx_handoff_queue_created_at ON handoff_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_handoff_queue_qualification_score ON handoff_queue(qualification_score DESC);

CREATE INDEX IF NOT EXISTS idx_handoff_queue_history_handoff_queue_id ON handoff_queue_history(handoff_queue_id);
CREATE INDEX IF NOT EXISTS idx_handoff_queue_history_changed_at ON handoff_queue_history(changed_at);

CREATE INDEX IF NOT EXISTS idx_bulk_qualification_operations_operation_id ON bulk_qualification_operations(operation_id);
CREATE INDEX IF NOT EXISTS idx_bulk_qualification_operations_status ON bulk_qualification_operations(status);
CREATE INDEX IF NOT EXISTS idx_bulk_qualification_operations_performed_at ON bulk_qualification_operations(performed_at);

CREATE INDEX IF NOT EXISTS idx_sales_team_members_user_id ON sales_team_members(user_id);
CREATE INDEX IF NOT EXISTS idx_sales_team_members_email ON sales_team_members(email);
CREATE INDEX IF NOT EXISTS idx_sales_team_members_is_active ON sales_team_members(is_active);

-- Insert default qualification criteria
INSERT INTO handoff_qualification_criteria (name, description, min_score, required_fields, engagement_requirements, custom_rules)
VALUES
    (
        'Basic Lead Qualification',
        'Basic qualification for general sales follow-up',
        50,
        '["name", "email", "website"]',
        '{"min_page_views": 2, "min_session_duration": 30}',
        '{"has_website": true, "min_business_score": 50}'
    ),
    (
        'High-Value Prospect',
        'High-value prospects for senior sales team',
        80,
        '["name", "email", "website", "phone", "address"]',
        '{"min_page_views": 5, "min_session_duration": 120, "has_conversions": true}',
        '{"has_website": true, "min_business_score": 80, "has_complete_profile": true}'
    ),
    (
        'Enterprise Lead',
        'Enterprise-level prospects requiring specialized attention',
        90,
        '["name", "email", "website", "phone", "address", "annual_revenue"]',
        '{"min_page_views": 10, "min_session_duration": 300, "has_conversions": true, "multiple_sessions": true}',
        '{"has_website": true, "min_business_score": 90, "enterprise_indicators": true}'
    )
ON CONFLICT (name) DO NOTHING;

-- Insert default sales team configuration (example)
INSERT INTO sales_team_members (user_id, name, email, role, specialties)
VALUES
    ('sales_rep_1', 'Sarah Johnson', 'sarah.johnson@company.com', 'sales_rep', '["technology", "healthcare"]'),
    ('sales_manager_1', 'Mike Chen', 'mike.chen@company.com', 'sales_manager', '["enterprise", "technology"]'),
    ('sales_rep_2', 'Jessica Brown', 'jessica.brown@company.com', 'sales_rep', '["retail", "ecommerce"]')
ON CONFLICT (user_id) DO NOTHING;

-- Engagement tracking tables for handoff queue integration
CREATE TABLE IF NOT EXISTS engagement_events (
    id SERIAL PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    properties JSONB DEFAULT '{}',
    page_url TEXT,
    referrer TEXT,
    user_agent TEXT,
    ip_address TEXT,
    campaign_id TEXT,
    ab_test_variant TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    total_events INTEGER DEFAULT 0,
    page_views INTEGER DEFAULT 0,
    unique_pages INTEGER DEFAULT 0,
    bounce_rate FLOAT DEFAULT 0.0,
    time_on_site FLOAT DEFAULT 0.0,
    conversion_events JSONB DEFAULT '[]',
    traffic_source TEXT,
    campaign_id TEXT,
    device_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversion_funnels (
    id SERIAL PRIMARY KEY,
    funnel_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    steps JSONB NOT NULL,
    goal_type TEXT NOT NULL,
    time_window_hours INTEGER DEFAULT 24,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS funnel_progress (
    id SERIAL PRIMARY KEY,
    funnel_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(funnel_id, user_id, step_index)
);

CREATE TABLE IF NOT EXISTS conversions (
    id SERIAL PRIMARY KEY,
    funnel_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    conversion_time TIMESTAMP NOT NULL,
    goal_type TEXT NOT NULL,
    event_id TEXT,
    campaign_id TEXT,
    ab_test_variant TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for engagement tracking
CREATE INDEX IF NOT EXISTS idx_engagement_events_user_id ON engagement_events(user_id);
CREATE INDEX IF NOT EXISTS idx_engagement_events_session_id ON engagement_events(session_id);
CREATE INDEX IF NOT EXISTS idx_engagement_events_timestamp ON engagement_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_engagement_events_event_type ON engagement_events(event_type);
CREATE INDEX IF NOT EXISTS idx_engagement_events_campaign_id ON engagement_events(campaign_id);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_id ON user_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_start_time ON user_sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_user_sessions_campaign_id ON user_sessions(campaign_id);

CREATE INDEX IF NOT EXISTS idx_conversion_funnels_funnel_id ON conversion_funnels(funnel_id);
CREATE INDEX IF NOT EXISTS idx_conversion_funnels_is_active ON conversion_funnels(is_active);

CREATE INDEX IF NOT EXISTS idx_funnel_progress_funnel_id ON funnel_progress(funnel_id);
CREATE INDEX IF NOT EXISTS idx_funnel_progress_user_id ON funnel_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_funnel_progress_timestamp ON funnel_progress(timestamp);

CREATE INDEX IF NOT EXISTS idx_conversions_funnel_id ON conversions(funnel_id);
CREATE INDEX IF NOT EXISTS idx_conversions_user_id ON conversions(user_id);
CREATE INDEX IF NOT EXISTS idx_conversions_conversion_time ON conversions(conversion_time);
