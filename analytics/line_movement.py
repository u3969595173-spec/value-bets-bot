"""
analytics/line_movement.py - Sistema de tracking y análisis de movimiento de líneas

Detecta movimientos significativos en cuotas (steam moves, reverse line movement)
para identificar sharp action y mejores oportunidades de value betting.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from data.historical_db import historical_db

logger = logging.getLogger(__name__)


class LineMovementTracker:
    """Rastrea y analiza movimientos de líneas/cuotas en tiempo real"""
    
    def __init__(self):
        self.odds_history = defaultdict(list)  # event_id -> [(timestamp, odds_data)]
        
    def record_odds_snapshot(self, events: List[Dict]) -> int:
        """
        Guarda snapshot de cuotas actuales para tracking histórico.
        
        Args:
            events: Lista de eventos con cuotas actuales
            
        Returns:
            Número de snapshots guardados
        """
        try:
            now = datetime.now(timezone.utc)
            saved = 0
            
            for event in events:
                event_id = event.get('id')
                if not event_id:
                    continue
                
                # Extraer cuotas de todos los bookmakers
                snapshots_to_save = []  # Acumular para batch insert
                
                for bookmaker in event.get('bookmakers', []):
                    book_name = bookmaker.get('title', bookmaker.get('key'))
                    
                    for market in bookmaker.get('markets', []):
                        market_key = market.get('key')
                        
                        for outcome in market.get('outcomes', []):
                            snapshot = {
                                'timestamp': now.isoformat(),
                                'event_id': event_id,
                                'sport_key': event.get('sport_key'),
                                'bookmaker': book_name,
                                'market': market_key,
                                'selection': outcome.get('name'),
                                'odds': float(outcome.get('price')),
                                'point': outcome.get('point')  # Para spreads/totals
                            }
                            
                            # Guardar en memoria (últimas 24 horas)
                            self.odds_history[event_id].append((now, snapshot))
                            snapshots_to_save.append(snapshot)
                            saved += 1
            
            # Guardar TODOS los snapshots en lote (mucho más rápido)
            if snapshots_to_save:
                logger.info(f"💾 Guardando {len(snapshots_to_save)} snapshots en lote...")
                historical_db.save_odds_snapshots_batch(snapshots_to_save)
            
            # Limpiar datos viejos (> 24 horas)
            self._cleanup_old_data()
            
            logger.info(f"📸 Recorded {saved} odds snapshots")
            return saved
            
        except Exception as e:
            logger.error(f"Error recording odds snapshot: {e}")
            return 0
    
    def _cleanup_old_data(self):
        """Elimina snapshots de memoria de hace más de 24 horas"""
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            
            for event_id in list(self.odds_history.keys()):
                # Filtrar solo snapshots recientes
                self.odds_history[event_id] = [
                    (ts, data) for ts, data in self.odds_history[event_id]
                    if ts > cutoff
                ]
                
                # Eliminar evento si no tiene snapshots
                if not self.odds_history[event_id]:
                    del self.odds_history[event_id]
                    
        except Exception as e:
            logger.error(f"Error cleaning old data: {e}")
    
    def detect_steam_moves(self, event_id: str, threshold_percent: float = 5.0) -> List[Dict]:
        """
        Detecta steam moves (movimientos bruscos de cuotas que indican sharp action).
        
        Un steam move típico es:
        - Movimiento rápido (< 30 min)
        - Cambio significativo (> 5%)
        - En dirección opuesta al público (RLM - Reverse Line Movement)
        
        Args:
            event_id: ID del evento
            threshold_percent: % mínimo de cambio para considerar steam move
            
        Returns:
            Lista de steam moves detectados
        """
        try:
            snapshots = self.odds_history.get(event_id, [])
            
            if len(snapshots) < 2:
                return []
            
            steam_moves = []
            
            # Agrupar por bookmaker + market + selection
            grouped = defaultdict(list)
            for ts, snap in snapshots:
                key = (snap['bookmaker'], snap['market'], snap['selection'])
                grouped[key].append((ts, snap))
            
            # Analizar cada serie temporal
            for key, series in grouped.items():
                if len(series) < 2:
                    continue
                
                # Ordenar por timestamp
                series.sort(key=lambda x: x[0])
                
                # Comparar último vs primero (últimos 30 min)
                recent = [s for s in series if s[0] > datetime.now(timezone.utc) - timedelta(minutes=30)]
                
                if len(recent) < 2:
                    continue
                
                first_odds = recent[0][1]['odds']
                last_odds = recent[-1][1]['odds']
                
                # Calcular cambio porcentual
                change_percent = ((last_odds - first_odds) / first_odds) * 100
                
                if abs(change_percent) >= threshold_percent:
                    steam_moves.append({
                        'event_id': event_id,
                        'bookmaker': key[0],
                        'market': key[1],
                        'selection': key[2],
                        'initial_odds': first_odds,
                        'current_odds': last_odds,
                        'change_percent': change_percent,
                        'time_frame': '30min',
                        'direction': 'shortening' if change_percent < 0 else 'drifting',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
            
            if steam_moves:
                logger.info(f"🔥 Detected {len(steam_moves)} steam moves for event {event_id[:8]}")
            
            return steam_moves
            
        except Exception as e:
            logger.error(f"Error detecting steam moves: {e}")
            return []
    
    def get_line_movement_summary(self, event_id: str, selection: str) -> Optional[Dict]:
        """
        Obtiene resumen del movimiento de línea para una selección específica.
        
        Args:
            event_id: ID del evento
            selection: Nombre de la selección (equipo/outcome)
            
        Returns:
            Dict con resumen del movimiento o None
        """
        try:
            snapshots = self.odds_history.get(event_id, [])
            
            if not snapshots:
                # Intentar obtener de Supabase
                snapshots_db = historical_db.get_odds_history(event_id, hours=24)
                if not snapshots_db:
                    return None
                
                # Convertir a formato interno
                snapshots = [(
                    datetime.fromisoformat(s['timestamp']),
                    s
                ) for s in snapshots_db if s['selection'] == selection]
            else:
                # Filtrar por selección
                snapshots = [(ts, snap) for ts, snap in snapshots 
                           if snap['selection'] == selection]
            
            if len(snapshots) < 2:
                return None
            
            # Ordenar por tiempo
            snapshots.sort(key=lambda x: x[0])
            
            # Calcular estadísticas
            odds_values = [snap['odds'] for _, snap in snapshots]
            
            opening_odds = odds_values[0]
            current_odds = odds_values[-1]
            peak_odds = max(odds_values)
            lowest_odds = min(odds_values)
            
            change_percent = ((current_odds - opening_odds) / opening_odds) * 100
            
            # Detectar tendencia
            if len(odds_values) >= 3:
                recent_trend = odds_values[-3:]
                if all(recent_trend[i] < recent_trend[i+1] for i in range(len(recent_trend)-1)):
                    trend = 'drifting'  # Cuota subiendo
                elif all(recent_trend[i] > recent_trend[i+1] for i in range(len(recent_trend)-1)):
                    trend = 'shortening'  # Cuota bajando
                else:
                    trend = 'stable'
            else:
                trend = 'insufficient_data'
            
            return {
                'event_id': event_id,
                'selection': selection,
                'opening_odds': opening_odds,
                'current_odds': current_odds,
                'peak_odds': peak_odds,
                'lowest_odds': lowest_odds,
                'change_percent': change_percent,
                'trend': trend,
                'snapshots_count': len(snapshots),
                'time_span_hours': (snapshots[-1][0] - snapshots[0][0]).total_seconds() / 3600,
                'is_favorable': current_odds > opening_odds  # Mejores cuotas que al inicio
            }
            
        except Exception as e:
            logger.error(f"Error getting line movement summary: {e}")
            return None
    
    def find_reverse_line_movement(self, events: List[Dict]) -> List[Dict]:
        """
        Detecta Reverse Line Movement (RLM): cuotas que se mueven contra el sentido común.
        
        RLM indica sharp action profesional apostando contra el público.
        
        Args:
            events: Lista de eventos a analizar
            
        Returns:
            Lista de RLM detectados
        """
        try:
            rlm_opportunities = []
            
            for event in events:
                event_id = event.get('id')
                if not event_id:
                    continue
                
                # Obtener movimientos para todas las selecciones principales
                home = event.get('home_team', event.get('home'))
                away = event.get('away_team', event.get('away'))
                
                for selection in [home, away]:
                    if not selection:
                        continue
                    
                    movement = self.get_line_movement_summary(event_id, selection)
                    
                    if movement and movement.get('is_favorable'):
                        # Cuotas mejoraron (subieron) - posible RLM
                        if movement['change_percent'] > 2.0:  # Movimiento significativo
                            rlm_opportunities.append({
                                'event_id': event_id,
                                'selection': selection,
                                'sport': event.get('sport_key'),
                                'opening_odds': movement['opening_odds'],
                                'current_odds': movement['current_odds'],
                                'improvement_percent': movement['change_percent'],
                                'trend': movement['trend'],
                                'confidence': 'high' if movement['change_percent'] > 5 else 'medium'
                            })
            
            if rlm_opportunities:
                logger.info(f"🔄 Found {len(rlm_opportunities)} RLM opportunities")
            
            return rlm_opportunities
            
        except Exception as e:
            logger.error(f"Error finding RLM: {e}")
            return []
    
    def get_best_odds_timing(self, event_id: str, selection: str) -> Dict:
        """
        Determina el mejor momento para apostar basado en movimiento histórico.
        
        Args:
            event_id: ID del evento
            selection: Selección a analizar
            
        Returns:
            Dict con recomendación de timing
        """
        try:
            movement = self.get_line_movement_summary(event_id, selection)
            
            if not movement:
                return {'recommendation': 'insufficient_data'}
            
            current = movement['current_odds']
            peak = movement['peak_odds']
            opening = movement['opening_odds']
            trend = movement['trend']
            
            # Lógica de recomendación
            if trend == 'drifting' and current >= peak * 0.98:
                # Cuotas subiendo y cerca del máximo
                return {
                    'recommendation': 'bet_now',
                    'reason': 'Cuotas en máximo reciente y subiendo',
                    'current_odds': current,
                    'confidence': 'high'
                }
            elif trend == 'shortening' and current <= opening * 1.02:
                # Cuotas bajando rápidamente
                return {
                    'recommendation': 'bet_soon',
                    'reason': 'Cuotas bajando, puede seguir cayendo',
                    'current_odds': current,
                    'confidence': 'medium'
                }
            elif trend == 'stable':
                return {
                    'recommendation': 'wait_and_watch',
                    'reason': 'Cuotas estables, monitorear',
                    'current_odds': current,
                    'confidence': 'low'
                }
            else:
                return {
                    'recommendation': 'analyze_carefully',
                    'reason': 'Movimiento impredecible',
                    'current_odds': current,
                    'confidence': 'low'
                }
                
        except Exception as e:
            logger.error(f"Error getting best timing: {e}")
            return {'recommendation': 'error'}


# Instancia global
line_tracker = LineMovementTracker()
