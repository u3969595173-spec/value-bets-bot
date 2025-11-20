"""
alerts_tracker.py - Rastrea todas las alertas enviadas y sus resultados

Guarda cada alerta con:
- Datos del pick (event_id, selection, odds, stake)
- Estado (pending/won/lost/push)
- Resultado verificado
- Usuario que recibió la alerta
"""

import json
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class AlertsTracker:
    """Gestiona el tracking de todas las alertas enviadas"""
    
    def __init__(self, filepath: str = "data/sent_alerts.json"):
        self.filepath = filepath
        self.alerts = self._load_alerts()
    
    def _load_alerts(self) -> Dict:
        """Carga alertas desde JSON"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading alerts: {e}")
                return {}
        return {}
    
    def _save_alerts(self):
        """Guarda alertas a JSON"""
        try:
            # Crear directorio si no existe
            Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.alerts, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving alerts: {e}")
    
    def add_alert(self, user_id: str, event_id: str, sport: str, 
                  pick_type: str, selection: str, odds: float,
                  stake: float, point: Optional[float] = None,
                  game_time: Optional[str] = None,
                  was_adjusted: bool = False,
                  original_odds: Optional[float] = None,
                  original_point: Optional[float] = None) -> str:
        """
        Registra una nueva alerta enviada
        
        Args:
            user_id: ID del usuario
            event_id: ID del evento
            sport: Deporte
            pick_type: Tipo de mercado (h2h, spreads, totals)
            selection: Selección (equipo/jugador)
            odds: Cuota AJUSTADA (la que se envió al usuario)
            stake: Cantidad apostada
            point: Punto/línea AJUSTADA (la que se envió)
            game_time: Hora del partido
            was_adjusted: Si la línea fue ajustada
            original_odds: Cuota original antes de ajustar
            original_point: Punto original antes de ajustar
            
        Returns:
            alert_id único
        """
        alert_id = f"{user_id}_{event_id}_{datetime.now(timezone.utc).timestamp()}"
        
        alert_data = {
            'user_id': user_id,
            'event_id': event_id,
            'sport': sport,
            'pick_type': pick_type,
            'selection': selection,
            'odds': odds,  # Cuota ajustada
            'stake': stake,
            'point': point,  # Punto ajustado
            'game_time': game_time,
            'status': 'pending',
            'sent_at': datetime.now(timezone.utc).isoformat(),
            'verified_at': None,
            'result': None,
            'profit_loss': 0.0,
            # Info de ajuste
            'was_adjusted': was_adjusted,
            'original_odds': original_odds,
            'original_point': original_point
        }
        
        self.alerts[alert_id] = alert_data
        self._save_alerts()
        
        logger.info(f"📝 Alert registered: {selection} @ {odds:.2f} for user {user_id}")
        if was_adjusted:
            logger.info(f"   🔧 Adjusted from {original_point} @ {original_odds:.2f}")
        
        return alert_id
    
    def update_alert_result(self, alert_id: str, result: str, 
                           profit_loss: float = None):
        """
        Actualiza el resultado de una alerta
        
        Args:
            alert_id: ID de la alerta
            result: 'won', 'lost', 'push'
            profit_loss: Ganancia/pérdida calculada con cuota AJUSTADA
        """
        if alert_id not in self.alerts:
            logger.warning(f"Alert {alert_id} not found")
            return
        
        self.alerts[alert_id]['status'] = result
        self.alerts[alert_id]['verified_at'] = datetime.now(timezone.utc).isoformat()
        self.alerts[alert_id]['final_result'] = result
        
        if profit_loss is not None:
            self.alerts[alert_id]['profit_loss'] = profit_loss
        
        self._save_alerts()
        logger.info(f"Alert {alert_id} result: {result}, P/L: {profit_loss}")
    
    def get_pending_alerts(self, hours_old: int = 3) -> List[Dict]:
        """
        Obtiene alertas pendientes de verificación
        
        Args:
            hours_old: Mínimo de horas desde envío para verificar
            
        Returns:
            Lista de alertas pendientes listas para verificar
        """
        from datetime import timedelta
        
        now = datetime.now(timezone.utc)
        pending = []
        
        for alert_id, alert in self.alerts.items():
            if alert['status'] != 'pending':
                continue
            
            sent_at = datetime.fromisoformat(alert['sent_at'])
            age = (now - sent_at).total_seconds() / 3600
            
            if age >= hours_old:
                pending.append({
                    'alert_id': alert_id,
                    **alert
                })
        
        return pending
    
    def get_user_stats(self, user_id: str, period: str = 'all') -> Dict:
        """
        Obtiene estadísticas de alertas de un usuario
        
        Args:
            user_id: ID del usuario
            period: 'all', 'week', 'month', 'year'
        
        Returns:
            Dict con wins, losses, ROI, etc.
        """
        from datetime import timedelta
        
        user_alerts = [a for a in self.alerts.values() if a['user_id'] == user_id]
        
        # Filtrar por período
        if period != 'all':
            now = datetime.now(timezone.utc)
            if period == 'week':
                cutoff = now - timedelta(days=7)
            elif period == 'month':
                cutoff = now - timedelta(days=30)
            elif period == 'year':
                cutoff = now - timedelta(days=365)
            else:
                cutoff = None
            
            if cutoff:
                user_alerts = [
                    a for a in user_alerts 
                    if datetime.fromisoformat(a['sent_at']) >= cutoff
                ]
        
        if not user_alerts:
            return {
                'total': 0,
                'won': 0,
                'lost': 0,
                'push': 0,
                'pending': 0,
                'win_rate': 0.0,
                'roi': 0.0,
                'total_staked': 0.0,
                'total_profit': 0.0
            }
        
        verified = [a for a in user_alerts if a['status'] in ['won', 'lost', 'push']]
        won = [a for a in verified if a['status'] == 'won']
        lost = [a for a in verified if a['status'] == 'lost']
        push = [a for a in verified if a['status'] == 'push']
        pending = [a for a in user_alerts if a['status'] == 'pending']
        
        total_staked = sum(a['stake'] for a in verified)
        total_profit = sum(a.get('profit_loss', 0) for a in verified)
        
        win_rate = (len(won) / len(verified) * 100) if verified else 0.0
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0.0
        
        return {
            'total': len(user_alerts),
            'won': len(won),
            'lost': len(lost),
            'push': len(push),
            'pending': len(pending),
            'win_rate': win_rate,
            'roi': roi,
            'total_staked': total_staked,
            'total_profit': total_profit
        }
    
    def get_global_stats(self) -> Dict:
        """Obtiene estadísticas globales de todas las alertas"""
        all_alerts = list(self.alerts.values())
        
        if not all_alerts:
            return {
                'total': 0,
                'won': 0,
                'lost': 0,
                'push': 0,
                'pending': 0,
                'win_rate': 0.0,
                'roi': 0.0,
                'by_sport': {}
            }
        
        verified = [a for a in all_alerts if a['status'] in ['won', 'lost', 'push']]
        won = [a for a in verified if a['status'] == 'won']
        lost = [a for a in verified if a['status'] == 'lost']
        push = [a for a in verified if a['status'] == 'push']
        pending = [a for a in all_alerts if a['status'] == 'pending']
        
        total_staked = sum(a['stake'] for a in verified)
        total_profit = sum(a.get('profit_loss', 0) for a in verified)
        
        win_rate = (len(won) / len(verified) * 100) if verified else 0.0
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0.0
        
        # Stats por deporte
        by_sport = {}
        for sport in set(a['sport'] for a in all_alerts):
            sport_alerts = [a for a in verified if a['sport'] == sport]
            sport_won = [a for a in sport_alerts if a['status'] == 'won']
            
            if sport_alerts:
                by_sport[sport] = {
                    'total': len(sport_alerts),
                    'won': len(sport_won),
                    'win_rate': len(sport_won) / len(sport_alerts) * 100
                }
        
        return {
            'total': len(all_alerts),
            'won': len(won),
            'lost': len(lost),
            'push': len(push),
            'pending': len(pending),
            'win_rate': win_rate,
            'roi': roi,
            'total_staked': total_staked,
            'total_profit': total_profit,
            'by_sport': by_sport
        }


# Instancia global
_tracker = None

def get_alerts_tracker() -> AlertsTracker:
    """Obtiene la instancia global del tracker"""
    global _tracker
    if _tracker is None:
        _tracker = AlertsTracker()
    return _tracker


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    tracker = AlertsTracker("data/test_alerts.json")
    
    # Añadir alertas de prueba
    alert1 = tracker.add_alert(
        user_id="123",
        event_id="event_abc",
        sport="basketball_nba",
        pick_type="spreads",
        selection="Lakers",
        odds=1.95,
        stake=10.0,
        point=5.5
    )
    print(f"Added alert: {alert1}")
    
    # Actualizar resultado
    tracker.update_alert_result(alert1, 'won', profit_loss=9.5)
    
    # Ver stats
    stats = tracker.get_user_stats("123")
    print(f"\nUser stats: {stats}")
