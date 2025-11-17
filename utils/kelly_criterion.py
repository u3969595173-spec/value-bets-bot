"""
utils/kelly_criterion.py - Kelly Criterion para sizing óptimo

Calcula el tamaño óptimo de apuesta basado en edge y odds.
Maximiza crecimiento a largo plazo minimizando riesgo de ruina.
"""
import logging
import math
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class KellyCriterion:
    """
    Calculadora de Kelly Criterion para bankroll management óptimo.
    
    Kelly Formula:
    f* = (bp - q) / b
    
    Donde:
    - f* = fracción del bankroll a apostar
    - b = odds decimales - 1
    - p = probabilidad de ganar
    - q = probabilidad de perder (1 - p)
    """
    
    def __init__(self, kelly_fraction: float = 0.25):
        """
        Args:
            kelly_fraction: Fracción de Kelly a usar (0.25 = Quarter Kelly)
                           - 1.0 = Full Kelly (óptimo matemático, volatilidad alta)
                           - 0.5 = Half Kelly (buen balance)
                           - 0.25 = Quarter Kelly (conservador, recomendado)
        """
        self.kelly_fraction = kelly_fraction
        logger.info(f" Kelly Criterion initialized: {kelly_fraction:.0%} Kelly")
    
    def calculate_stake(self, bankroll: float, odds: float, probability: float,
                       confidence_multiplier: float = 1.0) -> Dict:
        """
        Calcula stake óptimo usando Kelly Criterion.
        
        Args:
            bankroll: Bankroll total disponible
            odds: Cuota decimal (e.g., 2.10)
            probability: Probabilidad estimada de victoria (0-1)
            confidence_multiplier: Ajuste por confidence score (0.5-1.5)
            
        Returns:
            Dict con stake_amount, stake_pct, kelly_pct, edge, etc.
        """
        try:
            # Validar inputs
            if not self._validate_inputs(bankroll, odds, probability):
                return self._get_zero_stake()
            
            # Calcular Kelly
            kelly_pct = self._calculate_kelly(odds, probability)
            
            # Ajustar por confianza
            adjusted_kelly = kelly_pct * confidence_multiplier
            
            # Aplicar fracción de Kelly (Quarter Kelly por default)
            final_kelly = adjusted_kelly * self.kelly_fraction
            
            # Aplicar límites de seguridad
            final_kelly = self._apply_safety_limits(final_kelly, probability)
            
            # Calcular cantidad en dinero
            stake_amount = bankroll * final_kelly
            
            # Calcular edge
            edge = (odds * probability) - 1.0
            
            # Categorizar el tamaño
            size_category = self._categorize_stake(final_kelly)
            
            return {
                'stake_amount': round(stake_amount, 2),
                'stake_pct': round(final_kelly * 100, 2),
                'full_kelly_pct': round(kelly_pct * 100, 2),
                'edge': round(edge * 100, 2),
                'expected_value': round(stake_amount * edge, 2),
                'size_category': size_category,
                'recommendation': self._get_recommendation(final_kelly, edge),
                'risk_level': self._assess_risk(final_kelly, odds, probability)
            }
            
        except Exception as e:
            logger.error(f"Error calculating Kelly stake: {e}")
            return self._get_zero_stake()
    
    def _calculate_kelly(self, odds: float, probability: float) -> float:
        """
        Calcula Full Kelly percentage.
        
        Formula: f* = (bp - q) / b
        """
        b = odds - 1.0  # Profit per unit staked
        p = probability
        q = 1.0 - p
        
        kelly = (b * p - q) / b
        
        return max(0.0, kelly)  # No apostar si Kelly < 0
    
    def _validate_inputs(self, bankroll: float, odds: float, probability: float) -> bool:
        """Valida inputs"""
        if bankroll <= 0:
            logger.warning("Invalid bankroll: must be > 0")
            return False
        
        if odds < 1.01:
            logger.warning(f"Invalid odds: {odds} (must be >= 1.01)")
            return False
        
        if not (0 < probability < 1):
            logger.warning(f"Invalid probability: {probability} (must be 0-1)")
            return False
        
        # Verificar edge positivo
        edge = (odds * probability) - 1.0
        if edge <= 0:
            logger.debug(f"No positive edge: {edge:.2%}")
            return False
        
        return True
    
    def _apply_safety_limits(self, kelly_pct: float, probability: float) -> float:
        """Aplica límites de seguridad para proteger bankroll"""
        
        # Límite absoluto: nunca más del 10% del bankroll
        kelly_pct = min(kelly_pct, 0.10)
        
        # Si probabilidad < 55%, reducir stake
        if probability < 0.55:
            kelly_pct *= 0.7
        
        # Si probabilidad muy baja (<50%), no apostar
        if probability < 0.50:
            return 0.0
        
        # Mínimo: 0.5% del bankroll
        if kelly_pct > 0 and kelly_pct < 0.005:
            kelly_pct = 0.005
        
        return kelly_pct
    
    def _categorize_stake(self, kelly_pct: float) -> str:
        """Categoriza el tamaño de la apuesta"""
        if kelly_pct >= 0.08:
            return 'max_bet'
        elif kelly_pct >= 0.05:
            return 'large'
        elif kelly_pct >= 0.03:
            return 'medium'
        elif kelly_pct >= 0.01:
            return 'small'
        else:
            return 'minimal'
    
    def _get_recommendation(self, kelly_pct: float, edge: float) -> str:
        """Genera recomendación textual"""
        if kelly_pct == 0:
            return "Pass - No edge"
        elif kelly_pct >= 0.08:
            return f"Strong bet - {edge:.1f}% edge"
        elif kelly_pct >= 0.05:
            return f"Good opportunity - {edge:.1f}% edge"
        elif kelly_pct >= 0.03:
            return f"Moderate value - {edge:.1f}% edge"
        else:
            return f"Small edge - {edge:.1f}%"
    
    def _assess_risk(self, kelly_pct: float, odds: float, probability: float) -> str:
        """Evalúa nivel de riesgo"""
        # Risk aumenta con odds altas y baja probabilidad
        risk_score = (odds - 1.0) * (1.0 - probability) * kelly_pct
        
        if risk_score < 0.02:
            return 'low'
        elif risk_score < 0.05:
            return 'medium'
        else:
            return 'high'
    
    def _get_zero_stake(self) -> Dict:
        """Retorna stake cero cuando no hay edge"""
        return {
            'stake_amount': 0.0,
            'stake_pct': 0.0,
            'full_kelly_pct': 0.0,
            'edge': 0.0,
            'expected_value': 0.0,
            'size_category': 'no_bet',
            'recommendation': 'Pass - No positive edge',
            'risk_level': 'none'
        }
    
    def calculate_optimal_bankroll_allocation(self, opportunities: list,
                                             total_bankroll: float) -> Dict:
        """
        Calcula distribución óptima del bankroll entre múltiples oportunidades.
        
        Previene over-allocation cuando hay muchas apuestas simultáneas.
        
        Args:
            opportunities: Lista de dicts con {odds, probability, confidence}
            total_bankroll: Bankroll total disponible
            
        Returns:
            Dict con allocations por oportunidad y métricas totales
        """
        try:
            if not opportunities:
                return {'allocations': [], 'total_pct': 0.0}
            
            # Calcular Kelly para cada oportunidad
            allocations = []
            total_kelly = 0.0
            
            for opp in opportunities:
                stake_info = self.calculate_stake(
                    bankroll=total_bankroll,
                    odds=opp.get('odds'),
                    probability=opp.get('probability'),
                    confidence_multiplier=opp.get('confidence', 1.0)
                )
                
                allocations.append({
                    'opportunity': opp,
                    'stake': stake_info
                })
                
                total_kelly += stake_info['stake_pct'] / 100.0
            
            # Si allocation total > 20%, reducir proporcionalmente
            if total_kelly > 0.20:
                reduction_factor = 0.20 / total_kelly
                logger.warning(f"Over-allocation detected: {total_kelly:.1%}. Reducing by {reduction_factor:.2f}x")
                
                for alloc in allocations:
                    alloc['stake']['stake_amount'] *= reduction_factor
                    alloc['stake']['stake_pct'] *= reduction_factor
                
                total_kelly = 0.20
            
            return {
                'allocations': allocations,
                'total_pct': round(total_kelly * 100, 2),
                'count': len(allocations),
                'safety_status': 'safe' if total_kelly <= 0.20 else 'reduced'
            }
            
        except Exception as e:
            logger.error(f"Error calculating bankroll allocation: {e}")
            return {'allocations': [], 'total_pct': 0.0}


# Instancia global con Quarter Kelly (conservador)
kelly_calculator = KellyCriterion(kelly_fraction=0.25)