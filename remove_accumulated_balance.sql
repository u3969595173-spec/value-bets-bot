-- Eliminar columna accumulated_balance (es un alias de saldo_comision)
ALTER TABLE users DROP COLUMN IF EXISTS accumulated_balance;

-- Verificar que se eliminó
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'users' 
ORDER BY ordinal_position;
