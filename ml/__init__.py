"""
ml/__init__.py - Sistema de Machine Learning para predicciones mejoradas

Componentes:
- FeatureExtractor: Extrae features de eventos para ML
- MLPredictor: Motor de predicciones con XGBoost
- ModelTrainer: Entrenamiento y actualización de modelos
"""
from .feature_extractor import FeatureExtractor
from .ml_predictor import MLPredictor
from .model_trainer import ModelTrainer

__all__ = ['FeatureExtractor', 'MLPredictor', 'ModelTrainer']
