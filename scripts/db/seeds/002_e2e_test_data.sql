-- Seed file: 002_e2e_test_data
-- Description: Specific test data needed for E2E test scenarios

-- Insert special E2E test business
-- This is the specific test business used in BDD scenarios
INSERT INTO businesses (
    name, address, city, state, zip,
    phone, email, website, vertical, status
) VALUES
(
    'E2E Test Business',
    '123 Test St',
    'Testville',
    'TS',
    '12345',
    '555-123-4567',
    'test@example.com',
    'https://example.com',
    'restaurant',
    'pending'
)
ON CONFLICT DO NOTHING;
