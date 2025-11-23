-- ============================================================================
-- AGREGAR COLUMNA user_id A TABLA predictions
-- ============================================================================
-- Ejecuta este script en: SQL Editor de Supabase
-- ============================================================================

-- Agregar columna user_id a tabla predictions
ALTER TABLE predictions 
ADD COLUMN IF NOT EXISTS user_id VARCHAR(255);

-- Crear índice para búsquedas por usuario
CREATE INDEX IF NOT EXISTS idx_predictions_user ON predictions(user_id);

-- ============================================================================
-- VERIFICACIÓN
-- ============================================================================
-- Ejecuta esto para confirmar que la columna existe:
-- SELECT column_name, data_type FROM information_schema.columns 
-- WHERE table_name = 'predictions';
