-- Schema para clv_tracking
-- Closing Line Value: métrica #1 para medir calidad predictiva

CREATE TABLE IF NOT EXISTS clv_tracking (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Información del evento y apuesta
    event_id TEXT NOT NULL,
    selection TEXT NOT NULL,
    
    -- Cuotas
    opening_odds DECIMAL(10, 2) NOT NULL,  -- Cuota en momento de alerta
    closing_odds DECIMAL(10, 2),           -- Cuota 5min antes del partido
    clv DECIMAL(10, 4),                    -- Closing Line Value calculado
    
    -- Timestamps
    opening_timestamp TIMESTAMPTZ NOT NULL,
    closing_timestamp TIMESTAMPTZ,
    minutes_before_start INTEGER DEFAULT 5,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT clv_tracking_odds_check CHECK (opening_odds >= 1.0 AND opening_odds <= 1000.0),
    CONSTRAINT clv_tracking_unique UNIQUE(event_id, selection)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_clv_tracking_event ON clv_tracking(event_id);
CREATE INDEX IF NOT EXISTS idx_clv_tracking_created_at ON clv_tracking(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_clv_tracking_clv ON clv_tracking(clv) WHERE clv IS NOT NULL;

-- Comentarios
COMMENT ON TABLE clv_tracking IS 'Tracking de Closing Line Value para medir calidad predictiva';
COMMENT ON COLUMN clv_tracking.opening_odds IS 'Cuota en momento de la alerta';
COMMENT ON COLUMN clv_tracking.closing_odds IS 'Cuota 5 minutos antes del inicio';
COMMENT ON COLUMN clv_tracking.clv IS 'CLV = (closing_odds - opening_odds) / opening_odds';