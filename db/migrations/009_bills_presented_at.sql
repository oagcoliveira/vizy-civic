-- Add presentation date to bills
ALTER TABLE core.bills ADD COLUMN IF NOT EXISTS presented_at DATE;
