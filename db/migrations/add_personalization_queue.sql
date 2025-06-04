-- Add personalization queue table for GPU auto-scaling
-- This table tracks personalization tasks that may require GPU processing

CREATE TABLE IF NOT EXISTS personalization_queue (
    id SERIAL PRIMARY KEY,
    business_id INTEGER REFERENCES businesses(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL, -- 'website_mockup_generation', 'ai_content_personalization', etc.
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    gpu_required BOOLEAN DEFAULT FALSE,
    processing_node TEXT, -- Which GPU instance is processing this task
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    task_data JSONB, -- Task-specific parameters and data
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_personalization_queue_status ON personalization_queue(status);
CREATE INDEX IF NOT EXISTS idx_personalization_queue_priority ON personalization_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_personalization_queue_gpu_required ON personalization_queue(gpu_required);
CREATE INDEX IF NOT EXISTS idx_personalization_queue_created_at ON personalization_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_personalization_queue_processing_node ON personalization_queue(processing_node);
CREATE INDEX IF NOT EXISTS idx_personalization_queue_business_id ON personalization_queue(business_id);

-- Update function for updated_at timestamp
CREATE OR REPLACE FUNCTION update_personalization_queue_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at
CREATE TRIGGER update_personalization_queue_updated_at
    BEFORE UPDATE ON personalization_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_personalization_queue_updated_at();