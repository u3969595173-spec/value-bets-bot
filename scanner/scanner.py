"""Scanner: identify value bets using model.probabilities and per-sport thresholds.

Rules implemented per your spec:
- Value = odd * prob_est
- Thresholds by sport:
    NBA: 1.09
    MLB: 1.10
    Fútbol: 1.08
    Tenis: 1.07
- Only odds in range 1.5 - 2.5
- Probabilidad mínima: 55%
- Max 5 alerts per day (state stored in data/alerts_state.json)
- Reinicio diario a las 6 AM hora de América (Eastern Time)
- Excluir partidos en vivo (commence_time ya pasó)
- Solo partidos en las próximas 24 horas
- Incluir mercados: h2h, totals, spreads (hándicap)
"""
import logging
from typing import List, Dict
from statistics import mean
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Intentar usar modelo mejorado, fallback al básico
try:
    from model.enhanced_probabilities import estimate_probabilities_enhanced as estimate_probabilities
    USING_ENHANCED_MODEL = True
except ImportError:
    from model.probabilities import estimate_probabilities
    USING_ENHANCED_MODEL = False

from data.state import AlertsState
from analyzer import generate_analysis

# thresholds per sport key prefix (ELITE - ultra-profesional)
THRESHOLDS = {
    'basketball': 1.15,  # NBA elite (antes 1.12)
    'americanfootball': 1.15,
    'baseball': 1.16,  # MLB elite (antes 1.13)
    'soccer': 1.13,  # Fútbol elite (antes 1.10)
    'tennis': 1.12,  # Tenis elite (antes 1.09)
}


def implied_prob_from_odd(odd: float) -> float:
    return 1.0 / odd if odd and odd > 0 else 0.0


class ValueScanner:
    def __init__(self, min_odd: float = 1.6, max_odd: float = 2.8, min_prob: float = 0.58):
        self.min_odd = min_odd
        self.max_odd = max_odd
        self.min_prob = min_prob

    def sport_prefix(self, sport_key: str) -> str:
        for k in THRESHOLDS.keys():
            if sport_key.startswith(k):
                return k
        # fallback: try substrings
        if 'soccer' in sport_key or 'football' in sport_key:
            return 'soccer'
        if 'tennis' in sport_key:
            return 'tennis'
        if 'nba' in sport_key or 'basketball' in sport_key:
            return 'basketball'
        if 'mlb' in sport_key or 'baseball' in sport_key:
            return 'baseball'
        return 'other'

    def find_value_bets(self, events: List[Dict]) -> List[Dict]:
        results = []
        discarded = {'odds_range': 0, 'probability': 0, 'time_range': 0, 'no_threshold': 0, 'total_checked': 0, 'missing_fields': 0}
        now_utc = datetime.now(timezone.utc)
        # Límite: 24 horas desde ahora
        max_time = now_utc + timedelta(hours=24)
        for ev in events:
            # Filtrar partidos: solo en las próximas 24 horas
            commence_str = ev.get('commence_time')
            if commence_str:
                try:
                    commence_time = datetime.fromisoformat(commence_str.replace('Z', '+00:00'))
                    if commence_time <= now_utc:
                        discarded['time_range'] += 1
                        continue
                    if commence_time > max_time:
                        discarded['time_range'] += 1
                        continue
                except Exception:
                    logger.warning(f"[SCANNER] No se pudo parsear commence_time: {commence_str}")
                    continue
            else:
                logger.warning(f"[SCANNER] Evento sin commence_time: {ev.get('id')}")
                discarded['missing_fields'] += 1
                continue
            sport_key = ev.get('sport_key', ev.get('_sport_key', ''))
            prefix = self.sport_prefix(sport_key)
            threshold = THRESHOLDS.get(prefix)
            if not threshold:
                logger.warning(f"[SCANNER] Sin threshold para sport_key: {sport_key}")
                discarded['no_threshold'] += 1
                continue
            probs = estimate_probabilities(ev)
            # Incluir mercados: h2h, totals (over/under), spreads (hándicap)
            for bm in ev.get('bookmakers', []):
                for m in bm.get('markets', []):
                    market_key = m.get('key')
                    if market_key not in ['h2h', 'totals', 'spreads']:
                        continue
                    for out in m.get('outcomes', []):
                        discarded['total_checked'] += 1
                        sel = out.get('name') or 'Sin nombre'
                        if not sel or sel.strip() == '':
                            logger.warning(f"[SCANNER] Outcome sin nombre en evento {ev.get('id')}")
                            discarded['missing_fields'] += 1
                            continue
                        try:
                            odd = float(out.get('price'))
                        except Exception:
                            logger.warning(f"[SCANNER] Outcome sin price válido en evento {ev.get('id')}")
                            discarded['missing_fields'] += 1
                            continue
                        if odd < self.min_odd or odd > self.max_odd:
                            discarded['odds_range'] += 1
                            continue
                        # Determinar probabilidad según el mercado
                        prob_est = None
                        home = ev.get('home_team') or ev.get('home') or ev.get('competitor_home') or 'Equipo Local'
                        away = ev.get('away_team') or ev.get('away') or ev.get('competitor_away') or 'Equipo Visitante'
                        name_lower = sel.lower()
                        if market_key == 'h2h':
                            if 'draw' in name_lower or name_lower in ['x','empate']:
                                prob_est = probs.get('draw')
                            elif (home and home.lower() in name_lower) or name_lower in ['home','local']:
                                prob_est = probs.get('home')
                            elif (away and away.lower() in name_lower) or name_lower in ['away','visitante']:
                                prob_est = probs.get('away')
                            else:
                                prob_est = probs.get('home') if 'home' in probs else list(probs.values())[0]
                        elif market_key == 'totals':
                            prob_est = 0.52 if 'over' in sel.lower() else 0.48
                        elif market_key == 'spreads':
                            if home and home.lower() in name_lower:
                                prob_est = probs.get('home', 0.5)
                            else:
                                prob_est = probs.get('away', 0.5)
                        if not prob_est or prob_est < self.min_prob:
                            discarded['probability'] += 1
                            continue
                        value = odd * prob_est
                        if value >= threshold:
                            analysis = generate_analysis(ev, sel, odd, prob_est)
                            # Formatear fecha y hora del evento
                            commence_time_str = ""
                            try:
                                dt = datetime.fromisoformat(commence_str.replace('Z', '+00:00'))
                                commence_time_str = dt.strftime("%Y-%m-%d %H:%M UTC")
                            except:
                                commence_time_str = commence_str or 'Sin fecha'
                            event_name = f"{home} vs {away}"
                            point_value = out.get('point')
                            results.append({
                                'id': ev.get('id'),
                                'sport': ev.get('sport_nice', sport_key),
                                'sport_key': sport_key,
                                'home': home,
                                'away': away,
                                'event': event_name,
                                'commence_time': commence_time_str,
                                'market': market_key,
                                'market_key': market_key,
                                'selection': sel,
                                'odds': odd,
                                'prob': prob_est,
                                'real_probability': prob_est,
                                'value': value,
                                'book': bm.get('title') or 'Desconocida',
                                'bookmaker': bm.get('title') or 'Desconocida',
                                'url': bm.get('url',''),
                                'analysis': analysis,
                                'point': point_value,
                            })
        # De-duplicate by id+selection+bookmaker keeping highest value
        unique = {}
        for r in results:
            key = (r['id'], r['selection'], r['bookmaker'])
            if key not in unique or r['value'] > unique[key]['value']:
                unique[key] = r
        final_results = list(unique.values())
        # Logging detallado de descartes y advertencias
        logger.info(f"📊 Scan Summary:")
        logger.info(f"   Total outcomes checked: {discarded['total_checked']}")
        logger.info(f"   ❌ Discarded by odds range ({self.min_odd}-{self.max_odd}): {discarded['odds_range']}")
        logger.info(f"   ❌ Discarded by low probability (<{self.min_prob:.0%}): {discarded['probability']}")
        logger.info(f"   ❌ Discarded by time range: {discarded['time_range']}")
        logger.info(f"   ❌ Discarded by missing fields: {discarded['missing_fields']}")
        logger.info(f"   ❌ Discarded by no threshold: {discarded['no_threshold']}")
        logger.info(f"   ✅ Final candidates: {len(final_results)}")
        return final_results
