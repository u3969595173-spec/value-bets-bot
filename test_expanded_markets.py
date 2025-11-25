"""Test script para verificar los mercados expandidos (quarters, halves, player props)"""

import asyncio
from data.odds_api import OddsFetcher
from scanner.scanner import ValueScanner
from utils.sport_translator import translate_market, translate_sport
from notifier.alert_formatter import get_market_info
import os

# Usar API key de entorno
API_KEY = os.getenv('THEODDS_API_KEY') or os.getenv('API_KEY')

async def test_expanded_markets():
    """Test que los mercados expandidos funcionan correctamente"""
    
    print("=" * 80)
    print("TEST: MERCADOS EXPANDIDOS (Quarters, Halves, Player Props)")
    print("=" * 80)
    print()
    
    # 1. Test de traducciones
    print("1. TRADUCCIONES DE MERCADOS:")
    print("-" * 40)
    test_markets = [
        'h2h', 'spreads', 'totals',
        'h2h_q1', 'h2h_q2', 'totals_q1', 'spreads_h1',
        'player_points', 'player_assists', 'player_rebounds'
    ]
    for market in test_markets:
        translation = translate_market(market)
        print(f"   {market:20s} -> {translation}")
    print()
    
    # 2. Test de formateo de alertas
    print("2. FORMATEO DE ALERTAS:")
    print("-" * 40)
    
    # Test quarter market
    test_candidate_q1 = {
        'market_key': 'h2h_q1',
        'selection': 'Los Angeles Lakers',
        'point': None,
        'odds': 1.95
    }
    info = get_market_info(
        test_candidate_q1['market_key'],
        test_candidate_q1['selection'],
        test_candidate_q1['point'],
        test_candidate_q1['odds']
    )
    print("   Mercado: 1er Cuarto (h2h_q1)")
    print(f"   Tipo: {info['type']}")
    print(f"   Descripción: {info['description']}")
    print(f"   Detalles: {info['details']}")
    print()
    
    # Test totals half
    test_candidate_h1 = {
        'market_key': 'totals_h1',
        'selection': 'Over 110.5',
        'point': 110.5,
        'odds': 1.85
    }
    info = get_market_info(
        test_candidate_h1['market_key'],
        test_candidate_h1['selection'],
        test_candidate_h1['point'],
        test_candidate_h1['odds']
    )
    print("   Mercado: Total 1era Mitad (totals_h1)")
    print(f"   Tipo: {info['type']}")
    print(f"   Descripción: {info['description']}")
    print(f"   Detalles: {info['details']}")
    print()
    
    # Test player prop
    test_candidate_player = {
        'market_key': 'player_points',
        'selection': 'LeBron James - Over 25.5',
        'point': 25.5,
        'odds': 1.83
    }
    info = get_market_info(
        test_candidate_player['market_key'],
        test_candidate_player['selection'],
        test_candidate_player['point'],
        test_candidate_player['odds']
    )
    print("   Mercado: Puntos del Jugador (player_points)")
    print(f"   Tipo: {info['type']}")
    print(f"   Descripción: {info['description']}")
    print(f"   Detalles: {info['details']}")
    print()
    
    # 3. Test de API (solo si hay API key)
    if API_KEY:
        print("3. TEST DE API (MERCADOS REALES):")
        print("-" * 40)
        print("   Consultando The Odds API con mercados expandidos...")
        
        fetcher = OddsFetcher(api_key=API_KEY)
        # Probar solo con NBA primero
        events = await fetcher.fetch_odds(['basketball_nba'])
        
        if events:
            print(f"   ✅ {len(events)} eventos obtenidos")
            
            # Verificar que hay mercados expandidos
            expanded_markets_found = set()
            for event in events[:3]:  # Revisar primeros 3 eventos
                for bookmaker in event.get('bookmakers', []):
                    for market in bookmaker.get('markets', []):
                        market_key = market.get('key', '')
                        if market_key not in ['h2h', 'spreads', 'totals']:
                            expanded_markets_found.add(market_key)
            
            if expanded_markets_found:
                print(f"   ✅ Mercados expandidos encontrados: {', '.join(sorted(expanded_markets_found))}")
            else:
                print("   ⚠️  No se encontraron mercados expandidos (puede ser normal si no hay eventos activos)")
            
            # Test del scanner con mercados expandidos
            print()
            print("4. TEST DEL SCANNER:")
            print("-" * 40)
            scanner = ValueScanner(min_odd=1.5, max_odd=3.0, min_prob=0.50)
            candidates = scanner.find_value_bets(events)
            
            print(f"   Total candidatos encontrados: {len(candidates)}")
            
            # Contar por tipo de mercado
            market_counts = {}
            for c in candidates:
                mk = c.get('market_key', 'unknown')
                market_counts[mk] = market_counts.get(mk, 0) + 1
            
            print("   Distribución por mercado:")
            for mk, count in sorted(market_counts.items()):
                print(f"      {mk:20s}: {count} picks")
            
            # Mostrar ejemplos de mercados expandidos
            expanded_picks = [c for c in candidates if c.get('market_key', '') not in ['h2h', 'spreads', 'totals']]
            if expanded_picks:
                print()
                print("   📊 EJEMPLOS DE PICKS CON MERCADOS EXPANDIDOS:")
                for pick in expanded_picks[:3]:
                    mk = pick.get('market_key', '')
                    sel = pick.get('selection', '')
                    odds = pick.get('odds', 0)
                    value = pick.get('value', 0)
                    print(f"      • {translate_market(mk)}: {sel} @ {odds:.2f} (valor: {value:.3f})")
        else:
            print("   ⚠️  No se obtuvieron eventos de la API")
    else:
        print("3. TEST DE API:")
        print("-" * 40)
        print("   ⚠️  No hay API key configurada. Saltando test de API real.")
    
    print()
    print("=" * 80)
    print("TEST COMPLETADO")
    print("=" * 80)

if __name__ == '__main__':
    asyncio.run(test_expanded_markets())
