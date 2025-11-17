"""
analytics/clv_tracker.py - Closing Line Value Tracker

Mide la calidad de las predicciones comparando cuotas apostadas vs cuotas de cierre.
CLV positivo = predictor exitoso, independiente del resultado.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from data.historical_db import historical_db

logger = logging.getLogger(__name__)


class CLVTracker:
    """
    Rastrea Closing Line Value para medir calidad predictiva.
    
    CLV es la métrica #1 de value bettors profesionales:
    - CLV > 0: Apuestas a mejor precio que el cierre (Sharp)
    - CLV = 0: Igual al cierre (Promedio)  
    - CLV < 0: Peor que el cierre (Recreational)
    
    Objetivo: CLV promedio > +3%
    """
    
    def __init__(self):
        self.clv_cache = {}  # event_id -> {opening_odds, closing_odds, clv}
    
    def record_opening_odds(self, event_id: str, selection: str, odds: float, 
                           timestamp: Optional[datetime] = None):
        """
        Registra cuotas en el momento de la apuesta.
        
        Args:
            event_id: ID del evento
            selection: Selección apostada
            odds: Cuota en momento de apuesta
            timestamp: Momento del registro (default: ahora)
        """
        try:
            if timestamp is None:
                timestamp = datetime.now(timezone.utc)
            
            key = f"{event_id}_{selection}"
            
            # Guardar en caché
            self.clv_cache[key] = {
                'event_id': event_id,
                'selection': selection,
                'opening_odds': odds,
                'opening_timestamp': timestamp.isoformat(),
                'closing_odds': None,
                'clv': None
            }
            
            # Guardar en BD
            data = {
                'event_id': event_id,
                'selection': selection,
                'opening_odds': odds,
                'opening_timestamp': timestamp.isoformat(),
                'created_at': timestamp.isoformat()
            }
            
            historical_db.supabase.table('clv_tracking').insert(data).execute()
            
            logger.debug(f" Recorded opening odds: {selection} @ {odds:.2f}")
            
        except Exception as e:
            logger.error(f"Error recording opening odds: {e}")
    
    def record_closing_odds(self, event_id: str, selection: str, odds: float,
                           minutes_before_start: int = 5):
        """
        Registra cuotas de cierre (5 min antes del partido).
        
        Args:
            event_id: ID del evento
            selection: Selección
            odds: Cuota de cierre
            minutes_before_start: Minutos antes del inicio
        """
        try:
            key = f"{event_id}_{selection}"
            
            # Calcular CLV si tenemos opening odds
            if key in self.clv_cache:
                opening_odds = self.clv_cache[key]['opening_odds']
                clv = self._calculate_clv(opening_odds, odds)
                
                self.clv_cache[key]['closing_odds'] = odds
                self.clv_cache[key]['clv'] = clv
                
                # Actualizar en BD
                historical_db.supabase.table('clv_tracking') \
                    .update({
                        'closing_odds': odds,
                        'clv': clv,
                        'minutes_before_start': minutes_before_start,
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }) \
                    .eq('event_id', event_id) \
                    .eq('selection', selection) \
                    .execute()
                
                logger.info(f" CLV: {selection} | Open: {opening_odds:.2f}  Close: {odds:.2f} | CLV: {clv:+.2%}")
            else:
                logger.warning(f"No opening odds found for {event_id}_{selection}")
                
        except Exception as e:
            logger.error(f"Error recording closing odds: {e}")
    
    def _calculate_clv(self, opening_odds: float, closing_odds: float) -> float:
        """
        Calcula Closing Line Value.
        
        CLV = (closing_odds - opening_odds) / opening_odds
        
        Ejemplo:
        - Apostaste @ 2.10, cierre @ 2.00  CLV = -4.76% (malo)
        - Apostaste @ 2.10, cierre @ 2.25  CLV = +7.14% (excelente)
        """
        return (closing_odds - opening_odds) / opening_odds
    
    def get_clv_stats(self, days: int = 30) -> Dict:
        """
        Obtiene estadísticas de CLV de los últimos N días.
        
        Returns:
            Dict con métricas: avg_clv, positive_rate, total_bets, etc.
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Obtener datos de BD
            response = historical_db.supabase.table('clv_tracking') \
                .select('*') \
                .gte('created_at', cutoff.isoformat()) \
                .not_.is_('clv', 'null') \
                .execute()
            
            if not response.data:
                return {
                    'total_bets': 0,
                    'avg_clv': 0.0,
                    'median_clv': 0.0,
                    'positive_rate': 0.0,
                    'best_clv': 0.0,
                    'worst_clv': 0.0
                }
            
            clv_values = [bet['clv'] for bet in response.data]
            
            # Calcular métricas
            avg_clv = sum(clv_values) / len(clv_values)
            positive_count = sum(1 for clv in clv_values if clv > 0)
            positive_rate = positive_count / len(clv_values)
            
            sorted_clv = sorted(clv_values)
            median_clv = sorted_clv[len(sorted_clv) // 2]
            
            return {
                'total_bets': len(clv_values),
                'avg_clv': avg_clv,
                'median_clv': median_clv,
                'positive_rate': positive_rate,
                'best_clv': max(clv_values),
                'worst_clv': min(clv_values),
                'days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting CLV stats: {e}")
            return {}
    
    def get_clv_by_sport(self, days: int = 30) -> Dict[str, Dict]:
        """Obtiene CLV promedio por deporte"""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Necesitamos join con predictions para obtener sport
            response = historical_db.supabase.table('predictions') \
                .select('sport_key, clv_tracking(clv)') \
                .gte('created_at', cutoff.isoformat()) \
                .execute()
            
            # Agrupar por deporte
            sport_clv = {}
            for pred in response.data:
                sport = pred.get('sport_key')
                clv_data = pred.get('clv_tracking', [])
                
                if sport and clv_data:
                    if sport not in sport_clv:
                        sport_clv[sport] = []
                    
                    for clv_record in clv_data:
                        if clv_record.get('clv') is not None:
                            sport_clv[sport].append(clv_record['clv'])
            
            # Calcular promedios
            results = {}
            for sport, clv_list in sport_clv.items():
                if clv_list:
                    results[sport] = {
                        'avg_clv': sum(clv_list) / len(clv_list),
                        'count': len(clv_list),
                        'positive_rate': sum(1 for c in clv_list if c > 0) / len(clv_list)
                    }
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting CLV by sport: {e}")
            return {}
    
    def is_sharp_bettor(self, min_bets: int = 50, min_clv: float = 0.02) -> Tuple[bool, Dict]:
        """
        Determina si el bot está actuando como sharp bettor.
        
        Criterios:
        - CLV promedio > +2%
        - Positive CLV rate > 60%
        - Mínimo 50 apuestas
        
        Returns:
            (is_sharp, stats_dict)
        """
        try:
            stats = self.get_clv_stats(days=90)
            
            total_bets = stats.get('total_bets', 0)
            avg_clv = stats.get('avg_clv', 0.0)
            positive_rate = stats.get('positive_rate', 0.0)
            
            is_sharp = (
                total_bets >= min_bets and
                avg_clv >= min_clv and
                positive_rate >= 0.60
            )
            
            return is_sharp, {
                'is_sharp': is_sharp,
                'total_bets': total_bets,
                'avg_clv': avg_clv,
                'positive_rate': positive_rate,
                'status': 'Sharp' if is_sharp else 'Developing',
                'requirements': {
                    'min_bets': min_bets,
                    'min_clv': min_clv,
                    'min_positive_rate': 0.60
                }
            }
            
        except Exception as e:
            logger.error(f"Error checking sharp status: {e}")
            return False, {}


# Instancia global
clv_tracker = CLVTracker()