"""
scanner/enhanced_scanner.py - Scanner mejorado con análisis de line movement

Combina value betting tradicional con detección de steam moves y RLM
para identificar las mejores oportunidades.
"""
import logging
from typing import List, Dict
from scanner.scanner import ValueScanner
from analytics.line_movement import line_tracker

logger = logging.getLogger(__name__)


class EnhancedValueScanner(ValueScanner):
    """Scanner de value bets mejorado con análisis de movimiento de líneas"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.line_tracker = line_tracker
    
    def adjust_candidate_odds(self, candidate: Dict, all_candidates: List[Dict]) -> Dict:
        """
        Si la cuota es >2.1, busca en el mismo partido y mercado una alternativa entre 1.7 y 1.9.
        Si la encuentra, retorna esa alternativa; si no, retorna el original.
        """
        odds = candidate.get('odds', 0)
        if odds <= 2.1:
            return candidate
        # Buscar alternativas en el mismo partido y mercado
        event_id = candidate.get('id')
        market_key = candidate.get('market_key')
        # Buscar en all_candidates (ya escaneados)
        alternatives = [c for c in all_candidates
                        if c.get('id') == event_id and c.get('market_key') == market_key
                        and 1.7 <= c.get('odds', 0) <= 1.9]
        if alternatives:
            # Elegir la de mayor valor
            return max(alternatives, key=lambda x: x.get('value', 0))
        return candidate
    
    def find_value_bets_with_movement(self, events: List[Dict]) -> List[Dict]:
        """
        Encuentra value bets considerando movimiento de líneas.
        
        Prioriza oportunidades con:
        - Value tradicional (cuota × prob ≥ threshold)
        - Mejora en cuotas (RLM - sharp action)
        - Steam moves indicando acción profesional
        
        Returns:
            Lista de value bets con información de line movement
        """
        try:
            # Obtener candidatos base usando scanner tradicional
            candidates = self.find_value_bets(events)
            
            if not candidates:
                return []
            
            # Enriquecer con información de line movement y ajustar cuotas si es necesario
            enhanced_candidates = []
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
                    confidence_score = self._calculate_confidence(candidate, movement)
                    candidate['confidence_score'] = confidence_score
                    candidate['confidence_level'] = self._confidence_level(confidence_score)
                    timing = self.line_tracker.get_best_odds_timing(event_id, selection)
                    candidate['timing_recommendation'] = timing.get('recommendation', 'unknown')
                    steam_moves = self.line_tracker.detect_steam_moves(event_id)
                    candidate['has_steam_move'] = any(
                        sm['selection'] == selection for sm in steam_moves
                    )
                else:
                    candidate['line_movement'] = None
                    candidate['confidence_score'] = 50
                    candidate['confidence_level'] = 'medium'
                    candidate['timing_recommendation'] = 'insufficient_data'
                    candidate['has_steam_move'] = False
                # Ajustar cuota si corresponde
                adjusted = self.adjust_candidate_odds(candidate, candidates)
                enhanced_candidates.append(adjusted)
            enhanced_candidates.sort(key=lambda x: x.get('confidence_score', 0), reverse=True)
            logger.info(f"Enhanced scan: {len(enhanced_candidates)} candidates with movement analysis")
            return enhanced_candidates
            
        except Exception as e:
            logger.error(f"Error in enhanced scanning: {e}")
            # Fallback a scanner tradicional
            return self.find_value_bets(events)
    
    def _calculate_confidence(self, candidate: Dict, movement: Dict) -> float:
        """
        Calcula score de confianza (0-100) basado en múltiples factores.
        
        Factores:
        - Value score (cuota × prob): 30 puntos
        - Mejora en cuotas (RLM): 25 puntos
        - Tendencia favorable: 20 puntos
        - Tiempo desde apertura: 15 puntos
        - Probabilidad estimada: 10 puntos
        """
        try:
            score = 0.0
            
            # Factor 1: Value score (30 puntos máx)
            value = candidate.get('value', 1.0)
            threshold = 1.09  # Promedio de thresholds
            if value >= threshold:
                value_excess = value - threshold
                score += min(30, value_excess * 100)  # Escalar proporcionalmente
            
            # Factor 2: Mejora en cuotas - RLM (25 puntos máx)
            if movement.get('is_favorable'):
                change_percent = movement.get('change_percent', 0)
                if change_percent > 0:
                    score += min(25, change_percent * 5)  # 5% = 25 puntos
            
            # Factor 3: Tendencia favorable (20 puntos)
            trend = movement.get('trend', 'unknown')
            if trend == 'drifting':  # Cuotas subiendo
                score += 20
            elif trend == 'stable':
                score += 10
            elif trend == 'shortening':  # Cuotas bajando
                score += 5
            
            # Factor 4: Tiempo de tracking (15 puntos máx)
            time_span = movement.get('time_span_hours', 0)
            if time_span >= 2:  # Al menos 2 horas de datos
                score += min(15, time_span * 3)
            
            # Factor 5: Probabilidad alta (10 puntos máx)
            prob = candidate.get('prob', 0.5)
            if prob >= 0.65:
                score += 10
            elif prob >= 0.60:
                score += 7
            elif prob >= 0.55:
                score += 5
            
            return min(100, score)  # Cap a 100
            
        except Exception as e:
            logger.error(f"Error calculating confidence: {e}")
            return 50.0
    
    def _confidence_level(self, score: float) -> str:
        """Convierte score numérico a nivel textual"""
        if score >= 75:
            return 'very_high'
        elif score >= 60:
            return 'high'
        elif score >= 45:
            return 'medium'
        else:
            return 'low'
    
    def filter_by_confidence(self, candidates: List[Dict], min_level: str = 'medium') -> List[Dict]:
        """
        Filtra candidatos por nivel mínimo de confianza.
        
        Args:
            candidates: Lista de candidatos
            min_level: 'very_high', 'high', 'medium', 'low'
            
        Returns:
            Candidatos filtrados
        """
        level_order = ['low', 'medium', 'high', 'very_high']
        min_index = level_order.index(min_level) if min_level in level_order else 1
        
        return [
            c for c in candidates
            if level_order.index(c.get('confidence_level', 'low')) >= min_index
        ]
