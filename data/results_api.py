"""
results_api.py - Obtiene resultados finales de partidos para verificar picks

Usa The Odds API endpoint /sports/{sport}/scores (GRATIS, no gasta créditos)
"""

import os
import requests
import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"


def get_game_scores(sport: str, days_from: int = 1) -> List[Dict]:
    """
    Obtiene scores finales de partidos completados
    
    Args:
        sport: Clave del deporte (basketball_nba, soccer_epl, etc)
        days_from: Días hacia atrás para buscar (default 1)
        
    Returns:
        Lista de eventos con scores finales
    """
    if not API_KEY:
        logger.warning("No API_KEY - cannot fetch scores")
        return []
    
    url = f"{BASE_URL}/sports/{sport}/scores/"
    params = {
        'apiKey': API_KEY,
        'daysFrom': days_from
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Fetched {len(data)} scores for {sport}")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching scores for {sport}: {e}")
        return []


def verify_pick_result(event_id: str, sport: str, pick_type: str, 
                       selection: str, point: Optional[float] = None) -> Optional[str]:
    """
    Verifica si un pick ganó o perdió
    
    Args:
        event_id: ID del evento
        sport: Deporte
        pick_type: Tipo de mercado (h2h, spreads, totals)
        selection: Selección apostada
        point: Punto del spread/total (si aplica)
        
    Returns:
        'won', 'lost', 'push', None (si no hay resultado aún)
    """
    scores = get_game_scores(sport, days_from=3)
    
    # Buscar el evento
    event = next((e for e in scores if e['id'] == event_id), None)
    if not event:
        logger.debug(f"Event {event_id} not found in scores")
        return None
    
    # Verificar que el evento terminó
    if not event.get('completed', False):
        logger.debug(f"Event {event_id} not completed yet")
        return None
    
    scores_data = event.get('scores')
    if not scores_data or len(scores_data) < 2:
        logger.warning(f"Event {event_id} missing scores data")
        return None
    
    home_team = event['home_team']
    away_team = event['away_team']
    home_score = int(scores_data[0]['score'])
    away_score = int(scores_data[1]['score'])
    
    logger.info(f"Verifying: {away_team} @ {home_team} = {away_score}-{home_score}")
    
    # Verificar según tipo de pick
    if pick_type == 'h2h':
        # Moneyline (ganador directo)
        if selection == home_team:
            return 'won' if home_score > away_score else 'lost'
        elif selection == away_team:
            return 'won' if away_score > home_score else 'lost'
    
    elif pick_type == 'spreads':
        # Point spread
        if point is None:
            logger.error("Spread pick missing point value")
            return None
        
        if selection == home_team:
            # Home team con spread
            adjusted_score = home_score + point
            if adjusted_score > away_score:
                return 'won'
            elif adjusted_score < away_score:
                return 'lost'
            else:
                return 'push'
        elif selection == away_team:
            # Away team con spread
            adjusted_score = away_score + point
            if adjusted_score > home_score:
                return 'won'
            elif adjusted_score < home_score:
                return 'lost'
            else:
                return 'push'
    
    elif pick_type == 'totals':
        # Over/Under
        if point is None:
            logger.error("Totals pick missing point value")
            return None
        
        total_score = home_score + away_score
        
        if selection.lower() == 'over':
            if total_score > point:
                return 'won'
            elif total_score < point:
                return 'lost'
            else:
                return 'push'
        elif selection.lower() == 'under':
            if total_score < point:
                return 'won'
            elif total_score > point:
                return 'lost'
            else:
                return 'push'
    
    logger.warning(f"Could not verify pick: type={pick_type}, selection={selection}")
    return None


def get_event_status(event_id: str, sport: str) -> Optional[Dict]:
    """
    Obtiene el estado de un evento específico
    
    Returns:
        Dict con completed, scores, etc. o None si no encontrado
    """
    scores = get_game_scores(sport, days_from=3)
    event = next((e for e in scores if e['id'] == event_id), None)
    
    if event:
        return {
            'event_id': event_id,
            'completed': event.get('completed', False),
            'home_team': event['home_team'],
            'away_team': event['away_team'],
            'scores': event.get('scores', [])
        }
    
    return None


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    # Obtener scores recientes de NBA
    scores = get_game_scores("basketball_nba", days_from=1)
    print(f"\nFound {len(scores)} completed NBA games")
    
    if scores:
        event = scores[0]
        print(f"\nExample game:")
        print(f"  {event['away_team']} @ {event['home_team']}")
        print(f"  Score: {event['scores'][1]['score']}-{event['scores'][0]['score']}")
        print(f"  Completed: {event['completed']}")
