"""
ml/model_trainer.py - Entrenamiento y actualización de modelos ML

Entrena modelos XGBoost con datos históricos verificados.
"""
import logging
import numpy as np
import joblib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from .feature_extractor import FeatureExtractor

try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, roc_auc_score, log_loss
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    xgb = None

logger = logging.getLogger(__name__)


class ModelTrainer:
    """Entrena y actualiza modelos ML con datos verificados"""
    
    def __init__(self, models_dir: str = "ml/models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.feature_extractor = FeatureExtractor()
        
        if not ML_AVAILABLE:
            logger.warning("ML libraries not available - training disabled")
    
    def train_model(self, sport_key: str, historical_db, 
                   min_samples: int = 100) -> Optional[Dict]:
        """
        Entrena un modelo para un deporte específico.
        
        Args:
            sport_key: Deporte (e.g., 'basketball_nba')
            historical_db: Instancia de HistoricalDatabase
            min_samples: Mínimo de muestras para entrenar
            
        Returns:
            Dict con métricas de entrenamiento o None
        """
        if not ML_AVAILABLE:
            logger.error("Cannot train - ML libraries not available")
            return None
        
        try:
            logger.info(f" Starting training for {sport_key}")
            
            # 1. Obtener datos históricos verificados
            X, y = self._prepare_training_data(sport_key, historical_db)
            
            if X is None or len(X) < min_samples:
                logger.warning(f"Insufficient data for {sport_key}: {len(X) if X is not None else 0} samples")
                return None
            
            logger.info(f" Training dataset: {len(X)} samples, {X.shape[1]} features")
            
            # 2. Split train/test
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # 3. Entrenar modelo XGBoost
            model = self._train_xgboost(X_train, y_train, X_test, y_test)
            
            # 4. Evaluar modelo
            metrics = self._evaluate_model(model, X_test, y_test)
            logger.info(f" Model metrics: {metrics}")
            
            # 5. Guardar modelo
            model_path = self.models_dir / f"{sport_key}.joblib"
            joblib.dump(model, model_path)
            logger.info(f" Model saved to {model_path}")
            
            return {
                'sport_key': sport_key,
                'samples': len(X),
                'features': X.shape[1],
                'metrics': metrics,
                'model_path': str(model_path),
                'trained_at': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error training model for {sport_key}: {e}")
            return None
    
    def _prepare_training_data(self, sport_key: str, historical_db) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Prepara datos de entrenamiento desde BD histórica"""
        try:
            # Obtener predicciones verificadas (últimos 90 días)
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=90)
            
            verified_predictions = historical_db.supabase.table('predictions') \
                .select('*') \
                .eq('sport_key', sport_key) \
                .not_.is_('result', 'null') \
                .gte('created_at', cutoff_date.isoformat()) \
                .execute()
            
            if not verified_predictions.data:
                return None, None
            
            X_list = []
            y_list = []
            
            for pred in verified_predictions.data:
                # Reconstruir features desde predicción
                # (En producción, guardarías features en la BD)
                features = self._reconstruct_features(pred)
                
                if features is not None:
                    X_list.append(features)
                    # Label: 1 si acertó, 0 si no
                    y_list.append(1 if pred.get('was_correct') else 0)
            
            if not X_list:
                return None, None
            
            X = np.array(X_list, dtype=np.float32)
            y = np.array(y_list, dtype=np.int32)
            
            return X, y
            
        except Exception as e:
            logger.error(f"Error preparing training data: {e}")
            return None, None
    
    def _reconstruct_features(self, prediction: Dict) -> Optional[np.ndarray]:
        """Reconstruye features desde predicción guardada"""
        try:
            # Features básicas que guardamos
            odds = prediction.get('odds', 2.0)
            prob = prediction.get('predicted_prob', 0.5)
            
            # Crear feature vector simplificado
            # En producción ideal, guardarías todas las features
            features = np.zeros(self.feature_extractor.get_feature_count(), dtype=np.float32)
            
            # Llenar features disponibles
            features[0] = odds  # odds_home
            features[3] = prob  # implied_prob_home
            
            return features
            
        except Exception as e:
            logger.error(f"Error reconstructing features: {e}")
            return None
    
    def _train_xgboost(self, X_train, y_train, X_val, y_val):
        """Entrena modelo XGBoost con early stopping"""
        try:
            # Parámetros optimizados
            params = {
                'objective': 'binary:logistic',
                'eval_metric': ['logloss', 'auc'],
                'max_depth': 6,
                'learning_rate': 0.05,
                'n_estimators': 200,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'min_child_weight': 3,
                'gamma': 0.1,
                'reg_alpha': 0.1,
                'reg_lambda': 1.0,
                'random_state': 42,
                'n_jobs': -1,
                'verbosity': 0
            }
            
            model = xgb.XGBClassifier(**params)
            
            # Entrenar con early stopping
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
            
            return model
            
        except Exception as e:
            logger.error(f"Error training XGBoost: {e}")
            raise
    
    def _evaluate_model(self, model, X_test, y_test) -> Dict:
        """Evalúa modelo en conjunto de prueba"""
        try:
            # Predicciones
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)[:, 1]
            
            # Métricas
            accuracy = accuracy_score(y_test, y_pred)
            auc = roc_auc_score(y_test, y_pred_proba)
            logloss = log_loss(y_test, y_pred_proba)
            
            return {
                'accuracy': float(accuracy),
                'auc': float(auc),
                'log_loss': float(logloss)
            }
            
        except Exception as e:
            logger.error(f"Error evaluating model: {e}")
            return {}
    
    def train_all_sports(self, historical_db, sports: List[str]) -> Dict[str, Dict]:
        """Entrena modelos para todos los deportes con datos suficientes"""
        results = {}
        
        for sport in sports:
            logger.info(f"Training model for {sport}...")
            result = self.train_model(sport, historical_db)
            
            if result:
                results[sport] = result
            else:
                logger.warning(f"Skipped {sport} - insufficient data")
        
        logger.info(f"Training complete: {len(results)}/{len(sports)} models trained")
        return results
    
    def retrain_if_needed(self, sport_key: str, historical_db, 
                         days_since_last_train: int = 7) -> bool:
        """Re-entrena modelo si han pasado N días desde último entrenamiento"""
        try:
            model_path = self.models_dir / f"{sport_key}.joblib"
            
            # Verificar si existe y cuándo se modificó
            if model_path.exists():
                modified_time = datetime.fromtimestamp(model_path.stat().st_mtime, tz=timezone.utc)
                days_old = (datetime.now(timezone.utc) - modified_time).days
                
                if days_old < days_since_last_train:
                    logger.info(f"Model for {sport_key} is only {days_old} days old - skipping retrain")
                    return False
            
            # Re-entrenar
            logger.info(f"Retraining model for {sport_key}")
            result = self.train_model(sport_key, historical_db)
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Error checking retrain status: {e}")
            return False