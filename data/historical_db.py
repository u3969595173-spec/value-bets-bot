"""
data/historical_db_api.py - Base de datos Supabase usando REST API

Versión simplificada usando el cliente oficial de Supabase
"""
import os
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class HistoricalDatabase:
    """Base de datos Supabase para almacenar historial deportivo"""
    
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("SUPABASE_URL y SUPABASE_KEY deben estar configurados en .env")
        
        self.supabase: Client = create_client(url, key)
        logger.info("Supabase client initialized successfully")
    
    # ==================== MATCHES ====================
    
    def save_match(self, match_data: Dict) -> bool:
        """Guardar o actualizar un partido"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            data = {
                'id': match_data['id'],
                'sport_key': match_data['sport_key'],
                'home_team': match_data['home_team'],
                'away_team': match_data['away_team'],
                'commence_time': match_data['commence_time'],
                'home_score': match_data.get('home_score'),
                'away_score': match_data.get('away_score'),
                'result': match_data.get('result'),
                'updated_at': now
            }
            
            # Verificar si existe
            existing = self.supabase.table('matches').select('id').eq('id', match_data['id']).execute()
            
            if existing.data:
                # Actualizar
                self.supabase.table('matches').update(data).eq('id', match_data['id']).execute()
            else:
                # Insertar
                data['created_at'] = now
                self.supabase.table('matches').insert(data).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving match: {e}")
            return False
    
    def get_h2h(self, team1: str, team2: str, sport_key: str, limit: int = 10) -> List[Dict]:
        """Obtener historial H2H entre dos equipos"""
        try:
            response = self.supabase.table('matches') \
                .select('*') \
                .eq('sport_key', sport_key) \
                .not_.is_('home_score', 'null') \
                .or_(f'and(home_team.eq.{team1},away_team.eq.{team2}),and(home_team.eq.{team2},away_team.eq.{team1})') \
                .order('commence_time', desc=True) \
                .limit(limit) \
                .execute()
            
            return response.data
            
        except Exception as e:
            logger.error(f"Error fetching H2H: {e}")
            return []
    
    def get_recent_matches(self, team: str, sport_key: str, limit: int = 10) -> List[Dict]:
        """Obtener últimos partidos de un equipo"""
        try:
            response = self.supabase.table('matches') \
                .select('*') \
                .eq('sport_key', sport_key) \
                .not_.is_('home_score', 'null') \
                .or_(f'home_team.eq.{team},away_team.eq.{team}') \
                .order('commence_time', desc=True) \
                .limit(limit) \
                .execute()
            
            return response.data
            
        except Exception as e:
            logger.error(f"Error fetching recent matches: {e}")
            return []
    
    # ==================== TEAM STATS ====================
    
    def save_team_stats(self, stats: Dict) -> bool:
        """Guardar estadísticas de un equipo"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            data = {
                'sport_key': stats['sport_key'],
                'team_name': stats['team_name'],
                'season': stats.get('season', '2024-25'),
                'wins': stats.get('wins', 0),
                'losses': stats.get('losses', 0),
                'draws': stats.get('draws', 0),
                'goals_for': stats.get('goals_for', 0),
                'goals_against': stats.get('goals_against', 0),
                'points_for': stats.get('points_for', 0),
                'points_against': stats.get('points_against', 0),
                'home_wins': stats.get('home_wins', 0),
                'away_wins': stats.get('away_wins', 0),
                'last_updated': now
            }
            
            # Verificar si existe
            existing = self.supabase.table('team_stats') \
                .select('id') \
                .eq('sport_key', stats['sport_key']) \
                .eq('team_name', stats['team_name']) \
                .eq('season', stats.get('season', '2024-25')) \
                .execute()
            
            if existing.data:
                # Actualizar
                self.supabase.table('team_stats').update(data).eq('id', existing.data[0]['id']).execute()
            else:
                # Insertar
                self.supabase.table('team_stats').insert(data).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving team stats: {e}")
            return False
    
    def get_team_stats(self, team_name: str, sport_key: str, season: str = "2024-25") -> Optional[Dict]:
        """Obtener estadísticas de un equipo"""
        try:
            response = self.supabase.table('team_stats') \
                .select('*') \
                .eq('sport_key', sport_key) \
                .eq('team_name', team_name) \
                .eq('season', season) \
                .execute()
            
            return response.data[0] if response.data else None
            
        except Exception as e:
            logger.error(f"Error fetching team stats: {e}")
            return None
    
    # ==================== PREDICTIONS ====================
    
    def save_prediction(self, prediction: Dict) -> Optional[int]:
        """Guardar una predicción del bot"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            data = {
                'match_id': prediction['match_id'],
                'sport_key': prediction['sport_key'],
                'selection': prediction['selection'],
                'odds': float(prediction['odds']),
                'predicted_prob': float(prediction['predicted_prob']),
                'value_score': float(prediction['value_score']),
                'stake': float(prediction.get('stake', 0)),
                'user_id': prediction.get('user_id'),
                'predicted_at': now
            }
            
            response = self.supabase.table('predictions').insert(data).execute()
            
            return response.data[0]['id'] if response.data else None
            
        except Exception as e:
            logger.error(f"Error saving prediction: {e}")
            return None
    
    def update_prediction_result(self, prediction_id: int, actual_result: str, 
                                 was_correct: bool, profit_loss: float = 0) -> bool:
        """Actualizar resultado real de una predicción"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            data = {
                'actual_result': actual_result,
                'was_correct': was_correct,
                'profit_loss': float(profit_loss),
                'verified_at': now
            }
            
            self.supabase.table('predictions').update(data).eq('id', prediction_id).execute()
            return True
            
        except Exception as e:
            logger.error(f"Error updating prediction result: {e}")
            return False
    
    def get_bot_performance(self, days: int = 30, sport_key: Optional[str] = None) -> Dict:
        """Calcular performance del bot en los últimos N días"""
        try:
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            query = self.supabase.table('predictions') \
                .select('*') \
                .not_.is_('verified_at', 'null') \
                .gte('predicted_at', cutoff_date)
            
            if sport_key:
                query = query.eq('sport_key', sport_key)
            
            response = query.execute()
            predictions = response.data
            
            if not predictions:
                return {
                    'total_predictions': 0,
                    'correct': 0,
                    'accuracy': 0,
                    'total_profit': 0,
                    'roi': 0,
                    'avg_odds': 0
                }
            
            total = len(predictions)
            correct = sum(1 for p in predictions if p.get('was_correct'))
            total_profit = sum(float(p.get('profit_loss', 0)) for p in predictions)
            total_stake = sum(float(p.get('stake', 0)) for p in predictions)
            avg_odds = sum(float(p.get('odds', 0)) for p in predictions) / total if total > 0 else 0
            
            return {
                'total_predictions': total,
                'correct': correct,
                'accuracy': correct / total if total > 0 else 0,
                'total_profit': total_profit,
                'roi': (total_profit / total_stake) if total_stake > 0 else 0,
                'avg_odds': avg_odds
            }
            
        except Exception as e:
            logger.error(f"Error calculating bot performance: {e}")
            return {
                'total_predictions': 0,
                'correct': 0,
                'accuracy': 0,
                'total_profit': 0,
                'roi': 0,
                'avg_odds': 0
            }
    
    # ==================== INJURIES ====================
    
    def save_injuries(self, injuries: List[Dict]) -> int:
        """Guardar múltiples lesiones"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            saved_count = 0
            
            for injury in injuries:
                try:
                    data = {
                        'sport_key': injury.get('sport_key', 'nba'),
                        'team_name': injury.get('team', ''),
                        'player_name': injury.get('player', ''),
                        'position': injury.get('position', ''),
                        'injury_type': injury.get('injury', ''),
                        'status': injury.get('status', ''),
                        'reported_at': now
                    }
                    
                    self.supabase.table('injuries').insert(data).execute()
                    saved_count += 1
                except:
                    continue
            
            logger.info(f"Saved {saved_count} injuries to Supabase")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving injuries: {e}")
            return 0
    
    def get_team_injuries(self, team_name: str, sport_key: str) -> List[Dict]:
        """Obtener lesiones actuales de un equipo"""
        try:
            response = self.supabase.table('injuries') \
                .select('*') \
                .eq('sport_key', sport_key) \
                .eq('team_name', team_name) \
                .is_('resolved_at', 'null') \
                .order('reported_at', desc=True) \
                .execute()
            
            return response.data
            
        except Exception as e:
            logger.error(f"Error fetching team injuries: {e}")
            return []
    
    # ==================== VERIFICATION ====================
    
    def get_unverified_predictions(self, before_time: str) -> List[Dict]:
        """Obtener predicciones sin verificar de hace más de X horas"""
        try:
            response = self.supabase.table('predictions') \
                .select('*') \
                .is_('verified_at', 'null') \
                .lt('predicted_at', before_time) \
                .order('predicted_at', desc=False) \
                .execute()
            
            return response.data
            
        except Exception as e:
            logger.error(f"Error fetching unverified predictions: {e}")
            return []
    
    def verify_prediction(self, prediction_id: str, was_correct: bool, 
                         actual_home_score: int, actual_away_score: int,
                         profit_loss: float) -> bool:
        """Marca una predicción como verificada con su resultado"""
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            data = {
                'was_correct': was_correct,
                'actual_home_score': actual_home_score,
                'actual_away_score': actual_away_score,
                'profit_loss': profit_loss,
                'verified_at': now
            }
            
            self.supabase.table('predictions').update(data).eq('id', prediction_id).execute()
            logger.info(f"✅ Prediction {prediction_id[:8]}... verified: {was_correct}, P/L: ${profit_loss:+.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying prediction: {e}")
            return False
    
    # ==================== LINE MOVEMENT ====================
    
    def save_odds_snapshot(self, snapshot: Dict) -> bool:
        """Guarda snapshot de cuotas para tracking de movimiento"""
        try:
            data = {
                'timestamp': snapshot['timestamp'],
                'event_id': snapshot['event_id'],
                'sport_key': snapshot.get('sport_key'),
                'bookmaker': snapshot['bookmaker'],
                'market': snapshot['market'],
                'selection': snapshot['selection'],
                'odds': snapshot['odds'],
                'point': snapshot.get('point')
            }
            
            self.supabase.table('odds_snapshots').insert(data).execute()
            return True
            
        except Exception as e:
            logger.error(f"Error saving odds snapshot: {e}")
            return False
    
    def save_odds_snapshots_batch(self, snapshots: List[Dict]) -> int:
        """Guarda múltiples snapshots en lote (mucho más rápido)"""
        if not snapshots:
            return 0
            
        try:
            # Preparar datos
            batch_data = []
            for snapshot in snapshots:
                batch_data.append({
                    'timestamp': snapshot['timestamp'],
                    'event_id': snapshot['event_id'],
                    'sport_key': snapshot.get('sport_key'),
                    'bookmaker': snapshot['bookmaker'],
                    'market': snapshot['market'],
                    'selection': snapshot['selection'],
                    'odds': snapshot['odds'],
                    'point': snapshot.get('point')
                })
            
            # Insertar en lotes de 1000 (límite de Supabase)
            batch_size = 1000
            total_saved = 0
            
            for i in range(0, len(batch_data), batch_size):
                batch = batch_data[i:i + batch_size]
                self.supabase.table('odds_snapshots').insert(batch).execute()
                total_saved += len(batch)
                logger.info(f"💾 Guardados {total_saved}/{len(batch_data)} snapshots...")
            
            return total_saved
            
        except Exception as e:
            logger.error(f"Error saving odds snapshots batch: {e}")
            return 0
    
    def get_odds_history(self, event_id: str, hours: int = 24) -> List[Dict]:
        """Obtiene histórico de cuotas de un evento"""
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            
            response = self.supabase.table('odds_snapshots') \
                .select('*') \
                .eq('event_id', event_id) \
                .gte('timestamp', cutoff) \
                .order('timestamp', desc=False) \
                .execute()
            
            return response.data
            
        except Exception as e:
            logger.error(f"Error fetching odds history: {e}")
            return []


# Instancia global
historical_db = HistoricalDatabase()
