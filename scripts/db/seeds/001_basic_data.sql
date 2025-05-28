-- Seed file: 001_basic_data
-- Description: Basic test data for E2E testing

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

-- Insert test businesses for E2E testing
INSERT INTO businesses (
    name, address, city, state, zip,
    phone, email, website, vertical, status
) VALUES
(
    'E2E Test Restaurant',
    '123 Test Street',
    'Beverly Hills',
    'CA',
    '90210',
    '555-123-4567',
    'restaurant@example.com',
    'https://restaurant-example.com',
    'restaurant',
    'pending'
),
(
    'E2E Test Retail',
    '456 Test Avenue',
    'New York',
    'NY',
    '10001',
    '555-987-6543',
    'retail@example.com',
    'https://retail-example.com',
    'retail',
    'pending'
),
(
    'E2E Test Salon',
    '789 Test Boulevard',
    'Chicago',
    'IL',
    '60601',
    '555-456-7890',
    'salon@example.com',
    'https://salon-example.com',
    'salon',
    'pending'
);
