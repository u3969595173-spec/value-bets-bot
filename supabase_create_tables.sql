-- ============================================================================
-- SCRIPT SQL PARA CREAR TABLAS EN SUPABASE
-- ============================================================================
-- Copia y pega este script en: SQL Editor de tu proyecto Supabase
-- Luego click en "Run" para crear todas las tablas
-- ============================================================================

-- Tabla matches (partidos)
CREATE TABLE IF NOT EXISTS matches (
    id VARCHAR(255) PRIMARY KEY,
    sport_key VARCHAR(100) NOT NULL,
    home_team VARCHAR(200) NOT NULL,
    away_team VARCHAR(200) NOT NULL,
    commence_time TIMESTAMP NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    result VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Tabla team_stats (estadísticas de equipos)
CREATE TABLE IF NOT EXISTS team_stats (
    id BIGSERIAL PRIMARY KEY,
    sport_key VARCHAR(100) NOT NULL,
    team_name VARCHAR(200) NOT NULL,
    season VARCHAR(50) NOT NULL,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    goals_for INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    points_for INTEGER DEFAULT 0,
    points_against INTEGER DEFAULT 0,
    home_wins INTEGER DEFAULT 0,
    away_wins INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(sport_key, team_name, season)
);

-- Tabla predictions (predicciones del bot)
CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL PRIMARY KEY,
    match_id VARCHAR(255) NOT NULL,
    sport_key VARCHAR(100) NOT NULL,
    selection TEXT NOT NULL,
    odds DECIMAL(10, 2) NOT NULL,
    predicted_prob DECIMAL(5, 4) NOT NULL,
    value_score DECIMAL(10, 2) NOT NULL,
    stake DECIMAL(10, 2),
    predicted_at TIMESTAMP DEFAULT NOW(),
    actual_result VARCHAR(50),
    was_correct BOOLEAN,
    profit_loss DECIMAL(10, 2),
    verified_at TIMESTAMP
);

-- Tabla injuries (lesiones)
CREATE TABLE IF NOT EXISTS injuries (
    id BIGSERIAL PRIMARY KEY,
    sport_key VARCHAR(100) NOT NULL,
    team_name VARCHAR(200) NOT NULL,
    player_name VARCHAR(200) NOT NULL,
    position VARCHAR(50),
    injury_type VARCHAR(200),
    status VARCHAR(100) NOT NULL,
    reported_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

-- ============================================================================
-- ÍNDICES PARA OPTIMIZAR BÚSQUEDAS
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team, away_team);
CREATE INDEX IF NOT EXISTS idx_matches_sport ON matches(sport_key);
CREATE INDEX IF NOT EXISTS idx_matches_time ON matches(commence_time);
CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_predictions_verified ON predictions(verified_at);
CREATE INDEX IF NOT EXISTS idx_team_stats_team ON team_stats(sport_key, team_name);
CREATE INDEX IF NOT EXISTS idx_injuries_team ON injuries(sport_key, team_name);

-- ============================================================================
-- POLÍTICAS DE SEGURIDAD (Row Level Security)
-- ============================================================================

-- Habilitar RLS en todas las tablas
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE injuries ENABLE ROW LEVEL SECURITY;

-- Permitir lectura pública (anon puede leer)
CREATE POLICY "Enable read access for all users" ON matches FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON team_stats FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON predictions FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON injuries FOR SELECT USING (true);

-- Permitir inserción/actualización con anon key
CREATE POLICY "Enable insert for anon" ON matches FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for anon" ON matches FOR UPDATE USING (true);
CREATE POLICY "Enable insert for anon" ON team_stats FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for anon" ON team_stats FOR UPDATE USING (true);
CREATE POLICY "Enable insert for anon" ON predictions FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for anon" ON predictions FOR UPDATE USING (true);
CREATE POLICY "Enable insert for anon" ON injuries FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for anon" ON injuries FOR UPDATE USING (true);

-- ============================================================================
-- TABLA USERS (usuarios del bot)
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    chat_id VARCHAR(255) PRIMARY KEY,
    username VARCHAR(200),
    nivel VARCHAR(50) NOT NULL DEFAULT 'gratis',
    bankroll DECIMAL(10, 2) DEFAULT 1000.0,
    initial_bankroll DECIMAL(10, 2) DEFAULT 1000.0,
    alerts_sent_today INTEGER DEFAULT 0,
    last_reset_date VARCHAR(50),
    total_bets INTEGER DEFAULT 0,
    won_bets INTEGER DEFAULT 0,
    total_profit DECIMAL(10, 2) DEFAULT 0.0,
    bet_history JSONB DEFAULT '[]'::jsonb,
    -- Campos de referidos
    referral_code VARCHAR(50) UNIQUE,
    referrer_id VARCHAR(255),
    referred_users JSONB DEFAULT '[]'::jsonb,
    premium_weeks_earned INTEGER DEFAULT 0,
    premium_expires_at VARCHAR(100),
    is_permanent_premium BOOLEAN DEFAULT false,
    -- Campos de comisiones
    referrals_paid INTEGER DEFAULT 0,
    saldo_comision DECIMAL(10, 2) DEFAULT 0.0,
    suscripcion_fin VARCHAR(100),
    total_commission_earned DECIMAL(10, 2) DEFAULT 0.0,
    free_weeks_earned INTEGER DEFAULT 0,
    -- Bank dinámico y pagos
    dynamic_bank DECIMAL(10, 2) DEFAULT 200.0,
    dynamic_bank_last_reset VARCHAR(50),
    week_start_bank DECIMAL(10, 2) DEFAULT 200.0,
    weekly_profit DECIMAL(10, 2) DEFAULT 0.0,
    weekly_fee_due DECIMAL(10, 2) DEFAULT 0.0,
    weekly_fee_paid BOOLEAN DEFAULT false,
    base_fee_paid BOOLEAN DEFAULT false,
    week_start_date VARCHAR(50),
    payment_status VARCHAR(50) DEFAULT 'pending',
    last_payment_date VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_users_nivel ON users(nivel);
CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code);
CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);

-- RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable read access for all users" ON users FOR SELECT USING (true);
CREATE POLICY "Enable insert for anon" ON users FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for anon" ON users FOR UPDATE USING (true);

-- ============================================================================
-- ✅ LISTO! Ahora ejecuta el script de migración de Python
-- ============================================================================

