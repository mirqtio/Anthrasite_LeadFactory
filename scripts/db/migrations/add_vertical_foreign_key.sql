-- Migration: Add vertical foreign key constraint to businesses table
-- This improves data integrity by ensuring all businesses reference valid verticals

-- Step 1: Add missing HVAC vertical to verticals table
INSERT INTO verticals (name, display_name, created_at)
VALUES ('hvac', 'HVAC Services', CURRENT_TIMESTAMP)
ON CONFLICT (name) DO NOTHING;

-- Step 2: Add new vertical_id column to businesses table
ALTER TABLE businesses ADD COLUMN vertical_id INTEGER;

-- Step 3: Populate vertical_id based on existing vertical text values
UPDATE businesses
SET vertical_id = v.id
FROM verticals v
WHERE LOWER(businesses.vertical) = LOWER(v.name);

-- Step 4: Handle any remaining unmapped verticals (create them)
-- This ensures no data is lost during migration
INSERT INTO verticals (name, display_name, created_at)
SELECT DISTINCT
    LOWER(b.vertical) as name,
    INITCAP(b.vertical) as display_name,
    CURRENT_TIMESTAMP
FROM businesses b
LEFT JOIN verticals v ON LOWER(b.vertical) = LOWER(v.name)
WHERE v.id IS NULL
  AND b.vertical IS NOT NULL
  AND b.vertical != '';

-- Step 5: Update any remaining businesses with new vertical IDs
UPDATE businesses
SET vertical_id = v.id
FROM verticals v
WHERE LOWER(businesses.vertical) = LOWER(v.name)
  AND businesses.vertical_id IS NULL;

-- Step 6: Add foreign key constraint
ALTER TABLE businesses
ADD CONSTRAINT fk_businesses_vertical
FOREIGN KEY (vertical_id) REFERENCES verticals(id);

-- Step 7: Set default vertical for any NULL values (use 'other' category)
INSERT INTO verticals (name, display_name, created_at)
VALUES ('other', 'Other Services', CURRENT_TIMESTAMP)
ON CONFLICT (name) DO NOTHING;

UPDATE businesses
SET vertical_id = (SELECT id FROM verticals WHERE name = 'other')
WHERE vertical_id IS NULL;

-- Step 8: Make vertical_id NOT NULL now that all records have values
ALTER TABLE businesses ALTER COLUMN vertical_id SET NOT NULL;

-- Step 9: Create index for performance
CREATE INDEX idx_businesses_vertical_id ON businesses(vertical_id);

-- Step 10: Add comment for documentation
COMMENT ON COLUMN businesses.vertical_id IS 'Foreign key to verticals table - ensures data integrity for business categories';

-- Note: Keep the old vertical column for now to allow gradual migration
-- It can be dropped in a future migration after confirming everything works
COMMENT ON COLUMN businesses.vertical IS 'DEPRECATED: Use vertical_id instead. Will be removed in future migration.';
