-- Tabla users para persistencia en Supabase
CREATE TABLE IF NOT EXISTS users (
    chat_id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100),
    nivel VARCHAR(20) DEFAULT 'gratis',
    bankroll DECIMAL(10, 2) DEFAULT 1000.0,
    initial_bankroll DECIMAL(10, 2) DEFAULT 1000.0,
    dynamic_bank DECIMAL(10, 2) DEFAULT 200.0,
    alerts_sent_today INTEGER DEFAULT 0,
    last_reset_date DATE,
    total_bets INTEGER DEFAULT 0,
    won_bets INTEGER DEFAULT 0,
    total_profit DECIMAL(10, 2) DEFAULT 0.0,
    bet_history JSONB DEFAULT '[]',
    referral_code VARCHAR(20),
    referrer_id VARCHAR(50),
    referred_users JSONB DEFAULT '[]',
    premium_weeks_earned INTEGER DEFAULT 0,
    premium_expires_at TIMESTAMP,
    is_permanent_premium BOOLEAN DEFAULT false,
    referrals_paid INTEGER DEFAULT 0,
    saldo_comision DECIMAL(10, 2) DEFAULT 0.0,
    suscripcion_fin TIMESTAMP,
    total_commission_earned DECIMAL(10, 2) DEFAULT 0.0,
    free_weeks_earned INTEGER DEFAULT 0,
    dynamic_bank_last_reset DATE,
    week_start_bank DECIMAL(10, 2) DEFAULT 0.0,
    weekly_profit DECIMAL(10, 2) DEFAULT 0.0,
    weekly_fee_due DECIMAL(10, 2) DEFAULT 0.0,
    weekly_fee_paid BOOLEAN DEFAULT false,
    base_fee_paid BOOLEAN DEFAULT false,
    week_start_date DATE,
    payment_status VARCHAR(20) DEFAULT 'pending',
    last_payment_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code);
CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);

-- RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable read access for all users" ON users FOR SELECT USING (true);
CREATE POLICY "Enable insert for anon" ON users FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for anon" ON users FOR UPDATE USING (true);
