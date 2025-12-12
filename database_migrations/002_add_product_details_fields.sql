-- Migration: Add additional fields for product details and specifications
-- Run this if you need to add these columns to an existing table

-- Add sodium tracking (common nutritional info)
ALTER TABLE costco_products ADD COLUMN IF NOT EXISTS sodium INT;

-- Add fiber tracking
ALTER TABLE costco_products ADD COLUMN IF NOT EXISTS fiber INT;

-- Add sugar tracking
ALTER TABLE costco_products ADD COLUMN IF NOT EXISTS sugar INT;

-- Add ingredients list
ALTER TABLE costco_products ADD COLUMN IF NOT EXISTS ingredients TEXT;

-- Add allergens
ALTER TABLE costco_products ADD COLUMN IF NOT EXISTS allergens TEXT;

-- Add raw product details (for any info not captured in structured fields)
ALTER TABLE costco_products ADD COLUMN IF NOT EXISTS raw_product_details TEXT;

-- Add raw specifications (for any info not captured in structured fields)
ALTER TABLE costco_products ADD COLUMN IF NOT EXISTS raw_specifications TEXT;

-- Update the updated_at trigger if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger if not exists (drop first to be safe)
DROP TRIGGER IF EXISTS update_costco_products_updated_at ON costco_products;
CREATE TRIGGER update_costco_products_updated_at
    BEFORE UPDATE ON costco_products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
