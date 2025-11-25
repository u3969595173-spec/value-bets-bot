"""
utils/sport_translator.py - Traduce nombres de deportes al español.
"""

SPORT_TRANSLATIONS = {
    # Basketball
    'basketball_nba': 'Baloncesto (NBA)',
    'basketball_euroleague': 'Baloncesto (Euroliga)',
    'basketball_ncaab': 'Baloncesto (NCAA)',
    'basketball_spain_acb': 'Baloncesto (ACB)',
    'basketball_france_lnb': 'Baloncesto (LNB)',
    'basketball_germany_bbl': 'Baloncesto (BBL)',
    'basketball_italy_lega_a': 'Baloncesto (Lega A)',
    'basketball': 'Baloncesto',
    
    # American Football
    'americanfootball_nfl': 'Fútbol Americano (NFL)',
    'americanfootball_ncaaf': 'Fútbol Americano (NCAA)',
    'americanfootball': 'Fútbol Americano',
    
    # Baseball
    'baseball_mlb': 'Béisbol (MLB)',
    'baseball': 'Béisbol',
    
    # Soccer
    'soccer_epl': 'Fútbol (Premier League)',
    'soccer_spain_la_liga': 'Fútbol (La Liga)',
    'soccer_germany_bundesliga': 'Fútbol (Bundesliga)',
    'soccer_italy_serie_a': 'Fútbol (Serie A)',
    'soccer_france_ligue_one': 'Fútbol (Ligue 1)',
    'soccer_uefa_champs_league': 'Fútbol (Champions)',
    'soccer_uefa_europa_league': 'Fútbol (Europa League)',
    'soccer_efl_champ': 'Fútbol (Championship)',
    'soccer_spain_la_liga2': 'Fútbol (La Liga 2)',
    'soccer': 'Fútbol',
    
    # Tennis
    'tennis_atp': 'Tenis (ATP)',
    'tennis_wta': 'Tenis (WTA)',
    'tennis': 'Tenis',
    
    # Cricket
    'cricket_international': 'Cricket (Internacional)',
    'cricket_big_bash': 'Cricket (Big Bash)',
    'cricket_ipl': 'Cricket (IPL)',
    'cricket_test_match': 'Cricket (Test Match)',
    'cricket': 'Cricket',
}


# Traducciones de mercados
MARKET_TRANSLATIONS = {
    # Mercados básicos
    'h2h': 'Ganador',
    'spreads': 'Hándicap',
    'totals': 'Total Puntos',
    
    # Quarters (cuartos)
    'h2h_q1': 'Ganador 1er Cuarto',
    'h2h_q2': 'Ganador 2do Cuarto',
    'h2h_q3': 'Ganador 3er Cuarto',
    'h2h_q4': 'Ganador 4to Cuarto',
    'spreads_q1': 'Hándicap 1er Cuarto',
    'spreads_q2': 'Hándicap 2do Cuarto',
    'spreads_q3': 'Hándicap 3er Cuarto',
    'spreads_q4': 'Hándicap 4to Cuarto',
    'totals_q1': 'Total 1er Cuarto',
    'totals_q2': 'Total 2do Cuarto',
    'totals_q3': 'Total 3er Cuarto',
    'totals_q4': 'Total 4to Cuarto',
    
    # Halves (mitades)
    'h2h_h1': 'Ganador 1era Mitad',
    'h2h_h2': 'Ganador 2da Mitad',
    'spreads_h1': 'Hándicap 1era Mitad',
    'spreads_h2': 'Hándicap 2da Mitad',
    'totals_h1': 'Total 1era Mitad',
    'totals_h2': 'Total 2da Mitad',
    
    # Player props (estadísticas de jugadores)
    'player_points': 'Puntos del Jugador',
    'player_assists': 'Asistencias del Jugador',
    'player_rebounds': 'Rebotes del Jugador',
    'player_pass_tds': 'TDs de Pase del Jugador',
    'player_rush_yds': 'Yardas Terrestres del Jugador',
    'player_receptions': 'Recepciones del Jugador',
    'player_pass_yds': 'Yardas de Pase del Jugador',
    'player_rush_attempts': 'Intentos Terrestres del Jugador',
}

def translate_sport(sport_key: str, sport_nice: str = None) -> str:
    """
    Traduce el nombre del deporte al español.
    
    Args:
        sport_key: Clave del deporte (ej: 'basketball_nba')
        sport_nice: Nombre legible opcional de la API
    
    Returns:
        Nombre del deporte en español
    """
    # Intentar traducción exacta primero
    if sport_key in SPORT_TRANSLATIONS:
        return SPORT_TRANSLATIONS[sport_key]
    
    # Intentar por prefijo
    for key, translation in SPORT_TRANSLATIONS.items():
        if sport_key.startswith(key):
            return translation
    
    # Fallback a sport_nice si existe
    if sport_nice:
        return sport_nice
    
    # Último fallback: capitalizar sport_key
    return sport_key.replace('_', ' ').title()

def translate_market(market_key: str) -> str:
    """
    Traduce el tipo de mercado al español.
    
    Args:
        market_key: Clave del mercado (ej: 'h2h_q1', 'player_points')
    
    Returns:
        Nombre del mercado en español
    """
    return MARKET_TRANSLATIONS.get(market_key, market_key.replace('_', ' ').title())
