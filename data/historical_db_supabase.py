"""
data/historical_db_supabase.py - Base de datos PostgreSQL (Supabase) para historial

Versión actualizada para usar PostgreSQL en Supabase en lugar de SQLite
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class HistoricalDatabase:
    """Base de datos PostgreSQL para almacenar historial deportivo"""
    
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL no configurado en .env")
        
        self._init_db()
    
    def _get_connection(self):
        """Crear conexión a PostgreSQL"""
        return psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)
    
    def _init_db(self):
        """Inicializar tablas si no existen"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Tabla de partidos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    id VARCHAR(255) PRIMARY KEY,
                    sport_key VARCHAR(100) NOT NULL,
                    home_team VARCHAR(200) NOT NULL,
                    away_team VARCHAR(200) NOT NULL,
                    commence_time TIMESTAMP NOT NULL,
                    home_score INTEGER,
                    away_score INTEGER,
                    result VARCHAR(50),
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            ''')
            
            # Tabla de estadísticas de equipos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS team_stats (
                    id SERIAL PRIMARY KEY,
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
                    last_updated TIMESTAMP NOT NULL,
                    UNIQUE(sport_key, team_name, season)
                )
            ''')
            
            # Tabla de predicciones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    id SERIAL PRIMARY KEY,
                    match_id VARCHAR(255) NOT NULL,
                    sport_key VARCHAR(100) NOT NULL,
                    selection TEXT NOT NULL,
                    odds DECIMAL(10, 2) NOT NULL,
                    predicted_prob DECIMAL(5, 4) NOT NULL,
                    value_score DECIMAL(10, 2) NOT NULL,
                    stake DECIMAL(10, 2),
                    predicted_at TIMESTAMP NOT NULL,
                    actual_result VARCHAR(50),
                    was_correct BOOLEAN,
                    profit_loss DECIMAL(10, 2),
                    verified_at TIMESTAMP
                )
            ''')
            
            # Tabla de lesiones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS injuries (
                    id SERIAL PRIMARY KEY,
                    sport_key VARCHAR(100) NOT NULL,
                    team_name VARCHAR(200) NOT NULL,
                    player_name VARCHAR(200) NOT NULL,
                    position VARCHAR(50),
                    injury_type VARCHAR(200),
                    status VARCHAR(100) NOT NULL,
                    reported_at TIMESTAMP NOT NULL,
                    resolved_at TIMESTAMP
                )
            ''')
            
            # Índices
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team, away_team)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_matches_sport ON matches(sport_key)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_team_stats_team ON team_stats(sport_key, team_name)')
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info("Supabase database initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Supabase database: {e}")
            raise
    
    # ==================== MATCHES ====================
    
    def save_match(self, match_data: Dict) -> bool:
        """Guardar o actualizar un partido"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc)
            
            # Verificar si existe
            cursor.execute('SELECT created_at FROM matches WHERE id = %s', (match_data['id'],))
            existing = cursor.fetchone()
            created_at = existing['created_at'] if existing else now
            
            cursor.execute('''
                INSERT INTO matches 
                (id, sport_key, home_team, away_team, commence_time, 
                 home_score, away_score, result, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    result = EXCLUDED.result,
                    updated_at = EXCLUDED.updated_at
            ''', (
                match_data['id'],
                match_data['sport_key'],
                match_data['home_team'],
                match_data['away_team'],
                match_data['commence_time'],
                match_data.get('home_score'),
                match_data.get('away_score'),
                match_data.get('result'),
                created_at,
                now
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error saving match: {e}")
            return False
    
    def get_h2h(self, team1: str, team2: str, sport_key: str, limit: int = 10) -> List[Dict]:
        """Obtener historial H2H entre dos equipos"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM matches
                WHERE sport_key = %s
                AND (
                    (home_team = %s AND away_team = %s)
                    OR (home_team = %s AND away_team = %s)
                )
                AND home_score IS NOT NULL
                ORDER BY commence_time DESC
                LIMIT %s
            ''', (sport_key, team1, team2, team2, team1, limit))
            
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error fetching H2H: {e}")
            return []
    
    def get_recent_matches(self, team: str, sport_key: str, limit: int = 10) -> List[Dict]:
        """Obtener últimos partidos de un equipo"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM matches
                WHERE sport_key = %s
                AND (home_team = %s OR away_team = %s)
                AND home_score IS NOT NULL
                ORDER BY commence_time DESC
                LIMIT %s
            ''', (sport_key, team, team, limit))
            
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error fetching recent matches: {e}")
            return []
    
    # ==================== TEAM STATS ====================
    
    def save_team_stats(self, stats: Dict) -> bool:
        """Guardar estadísticas de un equipo"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc)
            
            cursor.execute('''
                INSERT INTO team_stats
                (sport_key, team_name, season, wins, losses, draws,
                 goals_for, goals_against, points_for, points_against,
                 home_wins, away_wins, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sport_key, team_name, season) DO UPDATE SET
                    wins = EXCLUDED.wins,
                    losses = EXCLUDED.losses,
                    draws = EXCLUDED.draws,
                    goals_for = EXCLUDED.goals_for,
                    goals_against = EXCLUDED.goals_against,
                    points_for = EXCLUDED.points_for,
                    points_against = EXCLUDED.points_against,
                    home_wins = EXCLUDED.home_wins,
                    away_wins = EXCLUDED.away_wins,
                    last_updated = EXCLUDED.last_updated
            ''', (
                stats['sport_key'],
                stats['team_name'],
                stats.get('season', '2024-25'),
                stats.get('wins', 0),
                stats.get('losses', 0),
                stats.get('draws', 0),
                stats.get('goals_for', 0),
                stats.get('goals_against', 0),
                stats.get('points_for', 0),
                stats.get('points_against', 0),
                stats.get('home_wins', 0),
                stats.get('away_wins', 0),
                now
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error saving team stats: {e}")
            return False
    
    def get_team_stats(self, team_name: str, sport_key: str, season: str = "2024-25") -> Optional[Dict]:
        """Obtener estadísticas de un equipo"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM team_stats
                WHERE sport_key = %s AND team_name = %s AND season = %s
            ''', (sport_key, team_name, season))
            
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"Error fetching team stats: {e}")
            return None
    
    # ==================== PREDICTIONS ====================
    
    def save_prediction(self, prediction: Dict) -> Optional[int]:
        """Guardar una predicción del bot"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc)
            
            cursor.execute('''
                INSERT INTO predictions
                (match_id, sport_key, selection, odds, predicted_prob,
                 value_score, stake, user_id, predicted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                prediction['match_id'],
                prediction['sport_key'],
                prediction['selection'],
                prediction['odds'],
                prediction['predicted_prob'],
                prediction['value_score'],
                prediction.get('stake'),
                prediction.get('user_id'),
                now
            ))
            
            prediction_id = cursor.fetchone()['id']
            conn.commit()
            cursor.close()
            conn.close()
            
            return prediction_id
            
        except Exception as e:
            logger.error(f"Error saving prediction: {e}")
            return None
    
    def update_prediction_result(self, prediction_id: int, actual_result: str, 
                                 was_correct: bool, profit_loss: float = 0) -> bool:
        """Actualizar resultado real de una predicción"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc)
            
            cursor.execute('''
                UPDATE predictions
                SET actual_result = %s,
                    was_correct = %s,
                    profit_loss = %s,
                    verified_at = %s
                WHERE id = %s
            ''', (actual_result, was_correct, profit_loss, now, prediction_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error updating prediction result: {e}")
            return False
    
    def get_bot_performance(self, days: int = 30, sport_key: Optional[str] = None) -> Dict:
        """Calcular performance del bot en los últimos N días"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            query = '''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct,
                    SUM(profit_loss) as total_profit,
                    SUM(stake) as total_stake,
                    AVG(odds) as avg_odds
                FROM predictions
                WHERE verified_at IS NOT NULL
                AND predicted_at >= %s
            '''
            
            params = [cutoff_date]
            
            if sport_key:
                query += ' AND sport_key = %s'
                params.append(sport_key)
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if row and row['total'] and row['total'] > 0:
                total_stake = float(row['total_stake']) if row['total_stake'] else 1
                total_profit = float(row['total_profit']) if row['total_profit'] else 0
                correct = int(row['correct']) if row['correct'] else 0
                
                return {
                    'total_predictions': int(row['total']),
                    'correct': correct,
                    'accuracy': correct / int(row['total']),
                    'total_profit': total_profit,
                    'roi': (total_profit / total_stake) if total_stake > 0 else 0,
                    'avg_odds': float(row['avg_odds']) if row['avg_odds'] else 0
                }
            
            return {
                'total_predictions': 0,
                'correct': 0,
                'accuracy': 0,
                'total_profit': 0,
                'roi': 0,
                'avg_odds': 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating bot performance: {e}")
            return {}
    
    # ==================== INJURIES ====================
    
    def save_injuries(self, injuries: List[Dict]) -> int:
        """Guardar múltiples lesiones"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            now = datetime.now(timezone.utc)
            saved_count = 0
            
            for injury in injuries:
                try:
                    cursor.execute('''
                        INSERT INTO injuries
                        (sport_key, team_name, player_name, position,
                         injury_type, status, reported_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    ''', (
                        injury.get('sport_key', 'nba'),
                        injury.get('team', ''),
                        injury.get('player', ''),
                        injury.get('position', ''),
                        injury.get('injury', ''),
                        injury.get('status', ''),
                        now
                    ))
                    
                    if cursor.rowcount > 0:
                        saved_count += 1
                except:
                    continue
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Saved {saved_count} injuries to Supabase")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving injuries: {e}")
            return 0
    
    def get_team_injuries(self, team_name: str, sport_key: str) -> List[Dict]:
        """Obtener lesiones actuales de un equipo"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM injuries
                WHERE sport_key = %s AND team_name = %s
                AND resolved_at IS NULL
                ORDER BY reported_at DESC
            ''', (sport_key, team_name))
            
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error fetching team injuries: {e}")
            return []


# Instancia global
historical_db = HistoricalDatabase()
