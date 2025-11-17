"""
ml/ml_predictor.py - Motor de predicciones con XGBoost

Usa modelo entrenado para predecir probabilidades de victoria.
"""
import logging
import numpy as np
import joblib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from .feature_extractor import FeatureExtractor

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    xgb = None

logger = logging.getLogger(__name__)


class MLPredictor:
    """Predictor de probabilidades usando XGBoost"""
    
    def __init__(self, models_dir: str = "ml/models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.feature_extractor = FeatureExtractor()
        self.models = {}  # sport_key -> modelo
        self.is_ready = False
        
        if not XGBOOST_AVAILABLE:
            logger.warning("XGBoost not available - ML predictions disabled")
            return
        
        # Cargar modelos existentes
        self._load_models()
    
    def _load_models(self):
        """Carga modelos entrenados desde disco"""
        try:
            model_files = list(self.models_dir.glob("*.joblib"))
            
            for model_file in model_files:
                sport_key = model_file.stem
                try:
                    model = joblib.load(model_file)
                    self.models[sport_key] = model
                    logger.info(f" Loaded ML model for {sport_key}")
                except Exception as e:
                    logger.error(f"Error loading model {sport_key}: {e}")
            
            if self.models:
                self.is_ready = True
                logger.info(f" ML Predictor ready with {len(self.models)} models")
            else:
                logger.info("No trained models found - using fallback predictions")
                
        except Exception as e:
            logger.error(f"Error loading models: {e}")
    
    def predict_probability(self, event: Dict, team_stats: Optional[Dict] = None,
                          injuries: Optional[Dict] = None,
                          line_movement: Optional[Dict] = None) -> Optional[Dict]:
        """
        Predice probabilidades de victoria para un evento.
        
        Args:
            event: Datos del evento
            team_stats: Estadísticas de equipos
            injuries: Información de lesiones
            line_movement: Datos de movimiento de línea
            
        Returns:
            Dict con probabilidades {home, away, draw} o None
        """
        try:
            # Verificar si tenemos modelo para este deporte
            sport_key = event.get('sport_key', '')
            
            # Extraer features
            features = self.feature_extractor.extract_features(
                event, team_stats, injuries, line_movement
            )
            
            if features is None:
                return None
            
            # Si tenemos modelo entrenado, usarlo
            if sport_key in self.models:
                return self._predict_with_model(features, sport_key, event)
            else:
                # Fallback: usar predicción basada en odds
                return self._fallback_prediction(event)
                
        except Exception as e:
            logger.error(f"Error in ML prediction: {e}")
            return None
    
    def _predict_with_model(self, features: np.ndarray, sport_key: str, 
                           event: Dict) -> Dict:
        """Predicción con modelo ML"""
        try:
            model = self.models[sport_key]
            
            # Reshape features para predicción
            features_2d = features.reshape(1, -1)
            
            # Predecir probabilidades
            if hasattr(model, 'predict_proba'):
                probs = model.predict_proba(features_2d)[0]
                
                # Para clasificación binaria (win/loss)
                if len(probs) == 2:
                    prob_home = float(probs[1])  # Clase 1 = victoria
                    prob_away = 1.0 - prob_home
                    prob_draw = 0.0
                # Para clasificación multi-clase (home/draw/away)
                elif len(probs) == 3:
                    prob_home, prob_draw, prob_away = [float(p) for p in probs]
                else:
                    return self._fallback_prediction(event)
            else:
                # Regresión: predice probabilidad directa
                pred = model.predict(features_2d)[0]
                prob_home = float(np.clip(pred, 0.0, 1.0))
                prob_away = 1.0 - prob_home
                prob_draw = 0.0
            
            return {
                'home': prob_home,
                'away': prob_away,
                'draw': prob_draw,
                'method': 'ml_model',
                'model': sport_key
            }
            
        except Exception as e:
            logger.error(f"Error in model prediction: {e}")
            return self._fallback_prediction(event)
    
    def _fallback_prediction(self, event: Dict) -> Optional[Dict]:
        """Predicción fallback basada en odds de mercado"""
        try:
            bookmakers = event.get('bookmakers', [])
            if not bookmakers:
                return None
            
            # Obtener odds promedio del mercado
            odds_sum = {'home': [], 'away': [], 'draw': []}
            
            for book in bookmakers:
                for market in book.get('markets', []):
                    if market.get('key') == 'h2h':
                        for outcome in market.get('outcomes', []):
                            name = outcome.get('name', '').lower()
                            price = float(outcome.get('price', 0))
                            
                            if price > 0:
                                if 'home' in name or event.get('home_team', '') in outcome.get('name', ''):
                                    odds_sum['home'].append(price)
                                elif 'away' in name or event.get('away_team', '') in outcome.get('name', ''):
                                    odds_sum['away'].append(price)
                                elif 'draw' in name or 'tie' in name:
                                    odds_sum['draw'].append(price)
            
            # Calcular odds promedio
            avg_home = np.mean(odds_sum['home']) if odds_sum['home'] else 2.0
            avg_away = np.mean(odds_sum['away']) if odds_sum['away'] else 2.0
            avg_draw = np.mean(odds_sum['draw']) if odds_sum['draw'] else 3.5
            
            # Convertir a probabilidades (removiendo margen)
            implied_home = 1.0 / avg_home
            implied_away = 1.0 / avg_away
            implied_draw = 1.0 / avg_draw
            
            total = implied_home + implied_away + implied_draw
            
            # Normalizar (remover vig)
            prob_home = implied_home / total
            prob_away = implied_away / total
            prob_draw = implied_draw / total
            
            return {
                'home': prob_home,
                'away': prob_away,
                'draw': prob_draw,
                'method': 'market_implied',
                'model': 'fallback'
            }
            
        except Exception as e:
            logger.error(f"Error in fallback prediction: {e}")
            return None
    
    def predict_batch(self, events: List[Dict], 
                     team_stats: Optional[Dict] = None,
                     injuries: Optional[Dict] = None) -> Dict[str, Dict]:
        """
        Predice probabilidades para múltiples eventos.
        
        Returns:
            Dict: {event_id: prediction_dict}
        """
        predictions = {}
        
        for event in events:
            event_id = event.get('id')
            if not event_id:
                continue
            
            # Obtener line movement si está disponible
            line_movement = None
            try:
                from analytics.line_movement import line_tracker
                home_team = event.get('home_team')
                if home_team:
                    line_movement = line_tracker.get_line_movement_summary(event_id, home_team)
            except:
                pass
            
            pred = self.predict_probability(event, team_stats, injuries, line_movement)
            if pred:
                predictions[event_id] = pred
        
        return predictions
    
    def is_ml_enabled(self) -> bool:
        """Verifica si ML está disponible y listo"""
        return XGBOOST_AVAILABLE and self.is_ready and len(self.models) > 0
    
    def get_available_sports(self) -> List[str]:
        """Retorna lista de deportes con modelo entrenado"""
        return list(self.models.keys())