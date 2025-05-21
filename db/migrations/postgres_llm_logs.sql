-- Anthrasite Lead-Factory: LLM Logs Migration (PostgreSQL)
-- Add llm_logs table for storing LLM prompts and responses

-- Create llm_logs table
CREATE TABLE IF NOT EXISTS llm_logs (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES businesses(id) ON DELETE SET NULL,
    operation TEXT NOT NULL,
    model_version TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    response_json JSONB NOT NULL,
    tokens_prompt INTEGER,
    tokens_completion INTEGER,
    duration_ms INTEGER,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    retention_expires_at TIMESTAMP,
    metadata JSONB
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_llm_logs_business_id ON llm_logs(business_id);
CREATE INDEX IF NOT EXISTS idx_llm_logs_operation ON llm_logs(operation);
CREATE INDEX IF NOT EXISTS idx_llm_logs_created_at ON llm_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_logs_retention_expires ON llm_logs(retention_expires_at);
