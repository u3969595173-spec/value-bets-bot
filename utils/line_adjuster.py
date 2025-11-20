"""
utils/line_adjuster.py - Ajusta líneas cuando cuotas > 2.1 para mantener cuotas ≤ 2.0

Busca líneas alternativas más conservadoras en el mismo mercado y equipo.
"""

from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

MAX_ODD_THRESHOLD_STRICT = 2.1  # Threshold estricto (primera pasada)
MAX_ODD_THRESHOLD_RELAXED = 2.5  # Threshold relajado (fallback)
TARGET_ODD = 2.0  # Cuota objetivo para líneas ajustadas


def adjust_line_if_needed(candidate: Dict, event_bookmakers: List[Dict], use_relaxed: bool = False) -> Dict:
    """
    Ajusta línea si la cuota es > threshold, buscando alternativa más conservadora.
    
    Args:
        candidate: Diccionario del pick original
        event_bookmakers: Lista de bookmakers del evento con todos los mercados
        use_relaxed: Si True, usa threshold 2.5 en lugar de 2.1 (modo fallback)
        
    Returns:
        Diccionario con pick ajustado, original si no necesita ajuste, o None si debe rechazarse
    """
    original_odds = candidate.get('odds', 0)
    threshold = MAX_ODD_THRESHOLD_RELAXED if use_relaxed else MAX_ODD_THRESHOLD_STRICT
    
    # Si cuota <= threshold, no ajustar
    if original_odds <= threshold:
        return candidate
    
    logger.info(f"🔧 Ajustando línea: {candidate.get('selection')} @ {original_odds:.2f} (>2.1)")
    
    market_key = candidate.get('market_key')
    selection = candidate.get('selection', '')
    original_point = candidate.get('point')
    bookmaker_name = candidate.get('bookmaker', '')
    
    # Buscar líneas alternativas según tipo de mercado
    if market_key == 'spreads':
        adjusted = _find_adjusted_spread(candidate, event_bookmakers)
    elif market_key == 'totals':
        adjusted = _find_adjusted_total(candidate, event_bookmakers)
    else:
        # Para h2h no hay ajuste posible
        logger.info(f"⚠️ No se puede ajustar mercado {market_key}")
        return candidate
    
    if adjusted:
        # Marcar que fue ajustado
        adjusted['was_adjusted'] = True
        adjusted['original_odds'] = original_odds
        adjusted['original_point'] = original_point
        adjusted['adjustment_reason'] = f"Cuota original {original_odds:.2f} > {MAX_ODD_THRESHOLD}"
        
        logger.info(
            f"✅ Línea ajustada: {adjusted.get('selection')} "
            f"{adjusted.get('point')} @ {adjusted.get('odds'):.2f} "
            f"(original: {original_point} @ {original_odds:.2f})"
        )
        return adjusted
    else:
        mode_msg = f">{MAX_ODD_THRESHOLD_RELAXED}" if use_relaxed else f">{MAX_ODD_THRESHOLD_STRICT}"
        logger.warning(f"⚠️ No se encontró línea alternativa y odds {mode_msg}, RECHAZANDO pick")
        # Retornar None para que el pick sea filtrado
        return None


def _find_adjusted_spread(candidate: Dict, event_bookmakers: List[Dict]) -> Optional[Dict]:
    """
    Busca spread más conservador (menor handicap) con cuota cercana a 2.0
    
    Ejemplo: Lakers -10 @ 2.40 → Lakers -8 @ 2.00
    """
    selection = candidate.get('selection', '')
    original_point = candidate.get('point')
    market_key = candidate.get('market_key')
    
    if original_point is None:
        return None
    
    # Buscar en todos los bookmakers
    alternative_lines = []
    
    for bookmaker in event_bookmakers:
        for market in bookmaker.get('markets', []):
            if market.get('key') != 'spreads':
                continue
            
            for outcome in market.get('outcomes', []):
                outcome_name = outcome.get('name', '')
                
                # Debe ser mismo equipo
                if outcome_name.strip().lower() != selection.strip().lower():
                    continue
                
                outcome_point = outcome.get('point')
                outcome_odds = outcome.get('price')
                
                if outcome_point is None or outcome_odds is None:
                    continue
                
                # Buscar líneas más conservadoras
                # Si punto original es negativo (favorito): buscar menor valor absoluto
                # Si punto original es positivo (underdog): buscar mayor valor
                is_more_conservative = False
                
                if original_point < 0:  # Favorito
                    # -8 es más conservador que -10
                    is_more_conservative = outcome_point > original_point and outcome_point < 0
                else:  # Underdog
                    # +12 es más conservador que +10
                    is_more_conservative = outcome_point > original_point
                
                if is_more_conservative and outcome_odds <= TARGET_ODD + 0.15:
                    alternative_lines.append({
                        'selection': outcome_name,
                        'point': outcome_point,
                        'odds': outcome_odds,
                        'bookmaker': bookmaker.get('title', bookmaker.get('key')),
                        'market_key': market_key,
                        'distance_from_target': abs(outcome_odds - TARGET_ODD)
                    })
    
    if not alternative_lines:
        return None
    
    # Ordenar por cuota más cercana a TARGET_ODD (2.0)
    alternative_lines.sort(key=lambda x: x['distance_from_target'])
    best_line = alternative_lines[0]
    
    # Copiar datos originales y actualizar con nueva línea
    adjusted = candidate.copy()
    adjusted['point'] = best_line['point']
    adjusted['odds'] = best_line['odds']
    adjusted['bookmaker'] = best_line['bookmaker']
    
    return adjusted


def _find_adjusted_total(candidate: Dict, event_bookmakers: List[Dict]) -> Optional[Dict]:
    """
    Busca total más conservador con cuota cercana a 2.0
    
    Ejemplo: Over 220.5 @ 2.35 → Over 218.5 @ 2.00
    """
    selection = candidate.get('selection', '')
    original_point = candidate.get('point')
    market_key = candidate.get('market_key')
    
    if original_point is None:
        return None
    
    # Determinar dirección (Over/Under)
    is_over = 'over' in selection.lower()
    
    # Buscar en todos los bookmakers
    alternative_lines = []
    
    for bookmaker in event_bookmakers:
        for market in bookmaker.get('markets', []):
            if market.get('key') != 'totals':
                continue
            
            for outcome in market.get('outcomes', []):
                outcome_name = outcome.get('name', '')
                outcome_point = outcome.get('point')
                outcome_odds = outcome.get('price')
                
                if outcome_point is None or outcome_odds is None:
                    continue
                
                # Verificar que sea misma dirección
                outcome_is_over = 'over' in outcome_name.lower()
                if outcome_is_over != is_over:
                    continue
                
                # Buscar líneas más conservadoras
                # Para Over: buscar puntos menores (más fácil de pasar)
                # Para Under: buscar puntos mayores (más fácil de no pasar)
                is_more_conservative = False
                
                if is_over:
                    is_more_conservative = outcome_point < original_point
                else:
                    is_more_conservative = outcome_point > original_point
                
                if is_more_conservative and outcome_odds <= TARGET_ODD + 0.15:
                    alternative_lines.append({
                        'selection': outcome_name,
                        'point': outcome_point,
                        'odds': outcome_odds,
                        'bookmaker': bookmaker.get('title', bookmaker.get('key')),
                        'market_key': market_key,
                        'distance_from_target': abs(outcome_odds - TARGET_ODD)
                    })
    
    if not alternative_lines:
        return None
    
    # Ordenar por cuota más cercana a TARGET_ODD (2.0)
    alternative_lines.sort(key=lambda x: x['distance_from_target'])
    best_line = alternative_lines[0]
    
    # Copiar datos originales y actualizar con nueva línea
    adjusted = candidate.copy()
    adjusted['selection'] = best_line['selection']
    adjusted['point'] = best_line['point']
    adjusted['odds'] = best_line['odds']
    adjusted['bookmaker'] = best_line['bookmaker']
    
    return adjusted
