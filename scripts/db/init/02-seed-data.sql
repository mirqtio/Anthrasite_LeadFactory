-- Seed data for E2E testing

-- Insert test ZIP codes
INSERT INTO zip_queue (zip, city, state) VALUES
('90210', 'Beverly Hills', 'CA'),
('10001', 'New York', 'NY'),
('60601', 'Chicago', 'IL'),
('98101', 'Seattle', 'WA'),
('33139', 'Miami Beach', 'FL')
ON CONFLICT (zip) DO NOTHING;

-- Insert business verticals
INSERT INTO verticals (name, display_name) VALUES
('restaurant', 'Restaurant'),
('retail', 'Retail Store'),
('salon', 'Hair Salon'),
('fitness', 'Fitness Center'),
('dental', 'Dental Office'),
('legal', 'Law Firm'),
('realestate', 'Real Estate'),
('automotive', 'Automotive Shop')
ON CONFLICT (name) DO NOTHING;

-- Insert a test business for E2E testing
INSERT INTO businesses (
    name, address, city, state, zip,
    phone, email, website, vertical, status
) VALUES (
    'E2E Test Business',
    '123 Test Street',
    'Test City',
    'TS',
    '12345',
    '555-123-4567',
    'test@example.com',
    'https://example.com',
    'restaurant',
    'pending'
);
