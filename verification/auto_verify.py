"""
verification/auto_verify.py - Sistema de verificación automática de resultados

Verifica automáticamente las predicciones usando The Odds API para obtener scores.
Calcula ROI, accuracy y estadísticas de performance reales.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import httpx
from data.historical_db import historical_db

logger = logging.getLogger(__name__)


class AutoVerifier:
    """Verificador automático de resultados de predicciones"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.the-odds-api.com/v4"
    
    async def verify_pending_predictions(self) -> Dict:
        """
        Verifica todas las predicciones pendientes que ya deberían tener resultado.
        
        Returns:
            Dict con estadísticas: {
                'verified': int,
                'correct': int,
                'incorrect': int,
                'total_profit': float
            }
        """
        try:
            # Obtener predicciones sin verificar de hace más de 3 horas
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=3)
            
            pending = historical_db.get_unverified_predictions(
                before_time=cutoff_time.isoformat()
            )
            
            if not pending:
                logger.info("No hay predicciones pendientes de verificar")
                return {'verified': 0, 'correct': 0, 'incorrect': 0, 'total_profit': 0.0}
            
            logger.info(f"Verificando {len(pending)} predicciones...")
            
            stats = {
                'verified': 0,
                'correct': 0,
                'incorrect': 0,
                'total_profit': 0.0
            }
            
            # Agrupar por evento para minimizar llamadas a API
            events_to_verify = {}
            for pred in pending:
                event_id = pred.get('event_id')
                if event_id not in events_to_verify:
                    events_to_verify[event_id] = []
                events_to_verify[event_id].append(pred)
            
            # Verificar cada evento
            async with httpx.AsyncClient(timeout=30.0) as client:
                for event_id, predictions in events_to_verify.items():
                    try:
                        result = await self._get_event_result(client, predictions[0])
                        
                        if result:
                            # Verificar todas las predicciones de este evento
                            for pred in predictions:
                                verified = self._verify_prediction(pred, result)
                                if verified:
                                    stats['verified'] += 1
                                    if verified['was_correct']:
                                        stats['correct'] += 1
                                    else:
                                        stats['incorrect'] += 1
                                    stats['total_profit'] += verified['profit_loss']
                                    
                                    # NUEVO: Actualizar estadísticas del usuario
                                    user_id = pred.get('user_id')
                                    if user_id:
                                        self._update_user_stats(user_id, pred, verified)
                        
                        # Rate limiting: esperar entre requests
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"Error verificando evento {event_id}: {e}")
                        continue
            
            logger.info(f"✅ Verificación completa: {stats['verified']} predicciones, "
                       f"{stats['correct']} correctas, ROI: ${stats['total_profit']:+.2f}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error en verificación automática: {e}")
            return {'verified': 0, 'correct': 0, 'incorrect': 0, 'total_profit': 0.0}
    
    async def _get_event_result(self, client: httpx.AsyncClient, prediction: Dict) -> Optional[Dict]:
        """
        Obtiene el resultado de un evento desde The Odds API.
        
        Args:
            client: Cliente HTTP
            prediction: Diccionario con datos de la predicción
            
        Returns:
            Dict con resultado del evento o None si no disponible
        """
        try:
            sport_key = prediction.get('sport_key')
            event_id = prediction.get('event_id')
            
            if not sport_key or not event_id:
                return None
            
            # Intentar obtener scores del evento
            url = f"{self.base_url}/sports/{sport_key}/scores"
            params = {
                'apiKey': self.api_key,
                'daysFrom': 1  # Últimas 24 horas
            }
            
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                events = response.json()
                
                # Buscar el evento específico
                for event in events:
                    if event.get('id') == event_id:
                        if event.get('completed'):
                            return {
                                'home_team': event.get('home_team'),
                                'away_team': event.get('away_team'),
                                'home_score': event.get('scores', [{}])[0].get('score') if event.get('scores') else None,
                                'away_score': event.get('scores', [{}])[1].get('score') if len(event.get('scores', [])) > 1 else None,
                                'completed': True
                            }
                return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo resultado: {e}")
            return None
    
    def _verify_prediction(self, prediction: Dict, result: Dict) -> Optional[Dict]:
        """
        Verifica si una predicción fue correcta comparando con el resultado real.
        
        Args:
            prediction: Predicción original
            result: Resultado real del evento
            
        Returns:
            Dict con resultado de verificación o None si no se pudo verificar
        """
        try:
            market = prediction.get('market', 'h2h')
            selection = prediction.get('selection', '')
            odds = float(prediction.get('odds', 0))
            stake = float(prediction.get('stake', 0))
            
            home_score = result.get('home_score')
            away_score = result.get('away_score')
            
            if home_score is None or away_score is None:
                return None
            
            home_score = int(home_score)
            away_score = int(away_score)
            
            was_correct = False
            
            # Verificar según el mercado
            if market == 'h2h':
                was_correct = self._verify_h2h(
                    selection, 
                    result['home_team'], 
                    result['away_team'],
                    home_score,
                    away_score
                )
            elif market == 'totals':
                was_correct = self._verify_totals(selection, home_score + away_score, prediction)
            elif market == 'spreads':
                was_correct = self._verify_spreads(
                    selection,
                    result['home_team'],
                    home_score,
                    away_score,
                    prediction
                )
            
            # Calcular profit/loss
            if was_correct:
                profit_loss = stake * (odds - 1)  # Ganancia
            else:
                profit_loss = -stake  # Pérdida
            
            # Guardar en base de datos
            historical_db.verify_prediction(
                prediction_id=prediction.get('id'),
                was_correct=was_correct,
                actual_home_score=home_score,
                actual_away_score=away_score,
                profit_loss=profit_loss
            )
            
            return {
                'was_correct': was_correct,
                'profit_loss': profit_loss,
                'home_score': home_score,
                'away_score': away_score
            }
            
        except Exception as e:
            logger.error(f"Error verificando predicción: {e}")
            return None
    
    def _verify_h2h(self, selection: str, home_team: str, away_team: str, 
                    home_score: int, away_score: int) -> bool:
        """Verifica predicción de ganador (h2h)"""
        selection_lower = selection.lower()
        
        # Draw
        if 'draw' in selection_lower or selection_lower in ['x', 'empate']:
            return home_score == away_score
        
        # Home win
        if home_team.lower() in selection_lower:
            return home_score > away_score
        
        # Away win
        if away_team.lower() in selection_lower:
            return away_score > home_score
        
        return False
    
    def _verify_totals(self, selection: str, total_score: int, prediction: Dict) -> bool:
        """Verifica predicción de totales (over/under)"""
        line = prediction.get('point', 0)
        
        if 'over' in selection.lower():
            return total_score > line
        elif 'under' in selection.lower():
            return total_score < line
        
        return False
    
    def _verify_spreads(self, selection: str, home_team: str, 
                       home_score: int, away_score: int, prediction: Dict) -> bool:
        """Verifica predicción de spreads (hándicap)"""
        spread = float(prediction.get('point', 0))
        
        if home_team.lower() in selection.lower():
            # Home con spread
            adjusted_home = home_score + spread
            return adjusted_home > away_score
        else:
            # Away con spread
            adjusted_away = away_score - spread
            return adjusted_away > home_score
    
    def get_performance_summary(self, days: int = 7) -> Dict:
        """
        Obtiene resumen de performance verificado.
        
        Args:
            days: Número de días a analizar
            
        Returns:
            Dict con estadísticas de performance
        """
        try:
            stats = historical_db.get_bot_performance(days=days)
            
            if stats['total_predictions'] == 0:
                return {
                    'days': days,
                    'total_predictions': 0,
                    'message': 'Sin predicciones verificadas aún'
                }
            
            return {
                'days': days,
                'total_predictions': stats['total_predictions'],
                'correct': stats['correct'],
                'incorrect': stats['incorrect'],
                'accuracy': f"{stats['accuracy']*100:.1f}%",
                'roi': f"{stats['roi']*100:+.1f}%",
                'total_profit': f"${stats['total_profit']:+.2f}",
                'avg_odds': f"{stats['avg_odds']:.2f}",
                'total_stake': f"${stats['total_stake']:.2f}"
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo resumen: {e}")
            return {'error': str(e)}

    def _update_user_stats(self, user_id: str, prediction: Dict, verified_result: Dict):
        """
        Actualiza estadísticas del usuario en users.json después de verificar pick
        
        Args:
            user_id: ID del usuario
            prediction: Predicción original
            verified_result: Resultado de verificación con was_correct y profit_loss
        """
        try:
            from data.users import get_users_manager
            
            users_manager = get_users_manager()
            user = users_manager.get_user(user_id)
            
            if not user:
                logger.warning(f"Usuario {user_id} no encontrado para actualizar stats")
                return
            
            # Actualizar total_bets
            user.total_bets += 1
            
            # Actualizar won_bets si ganó
            if verified_result['was_correct']:
                user.won_bets += 1
            
            # Actualizar total_profit
            user.total_profit += verified_result['profit_loss']
            
            # Actualizar bankroll dinámico
            user.bankroll += verified_result['profit_loss']
            
            # Actualizar bet en bet_history si existe
            event_id = prediction.get('event_id')
            if event_id and hasattr(user, 'bet_history') and user.bet_history:
                for bet in user.bet_history:
                    if bet.get('event_id') == event_id and bet.get('status') == 'pending':
                        bet['status'] = 'won' if verified_result['was_correct'] else 'lost'
                        bet['profit'] = verified_result['profit_loss']
                        bet['home_score'] = verified_result.get('home_score')
                        bet['away_score'] = verified_result.get('away_score')
                        bet['verified_at'] = datetime.now(timezone.utc).isoformat()
                        break
            
            # Guardar cambios
            users_manager.save()
            
            logger.info(f"✅ Stats actualizadas para usuario {user_id}: "
                       f"{user.won_bets}/{user.total_bets} ganadas, "
                       f"profit: ${user.total_profit:+.2f}, "
                       f"bankroll: ${user.bankroll:.2f}")
            
        except Exception as e:
            logger.error(f"Error actualizando stats de usuario {user_id}: {e}")


async def run_verification_cycle():
    """Ejecuta un ciclo de verificación (llamar diariamente)"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv('API_KEY')
    
    if not api_key:
        logger.error("API_KEY no configurada")
        return
    
    verifier = AutoVerifier(api_key)
    results = await verifier.verify_pending_predictions()
    
    logger.info(f"📊 Ciclo de verificación completado: {results}")
    return results


if __name__ == '__main__':
    # Test
    asyncio.run(run_verification_cycle())
