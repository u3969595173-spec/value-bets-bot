"""
main.py - Bot de Value Bets con monitoreo continuo y alertas progresivas

Caractersticas principales:
- Monitoreo diario a las 6 AM (hora de Amrica)
- Actualizacin cada hora de cuotas y probabilidades
- Alertas solo cuando el evento est a menos de 2 horas
- Mximo 3-5 alertas diarias por usuario
- Solo usuarios premium reciben alertas
- Filtros estrictos: cuotas 1.5-2.1, probabilidad 70%+
"""

import asyncio
import sys
import pathlib
import os
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import List, Dict, Set, Optional
from dotenv import load_dotenv

# Asegurar que el proyecto est en sys.path
PROJECT_ROOT = pathlib.Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Imports del sistema existente
from data.odds_api import OddsFetcher
from scanner.scanner import ValueScanner, USING_ENHANCED_MODEL
from notifier.telegram import TelegramNotifier
from data.users import get_users_manager, User
from data.state import AlertsState
from notifier.alert_formatter import format_premium_alert
from utils.sport_translator import translate_sport

# Imports del sistema mejorado (opcional)
try:
    from data.historical_db import historical_db
    from data.stats_api import injury_scraper
    from analytics.line_movement import line_tracker
    from scanner.enhanced_scanner import EnhancedValueScanner
    from scanner.ml_scanner import MLValueScanner
    from analytics.clv_tracker import clv_tracker
    from utils.kelly_criterion import kelly_calculator
    ENHANCED_SYSTEM_AVAILABLE = True
except ImportError:
    historical_db = None
    injury_scraper = None
    line_tracker = None
    EnhancedValueScanner = None
    ENHANCED_SYSTEM_AVAILABLE = False

# Configurar encoding UTF-8 para Windows
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('value_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuracin desde .env
API_KEY = os.getenv("API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN") 
CHAT_ID = os.getenv("CHAT_ID")

# Configuracin de filtros
MIN_ODD = float(os.getenv("MIN_ODD", "1.5"))
MAX_ODD = float(os.getenv("MAX_ODD", "2.5"))
MIN_PROB = float(os.getenv("MIN_PROB", "0.60"))  # 60% mÃƒÂ­nimo
MAX_ALERTS_PER_DAY = int(os.getenv("MAX_ALERTS_PER_DAY", "5"))

# Deportes a monitorear
SPORTS = os.getenv("SPORTS", "basketball_nba,soccer_epl,soccer_spain_la_liga,tennis_atp,tennis_wta,baseball_mlb").split(",")

# ConfiguraciÃƒÂ³n de tiempo
AMERICA_TZ = ZoneInfo("America/New_York")  # Hora de AmÃƒÂ©rica
DAILY_START_HOUR = 6  # 6 AM
UPDATE_INTERVAL_MINUTES = 10  # Actualizar cada 10 minutos (mantiene Render activo)
ALERT_WINDOW_HOURS = 4  # Alertar cuando falten menos de 4 horas

# Configuracin adicional
SAMPLE_PATH = os.getenv("SAMPLE_ODDS_PATH", "data/sample_odds.json")


class ValueBotMonitor:
    """
    Monitor principal del bot de value bets con alertas progresivas
    """
    
    def __init__(self):
        self.fetcher = OddsFetcher(api_key=API_KEY)
        
        # Usar scanner mejorado si estÃƒÂ¡ disponible
        if ENHANCED_SYSTEM_AVAILABLE and EnhancedValueScanner:
            self.scanner = EnhancedValueScanner(
                min_odd=MIN_ODD, 
                max_odd=MAX_ODD, 
                min_prob=MIN_PROB
            )
            logger.info("Ã¢Å“â€¦ Usando EnhancedValueScanner con line movement")
        else:
            self.scanner = ValueScanner(
                min_odd=MIN_ODD, 
                max_odd=MAX_ODD, 
                min_prob=MIN_PROB
            )
            logger.info("Ã¢Å¡Â Ã¯Â¸Â  Usando ValueScanner bÃƒÂ¡sico")
        
        self.notifier = TelegramNotifier(BOT_TOKEN)
        self.users_manager = get_users_manager()
        self.alerts_state = AlertsState("data/alerts_state.json", MAX_ALERTS_PER_DAY)
        
        # Tracking de eventos monitoreados
        self.monitored_events: Dict[str, Dict] = {}  # event_id -> event_data
        self.sent_alerts: Set[str] = set()  # Para evitar duplicados
        
        logger.info("ValueBotMonitor inicializado")
        logger.info(f"Deportes: {', '.join(SPORTS)}")
        logger.info(f"Filtros: odds {MIN_ODD}-{MAX_ODD}, prob {MIN_PROB:.0%}+")
        logger.info(f"Alertas: maximo {MAX_ALERTS_PER_DAY} diarias, <{ALERT_WINDOW_HOURS}h antes")
        
        # Log sistema mejorado
        if ENHANCED_SYSTEM_AVAILABLE:
            logger.info("Ã¢Å“â€¦ Sistema mejorado disponible:")
            logger.info(f"   - Base de datos histÃƒÂ³rica: {historical_db is not None}")
            logger.info(f"   - Scraper de lesiones: {injury_scraper is not None}")
            logger.info(f"   - Modelo mejorado: {USING_ENHANCED_MODEL}")
        else:
            logger.info("Ã¢Å¡Â Ã¯Â¸Â  Sistema mejorado no disponible, usando versiÃƒÂ³n bÃƒÂ¡sica")

    def is_daily_start_time(self) -> bool:
        """
        Verifica si es hora de inicio diario (6 AM Amrica)
        """
        now = datetime.now(AMERICA_TZ)
        return now.hour == DAILY_START_HOUR and now.minute < 5

    def get_events_starting_soon(self, max_hours: float = ALERT_WINDOW_HOURS) -> List[Dict]:
        """
        Filtra eventos que empiezan en menos de max_hours
        """
        now = datetime.now(timezone.utc)
        cutoff_time = now + timedelta(hours=max_hours)
        
        events_soon = []
        for event_id, event_data in self.monitored_events.items():
            commence_time = event_data.get('commence_time')
            if commence_time and isinstance(commence_time, datetime):
                if now <= commence_time <= cutoff_time:
                    events_soon.append(event_data)
        
        return events_soon

    def get_next_update_time(self) -> datetime:
        """
        Calcula la prÃƒÂ³xima actualizaciÃƒÂ³n (cada 10 minutos)
        """
        now = datetime.now(AMERICA_TZ)
        next_update = now + timedelta(minutes=UPDATE_INTERVAL_MINUTES)
        return next_update

    def get_next_daily_start(self) -> datetime:
        """
        Calcula el prximo inicio diario (6 AM Amrica)
        """
        now = datetime.now(AMERICA_TZ)
        next_start = now.replace(hour=DAILY_START_HOUR, minute=0, second=0, microsecond=0)
        
        if now >= next_start:
            next_start += timedelta(days=1)
        
        return next_start
    
    def get_next_verification_time(self) -> datetime:
        """
        Calcula la prÃƒÂ³xima verificaciÃƒÂ³n de resultados (2 AM AmÃƒÂ©rica)
        """
        now = datetime.now(AMERICA_TZ)
        next_verification = now.replace(hour=2, minute=0, second=0, microsecond=0)
        
        if now >= next_verification:
            next_verification += timedelta(days=1)
        
        return next_verification
    
    async def verify_results(self):
        """
        Verifica resultados de predicciones pendientes usando auto-verificaciÃƒÂ³n
        """
        if not ENHANCED_SYSTEM_AVAILABLE or not API_KEY:
            logger.warning("Sistema mejorado o API_KEY no disponible, saltando verificaciÃƒÂ³n")
            return
        
        try:
            logger.info("Ã°Å¸â€Â Iniciando verificaciÃƒÂ³n automÃƒÂ¡tica de resultados...")
            
            # Importar el verificador automÃƒÂ¡tico
            from verification.auto_verify import AutoVerifier
            
            verifier = AutoVerifier(API_KEY)
            stats = await verifier.verify_pending_predictions()
            
            # Log de resultados
            if stats['verified'] > 0:
                accuracy = (stats['correct'] / stats['verified'] * 100) if stats['verified'] > 0 else 0
                logger.info(f"Ã¢Å“â€¦ VerificaciÃƒÂ³n completada:")
                logger.info(f"   Ã¢â‚¬Â¢ Verificadas: {stats['verified']}")
                logger.info(f"   Ã¢â‚¬Â¢ Correctas: {stats['correct']}")
                logger.info(f"   Ã¢â‚¬Â¢ Accuracy: {accuracy:.1f}%")
                logger.info(f"   Ã¢â‚¬Â¢ Profit: ${stats['total_profit']:+.2f}")
                
                # Notificar al admin con resumen de 7 dÃƒÂ­as
                performance = verifier.get_performance_summary(days=7)
                
                report = f"""Ã°Å¸â€œÅ  **VERIFICACIÃƒâ€œN DIARIA DE RESULTADOS**

Ã°Å¸â€ â€¢ **ÃƒÅ¡ltimas 24h:**
Ã¢Å“â€¦ Predicciones verificadas: {stats['verified']}
Ã°Å¸Å½Â¯ Correctas: {stats['correct']}
Ã°Å¸â€œË† Accuracy: {accuracy:.1f}%
Ã°Å¸â€™Â° Profit: ${stats['total_profit']:+.2f}

Ã°Å¸â€œâ€¦ **ÃƒÅ¡ltimos 7 dÃƒÂ­as:**
Ã°Å¸Å½Â² Total: {performance.get('total_predictions', 0)}
Ã¢Å“â€¦ Accuracy: {performance.get('accuracy', '0%')}
Ã°Å¸â€™Âµ ROI: {performance.get('roi', '0%')}
Ã°Å¸â€™Â° Profit: {performance.get('total_profit', '$0')}"""
                
                await self.notifier.send_message(CHAT_ID, report)
            else:
                logger.info("Ã¢â€žÂ¹Ã¯Â¸Â No hay predicciones para verificar")
                
        except Exception as e:
            logger.error(f"Ã¢ÂÅ’ Error en verificaciÃƒÂ³n de resultados: {e}")

    async def fetch_and_update_events(self) -> List[Dict]:
        """
        Obtiene eventos de las APIs y actualiza el monitoring + line tracking
        """
        try:
            logger.info("Fetching odds from APIs...")
            events = await self.fetcher.fetch_odds(SPORTS)
            logger.info(f"Fetched {len(events)} events total")
            
            # Procesar y almacenar eventos
            processed_events = []
            current_time = datetime.now(timezone.utc)
            
            for event in events:
                try:
                    # Parsear tiempo de inicio
                    commence_str = event.get('commence_time')
                    if commence_str:
                        if isinstance(commence_str, str):
                            commence_time = datetime.fromisoformat(commence_str.replace('Z', '+00:00'))
                        else:
                            commence_time = commence_str
                    else:
                        continue  # Skip eventos sin tiempo
                    
                    # Solo eventos futuros (no en vivo)
                    if commence_time <= current_time:
                        continue
                    
                    # Agregar tiempo parseado al evento
                    event['commence_time'] = commence_time
                    event_id = event.get('id', f"{event.get('sport_key', 'unknown')}_{len(processed_events)}")
                    
                    # Actualizar en monitored_events
                    self.monitored_events[event_id] = event
                    processed_events.append(event)
                    
                except Exception as e:
                    logger.warning(f"Error processing event: {e}")
                    continue
            
            # Guardar snapshot de cuotas para line movement tracking
            if ENHANCED_SYSTEM_AVAILABLE and line_tracker and processed_events:
                line_tracker.record_odds_snapshot(processed_events)
            
            # Limpiar eventos pasados del monitoring
            current_time = datetime.now(timezone.utc)
            expired_events = [
                event_id for event_id, event in self.monitored_events.items()
                if event.get('commence_time') and event['commence_time'] <= current_time
            ]
            
            for event_id in expired_events:
                del self.monitored_events[event_id]
                logger.debug(f" Removed expired event: {event_id}")
            
            logger.info(f"Events processed: {len(processed_events)}, total monitored: {len(self.monitored_events)}")
            return processed_events
            
        except Exception as e:
            logger.error(f" Error fetching events: {e}")
            return []

    async def find_value_opportunities(self, events: List[Dict]) -> List[Dict]:
        """
        Encuentra oportunidades de value betting usando el scanner mejorado
        """
        try:
            # Usar scanner mejorado si estÃƒÂ¡ disponible
            if ENHANCED_SYSTEM_AVAILABLE and EnhancedValueScanner and isinstance(self.scanner, EnhancedValueScanner):
                # Scanner con anÃƒÂ¡lisis de line movement
                candidates = self.scanner.find_value_bets_with_movement(events)
                
                # Filtrar por nivel de confianza (solo high y very_high)
                candidates = self.scanner.filter_by_confidence(candidates, min_level='high')
                
                logger.info(f"Ã°Å¸Å½Â¯ Found {len(candidates)} high-confidence value opportunities with movement analysis")
                
                # Log detallado de candidatos
                for i, candidate in enumerate(candidates[:10], 1):
                    sport = candidate.get('sport', 'Unknown')
                    selection = candidate.get('selection', 'Unknown')
                    odds = candidate.get('odds', 0.0)
                    prob = candidate.get('prob', 0.0) * 100
                    value = candidate.get('value', 0.0)
                    confidence = candidate.get('confidence_level', 'unknown')
                    steam = "Ã°Å¸â€Â¥" if candidate.get('has_steam_move') else ""
                    
                    movement = candidate.get('line_movement')
                    if movement:
                        change = movement.get('change_percent', 0)
                        trend_emoji = "Ã°Å¸â€œË†" if change > 0 else "Ã°Å¸â€œâ€°" if change < 0 else "Ã¢Å¾Â¡Ã¯Â¸Â"
                        logger.info(
                            f"  [{i}] {sport}: {selection} @ {odds:.2f} "
                            f"(prob: {prob:.1f}%, value: {value:.3f}) "
                            f"{steam}{trend_emoji} {confidence} ({change:+.1f}%)"
                        )
                    else:
                        logger.info(
                            f"  [{i}] {sport}: {selection} @ {odds:.2f} "
                            f"(prob: {prob:.1f}%, value: {value:.3f}) {confidence}"
                        )
            else:
                # Scanner bÃƒÂ¡sico
                candidates = self.scanner.find_value_bets(events)
                
                logger.info(f"Ã°Å¸â€œÅ  Found {len(candidates)} value candidates (basic scan)")
                
                # Log de candidatos encontrados
                for i, candidate in enumerate(candidates[:10], 1):
                    sport = candidate.get('sport', 'Unknown')
                    selection = candidate.get('selection', 'Unknown')
                    odds = candidate.get('odds', 0.0)
                    prob = candidate.get('prob', 0.0) * 100
                    value = candidate.get('value', 0.0)
                    
                    logger.info(
                        f"  [{i}] {sport}: {selection} @ {odds:.2f} "
                        f"(prob: {prob:.1f}%, value: {value:.3f})"
                    )
            
            return candidates
            
        except Exception as e:
            logger.error(f"Ã¢ÂÅ’ Error finding value opportunities: {e}")
            return []

    async def send_alert_to_user(self, user: User, candidate: Dict) -> bool:
        """
        Enva alerta a un usuario especfico
        """
        try:
            # Verificar si el usuario puede recibir ms alertas
            if not user.can_send_alert():
                logger.debug(f"User {user.chat_id} has reached daily limit")
                return False
            
            # Verificar si es usuario premium
            if not user.is_premium_active():
                logger.debug(f"User {user.chat_id} is not premium")
                return False
            
            # Calcular stake recomendado
            odds = candidate.get('odds', 2.0)
            prob = candidate.get('prob', 0.5)
            stake = user.calculate_stake(odds, prob)
            
            # Formatear mensaje premium
            message = format_premium_alert(candidate, user, stake)
            
            # Enviar mensaje
            await self.notifier.send_message(user.chat_id, message)
            
            # Registrar alerta enviada
            user.record_alert_sent()
            self.users_manager.save_user(user)
            
            # SISTEMA MEJORADO: Guardar predicciÃƒÂ³n en BD
            if ENHANCED_SYSTEM_AVAILABLE and historical_db:
                try:
                    prediction = {
                        'match_id': candidate.get('id', ''),
                        'sport_key': candidate.get('sport_key', ''),
                        'selection': candidate.get('selection', ''),
                        'odds': odds,
                        'predicted_prob': prob,
                        'value_score': candidate.get('value', 0.0),
                        'stake': stake
                    }
                    pred_id = historical_db.save_prediction(prediction)
                    if pred_id:
                        logger.debug(f"PredicciÃƒÂ³n guardada con ID: {pred_id}")
                except Exception as e:
                    logger.error(f"Error guardando predicciÃƒÂ³n: {e}")
            
            # Agregar a sent_alerts para evitar duplicados
            alert_key = f"{user.chat_id}_{candidate.get('id', '')}_{candidate.get('selection', '')}"
            self.sent_alerts.add(alert_key)
            
            logger.info(f" Alert sent to {user.chat_id}: {candidate.get('selection', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f" Error sending alert to {user.chat_id}: {e}")
            return False

    async def process_alerts_for_imminent_events(self) -> int:
        """
        Procesa alertas para eventos que empiezan pronto
        """
        # Obtener eventos que empiezan pronto
        imminent_events = self.get_events_starting_soon(ALERT_WINDOW_HOURS)
        
        if not imminent_events:
            logger.info("No imminent events found")
            return 0
        
        logger.info(f" {len(imminent_events)} events starting within {ALERT_WINDOW_HOURS} hours")
        
        # Encontrar value bets en estos eventos
        value_candidates = await self.find_value_opportunities(imminent_events)
        
        if not value_candidates:
            logger.info("No value opportunities in imminent events")
            return 0
        
        # Obtener usuarios premium
        users = self.users_manager.get_all_users()
        premium_users = [user for user in users if user.is_premium_active()]
        
        if not premium_users:
            logger.info("No premium users to send alerts")
            return 0
        
        logger.info(f" {len(premium_users)} premium users available")
        
        total_alerts_sent = 0
        
        # Enviar alertas a usuarios premium
        for candidate in value_candidates:
            # Verificar si ya enviamos esta alerta
            candidate_key = f"{candidate.get('id', '')}_{candidate.get('selection', '')}"
            
            alerts_sent_for_candidate = 0
            
            for user in premium_users:
                # Verificar lmites
                if not user.can_send_alert():
                    continue
                
                # Verificar duplicados
                alert_key = f"{user.chat_id}_{candidate_key}"
                if alert_key in self.sent_alerts:
                    continue
                
                # Enviar alerta
                success = await self.send_alert_to_user(user, candidate)
                if success:
                    alerts_sent_for_candidate += 1
                    total_alerts_sent += 1
                
                # Limitar alertas por candidato (evitar spam)
                if alerts_sent_for_candidate >= len(premium_users):
                    break
        
        logger.info(f" Total alerts sent: {total_alerts_sent}")
        return total_alerts_sent

    async def daily_initialization(self):
        """
        Inicializacin diaria a las 6 AM
        """
        logger.info("DAILY INITIALIZATION - 6 AM America")
        
        # Reset del estado de alertas diarias
        self.alerts_state.reset_if_needed()
        
        # Reset de usuarios (contadores diarios)
        users = self.users_manager.get_all_users()
        for user in users:
            user._check_reset()  # Reset contadores diarios
        
        # Limpiar sent_alerts del da anterior
        self.sent_alerts.clear()
        
        # SISTEMA MEJORADO: Actualizar lesiones
        if ENHANCED_SYSTEM_AVAILABLE and injury_scraper:
            logger.info("Ã°Å¸â€œÅ  Actualizando lesiones de deportes...")
            try:
                # Actualizar lesiones de NBA
                nba_injuries = injury_scraper.get_injuries('nba')
                if nba_injuries:
                    for injury in nba_injuries:
                        injury['sport_key'] = 'basketball_nba'
                    saved = historical_db.save_injuries(nba_injuries)
                    logger.info(f"Ã¢Å“â€¦ {saved} lesiones NBA guardadas")
                
                # Actualizar lesiones de NFL
                nfl_injuries = injury_scraper.get_injuries('nfl')
                if nfl_injuries:
                    for injury in nfl_injuries:
                        injury['sport_key'] = 'americanfootball_nfl'
                    saved = historical_db.save_injuries(nfl_injuries)
                    logger.info(f"Ã¢Å“â€¦ {saved} lesiones NFL guardadas")
                
                # Actualizar lesiones de MLB
                mlb_injuries = injury_scraper.get_injuries('mlb')
                if mlb_injuries:
                    for injury in mlb_injuries:
                        injury['sport_key'] = 'baseball_mlb'
                    saved = historical_db.save_injuries(mlb_injuries)
                    logger.info(f"Ã¢Å“â€¦ {saved} lesiones MLB guardadas")
                    
            except Exception as e:
                logger.error(f"Error actualizando lesiones: {e}")
        
        # Fetch inicial de eventos del da
        events = await self.fetch_and_update_events()
        
        # SISTEMA MEJORADO: Guardar eventos en BD
        if ENHANCED_SYSTEM_AVAILABLE and historical_db:
            try:
                for event in events:
                    match_data = {
                        'id': event.get('id', ''),
                        'sport_key': event.get('sport_key', ''),
                        'home_team': event.get('home_team') or event.get('home', ''),
                        'away_team': event.get('away_team') or event.get('away', ''),
                        'commence_time': event.get('commence_time', '')
                    }
                    if match_data['id']:
                        historical_db.save_match(match_data)
                logger.info(f"Ã¢Å“â€¦ {len(events)} eventos guardados en BD")
            except Exception as e:
                logger.error(f"Error guardando eventos en BD: {e}")
        
        # Log resumen de eventos por deporte
        sport_counts = {}
        for event in events:
            sport = event.get('sport_key', 'unknown')
            sport_counts[sport] = sport_counts.get(sport, 0) + 1
        
        logger.info("Events by sport:")
        for sport, count in sport_counts.items():
            sport_name = translate_sport(sport, sport)
            logger.info(f"   {sport_name}: {count} events")
        
        logger.info(f" Daily initialization complete - monitoring {len(events)} events")

    async def hourly_update(self):
        """
        Actualizacin cada hora (o cada 10 minutos en producciÃƒÂ³n)
        """
        logger.info("Ã¢ÂÂ° HOURLY UPDATE")
        
        # Actualizar eventos y cuotas
        events = await self.fetch_and_update_events()
        
        # SISTEMA MEJORADO: Guardar snapshot de odds para line movement
        if ENHANCED_SYSTEM_AVAILABLE and line_tracker:
            try:
                snapshot_count = line_tracker.record_odds_snapshot(events)
                logger.info(f"Ã°Å¸â€œÂ¸ Recorded {snapshot_count} odds snapshots for line movement tracking")
            except Exception as e:
                logger.error(f"Error recording odds snapshot: {e}")
        
        # Procesar alertas para eventos inminentes
        alerts_sent = await self.process_alerts_for_imminent_events()
        
        # Log resumen
        imminent_count = len(self.get_events_starting_soon(ALERT_WINDOW_HOURS))
        total_monitored = len(self.monitored_events)
        
        logger.info(
            f"Ã°Å¸â€œÅ  Update summary: {total_monitored} events monitored, "
            f"{imminent_count} imminent, {alerts_sent} alerts sent"
        )

    async def run_continuous_monitoring(self):
        """
        Loop principal de monitoreo continuo
        """
        logger.info("Starting continuous monitoring")
        logger.info(f" Daily start: {DAILY_START_HOUR}:00 AM America")
        logger.info(f" Updates: every {UPDATE_INTERVAL_MINUTES} minutes")
        logger.info(f" Alert window: {ALERT_WINDOW_HOURS} hours before event")
        
        # Verificar configuracin
        # Verificar BOT_TOKEN (requerido)
        if not BOT_TOKEN:
            logger.error("Missing BOT_TOKEN in environment - cannot send alerts")
            return
        
        # API_KEY es opcional (se usarn datos de muestra si no est)
        if not API_KEY:
            logger.warning("No API_KEY - using sample data")
        
        while True:
            try:
                now = datetime.now(AMERICA_TZ)
                
                # Verificar si es hora de inicializacin diaria
                if self.is_daily_start_time():
                    await self.daily_initialization()
                
                # Verificar si es hora de verificaciÃƒÂ³n de resultados (2 AM)
                next_verification = self.get_next_verification_time()
                if now.hour == 2 and now.minute < 5:  # Ventana de 5 minutos
                    logger.info("Ã°Å¸â€¢Â°Ã¯Â¸Â Hora de verificaciÃƒÂ³n de resultados (2 AM)")
                    await self.verify_results()
                
                # Realizar actualizacin cada hora
                await self.hourly_update()
                
                # Calcular tiempo hasta prxima actualizacin
                next_update = self.get_next_update_time()
                sleep_seconds = (next_update - now).total_seconds()
                
                # Asegurar que dormimos al menos 1 minuto
                sleep_seconds = max(60, sleep_seconds)
                
                logger.info(f" Sleeping until next update: {next_update.strftime('%H:%M')} America ({sleep_seconds/60:.1f} min)")
                
                await asyncio.sleep(sleep_seconds)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f" Error in monitoring loop: {e}")
                logger.exception("Full traceback:")
                # Esperar 5 minutos antes de reintentar
                await asyncio.sleep(300)

    async def run_immediate_check(self):
        """
        Ejecuta un chequeo inmediato (para testing)
        """
        logger.info("Running immediate check")
        
        # Fetch eventos
        await self.fetch_and_update_events()
        
        # Procesar alertas
        alerts_sent = await self.process_alerts_for_imminent_events()
        
        # Mostrar resumen
        total_events = len(self.monitored_events)
        imminent_events = len(self.get_events_starting_soon(ALERT_WINDOW_HOURS))
        
        logger.info("Immediate check results:")
        logger.info(f"  Total events: {total_events}")
        logger.info(f"  Imminent events: {imminent_events}")
        logger.info(f"  Alerts sent: {alerts_sent}")


async def main():
    """
    Funcin principal
    """
    monitor = ValueBotMonitor()
    
    # Verificar argumentos de lnea de comandos
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        # Modo de prueba inmediata
        await monitor.run_immediate_check()
    else:
        # Modo de monitoreo continuo
        await monitor.run_continuous_monitoring()


if __name__ == "__main__":
    try:
        # Verificar que tenemos las variables necesarias
        if not API_KEY:
            print("Warning: API_KEY not found in .env - using sample data")
        
        if not BOT_TOKEN:
            print("Error: BOT_TOKEN not found in .env")
            sys.exit(1)
        
        print("Starting Value Bets Bot...")
        print(f"Monitoring: {', '.join(SPORTS)}")
        print(f"Filters: odds {MIN_ODD}-{MAX_ODD}, prob {MIN_PROB:.0%}+, max {MAX_ALERTS_PER_DAY} daily")
        print("Press Ctrl+C to stop")
        
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)