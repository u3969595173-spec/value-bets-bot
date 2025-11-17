"""
scanner/ml_scanner.py - Scanner profesional con ML + Line Movement

Combina:
- Machine Learning predictions
- Line movement analysis
- Confidence scoring
- Value betting tradicional
"""
import logging
from typing import List, Dict, Optional
from scanner.enhanced_scanner import EnhancedValueScanner

try:
    from ml.ml_predictor import MLPredictor
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    MLPredictor = None

logger = logging.getLogger(__name__)


class MLValueScanner(EnhancedValueScanner):
    """Scanner de value bets con predicciones ML"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Inicializar predictor ML
        self.ml_predictor = None
        if ML_AVAILABLE and MLPredictor:
            try:
                self.ml_predictor = MLPredictor()
                if self.ml_predictor.is_ml_enabled():
                    logger.info(f" ML Scanner ready - models for: {self.ml_predictor.get_available_sports()}")
                else:
                    logger.info(" ML Scanner initialized - using fallback predictions")
            except Exception as e:
                logger.error(f"Error initializing ML predictor: {e}")
                self.ml_predictor = None
        else:
            logger.warning(" ML not available - using traditional scanner")
    
    def find_value_bets_ml(self, events: List[Dict], team_stats: Optional[Dict] = None,
                          injuries: Optional[Dict] = None) -> List[Dict]:
        """
        Encuentra value bets usando ML predictions.
        
        Flujo:
        1. Predecir probabilidades con ML
        2. Comparar con odds del mercado
        3. Añadir análisis de line movement
        4. Calcular confidence score
        5. Filtrar por umbral mínimo
        
        Args:
            events: Lista de eventos
            team_stats: Estadísticas de equipos
            injuries: Información de lesiones
            
        Returns:
            Lista de value bets ordenados por confidence
        """
        if not self.ml_predictor:
            # Fallback a scanner mejorado
            return self.find_value_bets_with_movement(events)
        
        try:
            candidates = []
            
            # Predecir probabilidades para todos los eventos
            ml_predictions = self.ml_predictor.predict_batch(events, team_stats, injuries)
            
            for event in events:
                event_id = event.get('id')
                if not event_id or event_id not in ml_predictions:
                    continue
                
                # Obtener predicción ML
                ml_pred = ml_predictions[event_id]
                
                # Analizar value con predicción ML
                value_ops = self._analyze_ml_value(event, ml_pred)
                
                if value_ops:
                    candidates.extend(value_ops)
            
            # Enriquecer con line movement (del scanner padre)
            enriched = []
            for candidate in candidates:
                event_id = candidate.get('id')
                selection = candidate.get('selection')
                
                # Obtener movimiento de línea
                movement = self.line_tracker.get_line_movement_summary(event_id, selection)
                
                if movement:
                    candidate['line_movement'] = {
                        'opening_odds': movement['opening_odds'],
                        'current_odds': movement['current_odds'],
                        'change_percent': movement['change_percent'],
                        'trend': movement['trend'],
                        'is_favorable': movement['is_favorable']
                    }
                else:
                    candidate['line_movement'] = None
                
                # Calcular confidence con ML
                confidence_score = self._calculate_ml_confidence(candidate, movement, ml_pred)
                candidate['confidence_score'] = confidence_score
                candidate['confidence_level'] = self._confidence_level(confidence_score)
                
                # Detectar steam moves
                steam_moves = self.line_tracker.detect_steam_moves(event_id)
                candidate['has_steam_move'] = any(
                    sm['selection'] == selection for sm in steam_moves
                )
                
                enriched.append(candidate)
            
            # Ordenar por confidence
            enriched.sort(key=lambda x: x.get('confidence_score', 0), reverse=True)
            
            logger.info(f" ML scan: {len(enriched)} candidates with ML predictions")
            
            return enriched
            
        except Exception as e:
            logger.error(f"Error in ML scanning: {e}")
            return self.find_value_bets_with_movement(events)
    
    def _analyze_ml_value(self, event: Dict, ml_pred: Dict) -> List[Dict]:
        """Analiza value usando predicciones ML"""
        try:
            value_ops = []
            
            # Obtener mejor cuota de cada outcome
            bookmakers = event.get('bookmakers', [])
            best_odds = {}
            
            for book in bookmakers:
                book_name = book.get('title', book.get('key'))
                
                for market in book.get('markets', []):
                    if market.get('key') != 'h2h':
                        continue
                    
                    for outcome in market.get('outcomes', []):
                        name = outcome.get('name')
                        price = float(outcome.get('price', 0))
                        
                        if name not in best_odds or price > best_odds[name]['odds']:
                            best_odds[name] = {
                                'odds': price,
                                'bookmaker': book_name,
                                'outcome': name
                            }
            
            # Comparar predicción ML con odds del mercado
            home_team = event.get('home_team', '')
            away_team = event.get('away_team', '')
            
            # Analizar home
            if home_team in best_odds:
                ml_prob_home = ml_pred.get('home', 0.5)
                odds_home = best_odds[home_team]['odds']
                value = odds_home * ml_prob_home
                
                if value > self._get_threshold(event.get('sport_key')) and odds_home >= self.min_odd and odds_home <= self.max_odd:
                    value_ops.append({
                        'id': event.get('id'),
                        'sport': event.get('sport_title', event.get('sport_key')),
                        'sport_key': event.get('sport_key'),
                        'home_team': home_team,
                        'away_team': away_team,
                        'selection': home_team,
                        'odds': odds_home,
                        'prob': ml_prob_home,
                        'value': value,
                        'bookmaker': best_odds[home_team]['bookmaker'],
                        'commence_time': event.get('commence_time'),
                        'ml_method': ml_pred.get('method'),
                        'ml_model': ml_pred.get('model')
                    })
            
            # Analizar away
            if away_team in best_odds:
                ml_prob_away = ml_pred.get('away', 0.5)
                odds_away = best_odds[away_team]['odds']
                value = odds_away * ml_prob_away
                
                if value > self._get_threshold(event.get('sport_key')) and odds_away >= self.min_odd and odds_away <= self.max_odd:
                    value_ops.append({
                        'id': event.get('id'),
                        'sport': event.get('sport_title', event.get('sport_key')),
                        'sport_key': event.get('sport_key'),
                        'home_team': home_team,
                        'away_team': away_team,
                        'selection': away_team,
                        'odds': odds_away,
                        'prob': ml_prob_away,
                        'value': value,
                        'bookmaker': best_odds[away_team]['bookmaker'],
                        'commence_time': event.get('commence_time'),
                        'ml_method': ml_pred.get('method'),
                        'ml_model': ml_pred.get('model')
                    })
            
            return value_ops
            
        except Exception as e:
            logger.error(f"Error analyzing ML value: {e}")
            return []
    
    def _calculate_ml_confidence(self, candidate: Dict, movement: Optional[Dict], 
                                ml_pred: Dict) -> float:
        """Calcula confidence score con boost por ML"""
        # Score base del padre
        base_score = super()._calculate_confidence(candidate, movement) if movement else 50.0
        
        # Boost por ML
        ml_boost = 0.0
        
        # Si usó modelo ML (no fallback), boost +15 puntos
        if ml_pred.get('method') == 'ml_model':
            ml_boost += 15.0
        
        # Si la probabilidad ML es muy alta (>70%), boost adicional +5
        prob = candidate.get('prob', 0.5)
        if prob > 0.70:
            ml_boost += 5.0
        
        return min(100.0, base_score + ml_boost)
    
    def _get_threshold(self, sport_key: str) -> float:
        """Umbral de value por deporte"""
        thresholds = {
            'basketball_nba': 1.08,
            'soccer_epl': 1.10,
            'soccer_spain_la_liga': 1.10,
            'baseball_mlb': 1.09,
            'tennis_atp': 1.07,
            'tennis_wta': 1.07
        }
        return thresholds.get(sport_key, 1.09)