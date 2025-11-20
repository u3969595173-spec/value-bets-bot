-- Script para agregar columnas faltantes a la tabla users
-- Ejecutar en Supabase SQL Editor

-- Agregar columnas faltantes
ALTER TABLE users ADD COLUMN IF NOT EXISTS bet_history JSONB DEFAULT '[]';
ALTER TABLE users ADD COLUMN IF NOT EXISTS suscripcion_fin TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS dynamic_bank_last_reset DATE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS week_start_bank DECIMAL(10, 2) DEFAULT 0.0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS weekly_profit DECIMAL(10, 2) DEFAULT 0.0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS weekly_fee_due DECIMAL(10, 2) DEFAULT 0.0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS weekly_fee_paid BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS base_fee_paid BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS week_start_date DATE;

-- Verificar columnas
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'users' 
ORDER BY ordinal_position;
