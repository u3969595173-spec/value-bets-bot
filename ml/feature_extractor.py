"""
ml/feature_extractor.py - Extracción de features para ML

Convierte datos de eventos en features numéricas para el modelo.
"""
import logging
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """Extrae features de eventos para machine learning"""
    
    def __init__(self):
        self.feature_names = []
        self._build_feature_names()
    
    def _build_feature_names(self):
        """Define nombres de features"""
        self.feature_names = [
            # Features básicas
            'odds_home', 'odds_away', 'odds_draw',
            'implied_prob_home', 'implied_prob_away', 'implied_prob_draw',
            'market_margin',
            
            # Features de team stats
            'home_win_rate', 'away_win_rate',
            'home_recent_form', 'away_recent_form',
            'home_goals_avg', 'away_goals_avg',
            'home_conceded_avg', 'away_conceded_avg',
            
            # Features de lesiones
            'home_injuries_count', 'away_injuries_count',
            'home_key_injuries', 'away_key_injuries',
            
            # Features de line movement
            'odds_movement_pct', 'steam_move_detected',
            'rlm_detected', 'hours_tracked',
            
            # Features temporales
            'hours_until_match', 'is_weekend', 'hour_of_day'
        ]
    
    def extract_features(self, event: Dict, team_stats: Optional[Dict] = None,
                        injuries: Optional[Dict] = None,
                        line_movement: Optional[Dict] = None) -> Optional[np.ndarray]:
        """
        Extrae todas las features de un evento.
        
        Args:
            event: Datos del evento
            team_stats: Estadísticas de equipos (opcional)
            injuries: Información de lesiones (opcional)
            line_movement: Datos de movimiento de línea (opcional)
            
        Returns:
            Array numpy con features o None si faltan datos críticos
        """
        try:
            features = []
            
            # 1. Features básicas de odds
            odds_features = self._extract_odds_features(event)
            if odds_features is None:
                return None
            features.extend(odds_features)
            
            # 2. Features de team stats
            stats_features = self._extract_stats_features(event, team_stats)
            features.extend(stats_features)
            
            # 3. Features de lesiones
            injury_features = self._extract_injury_features(event, injuries)
            features.extend(injury_features)
            
            # 4. Features de line movement
            movement_features = self._extract_movement_features(event, line_movement)
            features.extend(movement_features)
            
            # 5. Features temporales
            temporal_features = self._extract_temporal_features(event)
            features.extend(temporal_features)
            
            return np.array(features, dtype=np.float32)
            
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return None
    
    def _extract_odds_features(self, event: Dict) -> Optional[List[float]]:
        """Extrae features de cuotas"""
        try:
            # Obtener mejores cuotas de cada mercado
            bookmakers = event.get('bookmakers', [])
            if not bookmakers:
                return None
            
            # Buscar mercado h2h
            best_odds = {'home': 0.0, 'away': 0.0, 'draw': 0.0}
            
            for book in bookmakers:
                for market in book.get('markets', []):
                    if market.get('key') == 'h2h':
                        for outcome in market.get('outcomes', []):
                            name = outcome.get('name', '').lower()
                            price = float(outcome.get('price', 0))
                            
                            if 'home' in name or event.get('home_team', '') in outcome.get('name', ''):
                                best_odds['home'] = max(best_odds['home'], price)
                            elif 'away' in name or event.get('away_team', '') in outcome.get('name', ''):
                                best_odds['away'] = max(best_odds['away'], price)
                            elif 'draw' in name or 'tie' in name:
                                best_odds['draw'] = max(best_odds['draw'], price)
            
            # Si no hay odds, no podemos continuar
            if best_odds['home'] == 0.0 or best_odds['away'] == 0.0:
                return None
            
            # Calcular probabilidades implícitas
            implied_home = 1.0 / best_odds['home'] if best_odds['home'] > 0 else 0
            implied_away = 1.0 / best_odds['away'] if best_odds['away'] > 0 else 0
            implied_draw = 1.0 / best_odds['draw'] if best_odds['draw'] > 0 else 0
            
            # Calcular margen del mercado
            margin = implied_home + implied_away + implied_draw - 1.0
            
            return [
                best_odds['home'], best_odds['away'], best_odds.get('draw', 1.01),
                implied_home, implied_away, implied_draw,
                max(0, margin)
            ]
            
        except Exception as e:
            logger.error(f"Error in odds features: {e}")
            return None
    
    def _extract_stats_features(self, event: Dict, team_stats: Optional[Dict]) -> List[float]:
        """Extrae features de estadísticas de equipos"""
        default_stats = [0.5, 0.5, 0.5, 0.5, 1.5, 1.5, 1.5, 1.5]
        
        if not team_stats:
            return default_stats
        
        try:
            home_team = event.get('home_team', '')
            away_team = event.get('away_team', '')
            
            home_stats = team_stats.get(home_team, {})
            away_stats = team_stats.get(away_team, {})
            
            return [
                home_stats.get('win_rate', 0.5),
                away_stats.get('win_rate', 0.5),
                home_stats.get('recent_form', 0.5),
                away_stats.get('recent_form', 0.5),
                home_stats.get('goals_avg', 1.5),
                away_stats.get('goals_avg', 1.5),
                home_stats.get('conceded_avg', 1.5),
                away_stats.get('conceded_avg', 1.5)
            ]
        except:
            return default_stats
    
    def _extract_injury_features(self, event: Dict, injuries: Optional[Dict]) -> List[float]:
        """Extrae features de lesiones"""
        default = [0.0, 0.0, 0.0, 0.0]
        
        if not injuries:
            return default
        
        try:
            home_team = event.get('home_team', '')
            away_team = event.get('away_team', '')
            
            home_injuries = injuries.get(home_team, [])
            away_injuries = injuries.get(away_team, [])
            
            # Contar lesiones
            home_count = len(home_injuries)
            away_count = len(away_injuries)
            
            # Contar lesiones de jugadores clave (starters)
            home_key = sum(1 for inj in home_injuries if inj.get('is_starter', False))
            away_key = sum(1 for inj in away_injuries if inj.get('is_starter', False))
            
            return [float(home_count), float(away_count), float(home_key), float(away_key)]
        except:
            return default
    
    def _extract_movement_features(self, event: Dict, line_movement: Optional[Dict]) -> List[float]:
        """Extrae features de movimiento de línea"""
        default = [0.0, 0.0, 0.0, 0.0]
        
        if not line_movement:
            return default
        
        try:
            return [
                line_movement.get('change_percent', 0.0),
                1.0 if line_movement.get('steam_move') else 0.0,
                1.0 if line_movement.get('rlm_detected') else 0.0,
                line_movement.get('hours_tracked', 0.0)
            ]
        except:
            return default
    
    def _extract_temporal_features(self, event: Dict) -> List[float]:
        """Extrae features temporales"""
        try:
            commence_time = event.get('commence_time')
            if isinstance(commence_time, str):
                commence_time = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
            
            now = datetime.now(timezone.utc)
            
            hours_until = (commence_time - now).total_seconds() / 3600
            is_weekend = 1.0 if commence_time.weekday() >= 5 else 0.0
            hour_of_day = float(commence_time.hour)
            
            return [hours_until, is_weekend, hour_of_day]
        except:
            return [24.0, 0.0, 20.0]
    
    def get_feature_count(self) -> int:
        """Retorna número de features"""
        return len(self.feature_names)