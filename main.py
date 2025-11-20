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
from data.alerts_tracker import get_alerts_tracker
from data.results_api import verify_pick_result

# Imports de Telegram para botones y handlers
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Imports del sistema mejorado (opcional)
try:
    from data.historical_db import historical_db
    from data.stats_api import injury_scraper
    from analytics.line_movement import line_tracker
    from scanner.enhanced_scanner import EnhancedValueScanner
    from scanner.ml_scanner import MLValueScanner
    from analytics.clv_tracker import clv_tracker
    from utils.kelly_criterion import kelly_calculator
    ENHANCED_SYSTEM_AVAILABLE = True  # Sistema mejorado con datos reales activado
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

# Configuracin de filtros (optimizados para exactamente 5 picks premium + 1 gratis)
MIN_ODD = float(os.getenv("MIN_ODD", "1.5"))  # Cuotas mínimas más estrictas
MAX_ODD = float(os.getenv("MAX_ODD", "3.0"))  # Cuotas máximas más conservadoras
MIN_PROB = float(os.getenv("MIN_PROB", "0.60"))  # 60% inicial, baja hasta 52% si es necesario
MAX_ALERTS_PER_DAY = int(os.getenv("MAX_ALERTS_PER_DAY", "5"))  # Exactamente 5 para premium
MIN_DAILY_PICKS = int(os.getenv("MIN_DAILY_PICKS", "3"))  # Mínimo garantizado: 3
MAX_DAILY_PICKS = int(os.getenv("MAX_DAILY_PICKS", "5"))  # Máximo: 5 picks
FREE_PICKS_PER_DAY = int(os.getenv("FREE_PICKS_PER_DAY", "1"))  # 1 pick para usuarios gratis

# Configuración ultra-profesional (reduce fallos)
MIN_CONFIDENCE_SCORE = float(os.getenv("MIN_CONFIDENCE_SCORE", "60"))  # Mínimo 60/100 de confianza
REQUIRE_LINE_MOVEMENT = os.getenv("REQUIRE_LINE_MOVEMENT", "true").lower() == "true"  # Obligar análisis de línea
REQUIRE_FAVORABLE_MOVEMENT = os.getenv("REQUIRE_FAVORABLE_MOVEMENT", "true").lower() == "true"  # Solo RLM favorable
MIN_VALUE_THRESHOLD = float(os.getenv("MIN_VALUE_THRESHOLD", "1.12"))  # Value mínimo global

# Ventana horaria para envío de alertas (hora de España)
SPAIN_TZ = ZoneInfo("Europe/Madrid")
ALERT_SEND_HOUR_START = 14  # 2 PM España
ALERT_SEND_HOUR_END = 22     # 10 PM España

# Deportes a monitorear (OPTIMIZADO: 4 deportes para 25-30 días con 20k créditos)
SPORTS = os.getenv("SPORTS", "basketball_nba,soccer_epl,soccer_spain_la_liga,tennis_atp").split(",")

# ConfiguraciÃƒÂ³n de tiempo (OPTIMIZADO para durar API credits)
AMERICA_TZ = ZoneInfo("America/New_York")  # Hora de AmÃƒÂ©rica
DAILY_START_HOUR = 6  # 6 AM
UPDATE_INTERVAL_MINUTES = 30  # 30 minutos = 48 requests/día × 4 deportes = 192 créditos/día
ALERT_WINDOW_HOURS = 8  # Alertar cuando falten menos de 8 horas (ampliado para más picks)

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
        
        # Application de Telegram para handlers de botones
        self.telegram_app = None
        
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
            logger.info("Ã¢Å¡Â Ã¯Â¸Â  Sistema mejorado no disponible, usando versiÃƒÂ³n bÃƒÂ¡sica")

    def get_main_keyboard(self, is_admin: bool = False):
        """Crea el teclado permanente con botones"""
        if is_admin:
            keyboard = [
                [KeyboardButton("📊 Mis Stats"), KeyboardButton("💰 Mis Referidos")],
                [KeyboardButton("👤 Mi Perfil"), KeyboardButton("💳 Estado Premium")],
                [KeyboardButton("⚡ Activar Premium"), KeyboardButton("💵 Marcar Pago")],
                [KeyboardButton("🔄 Reiniciar Saldo"), KeyboardButton("🔁 Reset Alertas")],
                [KeyboardButton("💎 Lista Premium"), KeyboardButton("🏆 Ranking Referidos")]
            ]
        else:
            keyboard = [
                [KeyboardButton("📊 Mis Stats"), KeyboardButton("💰 Mis Referidos")],
                [KeyboardButton("👤 Mi Perfil"), KeyboardButton("💳 Estado Premium")],
                [KeyboardButton("🏆 Ranking Referidos"), KeyboardButton("🎁 Canjear Semana")],
                [KeyboardButton("💵 Retirar Ganancias")]
            ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /start - muestra botones permanentes y procesa referrals"""
        chat_id = str(update.effective_chat.id)
        # CORREGIDO: Siempre guardar @username si existe
        username = update.effective_user.username  # username real de Telegram
        display_name = f"@{username}" if username else update.effective_user.first_name
        
        # Procesar código de referido si existe
        referrer_id = None
        if context.args and len(context.args) > 0:
            referral_code = context.args[0]
            # CORREGIDO: Buscar referrer por REFERRAL_CODE (no por chat_id)
            referrer = self.users_manager.find_user_by_referral_code(referral_code)
            if referrer:
                referrer_id = referrer.chat_id  # Guardar el chat_id del referente
                logger.info(f"🔗 Referral detectado: código {referral_code} → referente {referrer_id} → nuevo usuario {chat_id}")
            else:
                logger.warning(f"⚠️ Código de referido inválido: {referral_code}")
        
        # Registrar usuario si no existe
        user = self.users_manager.get_user(chat_id)
        if not user:
            # Guardar el username real (sin @)
            user = self.users_manager.add_user(chat_id, username or update.effective_user.first_name)
            
            # Asignar referrer si existe
            if referrer_id:
                user.referrer_id = referrer_id
                referrer = self.users_manager.get_user(referrer_id)
                if referrer:
                    if not hasattr(referrer, 'referred_users'):
                        referrer.referred_users = []
                    referrer.referred_users.append(chat_id)
                    self.users_manager.save()
                    logger.info(f"✅ Referral establecido: @{referrer.username} → @{user.username}")
                    
                    # Notificar al referrer
                    try:
                        msg = f"🎉 **¡Nuevo referido!**\n\n"
                        msg += f"👤 Usuario: @{user.username}\n"
                        msg += f"💰 Ganarás 10% de comisión cuando active Premium\n"
                        msg += f"🏆 Además, participas en el reparto semanal del 20% de ganancias"
                        await self.notifier.send_message(referrer_id, msg)
                    except Exception as e:
                        logger.error(f"Error notificando a referrer {referrer_id}: {e}")
            
            logger.info(f"Nuevo usuario registrado: {display_name} (ID: {chat_id})")
        else:
            # Actualizar username si cambió
            if username and user.username != username:
                user.username = username
                self.users_manager.save()
                logger.info(f"Username actualizado: {display_name} (ID: {chat_id})")
            
            # CORREGIR: Asignar referrer si se detectó código y el usuario aún NO tiene referrer
            if referrer_id and (not hasattr(user, 'referrer_id') or not user.referrer_id):
                user.referrer_id = referrer_id
                referrer = self.users_manager.get_user(referrer_id)
                if referrer:
                    if not hasattr(referrer, 'referred_users'):
                        referrer.referred_users = []
                    if chat_id not in referrer.referred_users:
                        referrer.referred_users.append(chat_id)
                    self.users_manager.save()
                    logger.info(f"✅ Referral asignado retroactivamente: @{referrer.username} → @{user.username}")
                    
                    # Notificar al referrer
                    try:
                        msg = f"🎉 **¡Nuevo referido!**\n\n"
                        msg += f"👤 Usuario: @{user.username}\n"
                        msg += f"💰 Ganarás 10% de comisión cuando active Premium\n"
                        msg += f"🏆 Además, participas en el reparto semanal del 20% de ganancias"
                        await self.notifier.send_message(referrer_id, msg)
                    except Exception as e:
                        logger.error(f"Error notificando a referrer {referrer_id}: {e}")
        
        is_admin = (chat_id == CHAT_ID)
        keyboard = self.get_main_keyboard(is_admin)
        
        welcome_msg = f"""
🎯 ¡Bienvenido a Value Bets Bot!

👋 Hola {display_name}

📊 **Sistema Activo:**
• Monitoreo cada 30 minutos
• 4 deportes profesionales
• Filtros ultra-estrictos (58%+ prob)
• Máximo 5 picks premium al día

💎 **Tu Estado:** {'Premium ✅' if user.is_premium_active() else 'Free (1 pick/día)'}

👇 Usa los botones para navegar:
"""
        await update.message.reply_text(welcome_msg, reply_markup=keyboard)
    
    async def handle_button_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para mensajes de botones"""
        chat_id = str(update.effective_chat.id)
        text = update.message.text
        user = self.users_manager.get_user(chat_id)
        
        if not user:
            await update.message.reply_text("❌ Usuario no registrado. Usa /start primero.")
            return
        
        is_admin = (chat_id == CHAT_ID)
        
        # Stats
        if text == "📊 Mis Stats":
            # Obtener stats por períodos
            tracker = get_alerts_tracker()
            stats_all = tracker.get_user_stats(chat_id, 'all')
            stats_week = tracker.get_user_stats(chat_id, 'week')
            stats_month = tracker.get_user_stats(chat_id, 'month')
            stats_year = tracker.get_user_stats(chat_id, 'year')
            
            msg = f"""
📊 **TUS ESTADÍSTICAS REALES**

👤 Usuario: @{user.username}
💎 Estado: {'Premium ✅' if user.is_premium_active() else 'Free'}
📅 Alertas hoy: {user.alerts_sent_today}/{MAX_ALERTS_PER_DAY if user.is_premium_active() else FREE_PICKS_PER_DAY}

━━━━━━━━━━━━━━━━━━━━━
📈 **HISTÓRICO TOTAL**
Picks: {stats_all['total']} | Win: {stats_all['win_rate']:.1f}% | ROI: {stats_all['roi']:+.1f}%
✅{stats_all['won']} ❌{stats_all['lost']} 🔄{stats_all['push']} ⏳{stats_all['pending']}
P/L: {stats_all['total_profit']:+.2f}€

📅 **ESTA SEMANA (7 días)**
Picks: {stats_week['total']} | Win: {stats_week['win_rate']:.1f}% | ROI: {stats_week['roi']:+.1f}%
P/L: {stats_week['total_profit']:+.2f}€

📆 **ESTE MES (30 días)**
Picks: {stats_month['total']} | Win: {stats_month['win_rate']:.1f}% | ROI: {stats_month['roi']:+.1f}%
P/L: {stats_month['total_profit']:+.2f}€

🗓️ **ESTE AÑO (365 días)**
Picks: {stats_year['total']} | Win: {stats_year['win_rate']:.1f}% | ROI: {stats_year['roi']:+.1f}%
P/L: {stats_year['total_profit']:+.2f}€

━━━━━━━━━━━━━━━━━━━━━
📊 **BANKROLL DINÁMICO**
Actual: {user.dynamic_bank:.2f}€ {'📈' if user.dynamic_bank >= 200 else '📉'}
Inicial: 200.00€
Cambio: {user.dynamic_bank - 200:+.2f}€ ({(user.dynamic_bank - 200) / 200 * 100:+.1f}%)

━━━━━━━━━━━━━━━━━━━━━
💡 100% transparente • Verificado automáticamente
🔄 Actualización cada 3h tras partidos
"""
            await update.message.reply_text(msg)
        
        # Referidos
        elif text == "💰 Mis Referidos":
            # CORREGIDO: Usar referral_code en vez de chat_id
            referral_code = user.referral_code if hasattr(user, 'referral_code') else chat_id
            referral_link = f"https://t.me/{context.bot.username}?start={referral_code}"
            
            # Contar referidos totales y premium
            total_refs = len(user.referred_users) if hasattr(user, 'referred_users') else 0
            
            # DEBUG: Log para ver qué pasa
            logger.info(f"DEBUG - Usuario {chat_id} tiene referred_users: {hasattr(user, 'referred_users')}")
            if hasattr(user, 'referred_users'):
                logger.info(f"DEBUG - Lista de referidos: {user.referred_users}")
            
            premium_refs = 0
            if hasattr(user, 'referred_users'):
                for ref_id in user.referred_users:
                    ref_user = self.users_manager.get_user(ref_id)
                    if ref_user and ref_user.is_premium_active():
                        premium_refs += 1
            
            # Lista de referidos (mostrar primeros 10)
            refs_list = ""
            if hasattr(user, 'referred_users') and user.referred_users:
                for ref_id in user.referred_users[:10]:
                    ref_user = self.users_manager.get_user(ref_id)
                    if ref_user:
                        status = "💎" if ref_user.is_premium_active() else "👤"
                        refs_list += f"{status} @{ref_user.username}\n"
            else:
                refs_list = "Ninguno aún"
            
            # Ganancias de referidos esta semana
            weekly_earnings = getattr(user, 'weekly_referral_earnings', 0.0)
            
            # Actualizar semanas gratis disponibles
            user.update_free_weeks()
            free_weeks = getattr(user, 'free_weeks_available', 0)
            
            msg = f"""
💰 **Sistema de Referidos**

🔗 **Tu link personal:**
`{referral_link}`

👥 **Tus referidos:**
• Total: {total_refs}
• Premium activos: {premium_refs}

🎁 **Semanas gratis:**
• Disponibles: {free_weeks}
• Progreso: {premium_refs % 5}/5 para próxima semana
• (5 premium = 1 semana gratis)

💵 **Ganancias:**
• Esta semana: {weekly_earnings:.2f}€
• Total acumulado: {user.accumulated_balance:.2f}€

📋 **Lista de referidos:**
{refs_list}

💡 **Beneficios:**
• 10% de comisión por cada premium
• Participas en reparto del 20% de ganancias
• Top 3 referrers ganan más cada semana
"""
            await update.message.reply_text(msg)
        
        # Ranking de Referidos
        elif text == "🏆 Ranking Referidos":
            users = list(self.users_manager.users.values())
            
            # Calcular stats de referidos
            referrers_stats = []
            for u in users:
                if hasattr(u, 'referred_users') and u.referred_users:
                    premium_count = 0
                    for ref_id in u.referred_users:
                        ref_user = self.users_manager.get_user(ref_id)
                        if ref_user and ref_user.is_premium_active():
                            premium_count += 1
                    
                    if premium_count > 0:
                        weekly_earnings = getattr(u, 'weekly_referral_earnings', 0.0)
                        referrers_stats.append({
                            'username': u.username,
                            'total_refs': len(u.referred_users),
                            'premium_refs': premium_count,
                            'weekly_earnings': weekly_earnings
                        })
            
            # Ordenar por premium refs
            referrers_stats.sort(key=lambda x: x['premium_refs'], reverse=True)
            
            if not referrers_stats:
                msg = "🏆 **Ranking de Referidos**\n\n❌ Aún no hay referrers con usuarios premium"
            else:
                msg = "🏆 **RANKING DE REFERIDOS**\n\n"
                msg += "Top referrers con usuarios premium activos:\n\n"
                
                for i, stat in enumerate(referrers_stats[:10], 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    msg += f"{medal} @{stat['username']}\n"
                    msg += f"   💎 Premium: {stat['premium_refs']} | Total: {stat['total_refs']}\n"
                    msg += f"   💰 Esta semana: {stat['weekly_earnings']:.2f}€\n\n"
                
                msg += "\n💡 Reparto: 🥇50% 🥈30% 🥉20% del 50% de ganancias semanales"
            
            await update.message.reply_text(msg)
        
        # Perfil
        elif text == "👤 Mi Perfil":
            msg = f"""
👤 **Tu Perfil**

🆔 ID: `{chat_id}`
📛 Usuario: @{user.username}
💎 Premium: {'Sí ✅' if user.is_premium_active() else 'No ❌'}
📅 Registrado: {user.last_reset_date}

📊 **Actividad:**
• Alertas recibidas hoy: {user.alerts_sent_today}
• Límite diario: {MAX_ALERTS_PER_DAY if user.is_premium_active() else FREE_PICKS_PER_DAY}

💰 **Finanzas:**
• Balance: {user.accumulated_balance:.2f}€
• Pago semanal: {user.get_weekly_payment():.2f}€
"""
            await update.message.reply_text(msg)
        
        # Botón Canjear Semana Gratis
        elif text == "🎁 Canjear Semana":
            # Actualizar semanas disponibles
            user.update_free_weeks()
            free_weeks = getattr(user, 'free_weeks_available', 0)
            
            if free_weeks <= 0:
                msg = """
🎁 **Canjear Semana Gratis**

❌ No tienes semanas gratis disponibles.

📊 **Cómo ganar semanas:**
• Cada 5 referidos premium = 1 semana gratis
• Invita amigos con tu link personal
• Cuando sean premium, acumulas progreso

💡 Ve a "💰 Mis Referidos" para ver tu progreso
"""
            elif getattr(user, 'pending_redemption', False):
                msg = """
🎁 **Canjear Semana Gratis**

⏳ Ya tienes una solicitud pendiente de aprobación.

El admin revisará tu solicitud pronto.
"""
            else:
                # Marcar solicitud pendiente
                user.pending_redemption = True
                self.users_manager.save()
                
                # Notificar al admin
                try:
                    admin_msg = f"""
🎁 **SOLICITUD DE CANJE - SEMANA GRATIS**

👤 Usuario: @{user.username}
🆔 ID: `{chat_id}`
📊 Referidos premium: {user.calculate_free_weeks_earned() * 5}
🎁 Semanas disponibles: {free_weeks}

¿Aprobar canje de 1 semana premium gratis?

Responde con:
`/aprobar_canje {chat_id}` - Aprobar
`/rechazar_canje {chat_id}` - Rechazar
"""
                    await self.notifier.send_message(CHAT_ID, admin_msg)
                except Exception as e:
                    logger.error(f"Error notificando admin sobre canje: {e}")
                
                msg = """
🎁 **Solicitud Enviada** ✅

Tu solicitud de canje ha sido enviada al admin.
Recibirás una notificación cuando sea aprobada.

⏳ Tiempo de respuesta: Normalmente < 24h
"""
            
            await update.message.reply_text(msg)
        
        # Botón Retirar Ganancias
        elif text == "💵 Retirar Ganancias":
            balance = getattr(user, 'accumulated_balance', 0.0)
            pending = getattr(user, 'pending_withdrawal', False)
            
            if pending:
                msg = """
💵 **Retiro de Ganancias**

⏳ Ya tienes una solicitud de retiro pendiente.

El admin la revisará pronto. Te notificaremos cuando esté lista.
"""
            elif balance <= 0:
                msg = """
💵 **Retiro de Ganancias**

❌ No tienes saldo disponible para retirar.

💡 **Cómo ganar:**
• Invita amigos con tu link de referidos
• Ganas 10% por cada referido premium
• Participa en el reparto semanal (top 3)

Ve a "💰 Mis Referidos" para ver tu link
"""
            else:
                msg = f"""
💵 **Retiro de Ganancias**

💰 **Saldo disponible:** {balance:.2f}€

¿Deseas solicitar el retiro de TODO tu saldo?

💡 Una vez aprobado por el admin:
• Recibirás tu pago
• Tu saldo se reiniciará a 0€
• Podrás seguir acumulando

Responde con: **RETIRAR** para confirmar
"""
            
            await update.message.reply_text(msg)
        
        # Confirmación de retiro
        elif text.upper() == "RETIRAR":
            balance = getattr(user, 'accumulated_balance', 0.0)
            pending = getattr(user, 'pending_withdrawal', False)
            
            if pending:
                await update.message.reply_text("⏳ Ya tienes un retiro pendiente.")
                return
            
            if balance <= 0:
                await update.message.reply_text("❌ No tienes saldo disponible.")
                return
            
            # Marcar retiro como pendiente
            user.pending_withdrawal = True
            user.withdrawal_amount = balance
            self.users_manager.save()
            
            # Notificar al admin
            try:
                admin_msg = f"""
💰 **SOLICITUD DE RETIRO**

👤 Usuario: @{user.username}
🆔 ID: `{chat_id}`
💵 Monto solicitado: {balance:.2f}€

📊 **Info del usuario:**
• Referidos totales: {len(user.referred_users) if hasattr(user, 'referred_users') else 0}
• Premium activos: {sum(1 for ref_id in (user.referred_users if hasattr(user, 'referred_users') else []) if self.users_manager.get_user(ref_id) and self.users_manager.get_user(ref_id).is_premium_active())}

¿Aprobar retiro?

Comandos:
`/aprobar_retiro {chat_id}` - Aprobar y pagar
`/rechazar_retiro {chat_id}` - Rechazar
"""
                await self.notifier.send_message(CHAT_ID, admin_msg)
            except Exception as e:
                logger.error(f"Error notificando admin sobre retiro: {e}")
            
            msg = """
✅ **Solicitud Enviada**

Tu solicitud de retiro ha sido enviada al admin.

⏳ **Próximos pasos:**
1. Admin revisa tu solicitud
2. Procesa el pago
3. Confirma y tu saldo se reinicia

📱 Te notificaremos cuando esté listo
"""
            await update.message.reply_text(msg)
        
        # Estado Premium
        elif text == "💳 Estado Premium":
            if user.is_premium_active():
                msg = f"""
💳 **Estado Premium Activo** ✅

🎯 Beneficios activos:
• 5 picks premium al día
• Filtros ultra-profesionales
• Alertas prioritarias
• Sistema de referidos 10%

💰 **Pagos:**
• Base semanal: 15€
• Ganancia referidos: {user.accumulated_balance:.2f}€
• **Total a pagar:** {user.get_weekly_payment():.2f}€

📅 Próximo reset: Lunes 06:00 AM
"""
            else:
                msg = """
💳 **Plan Free** 

🎯 Beneficios actuales:
• 1 pick gratis al día
• Acceso a sistema básico

💎 **Upgrade a Premium:**
• 5 picks diarios profesionales
• Sistema de referidos (10%)
• Filtros ultra-estrictos
• Solo 15€/semana

📞 Contacta al admin para activar
"""
            await update.message.reply_text(msg)
        
        # COMANDOS ADMIN
        elif is_admin:
            if text == "⚡ Activar Premium":
                msg = "Para activar premium a un usuario:\n\n`/activar @username`\n\nEjemplo: `/activar @juan123`"
                await update.message.reply_text(msg)
            
            elif text == "💵 Marcar Pago":
                msg = "Para marcar pago de un usuario:\n\n`/pago @username`\n\nEjemplo: `/pago @juan123`"
                await update.message.reply_text(msg)
            
            elif text == "🔄 Reiniciar Saldo":
                msg = "Para reiniciar saldo de un usuario:\n\n`/reset_saldo @username`\n\nEjemplo: `/reset_saldo @juan123`"
                await update.message.reply_text(msg)
            
            elif text == "🔁 Reset Alertas":
                msg = "Para resetear alertas de un usuario:\n\n`/reset_alertas @username`\n\nEjemplo: `/reset_alertas @juan123`"
                await update.message.reply_text(msg)
            
            elif text == "💎 Lista Premium":
                # Llamar al handler de lista premium directamente
                await self.handle_lista_premium(update, context)
        
        else:
            # Mensaje desconocido
            await update.message.reply_text("No entiendo ese comando. Usa los botones 👇")
    
    async def handle_activar_premium(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /activar @username o ID o nombre"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        if len(context.args) == 0:
            await update.message.reply_text("Uso: /activar @username o /activar chat_id o /activar nombre")
            return
        
        target_input = context.args[0].replace("@", "")
        
        # Intentar buscar: primero por username, luego por nombre, luego por ID
        target_user = self.users_manager.get_user_by_username(target_input)
        
        if not target_user:
            # Buscar por nombre (case-insensitive) - verificar que username no sea None
            for user in self.users_manager.users.values():
                if user.username and user.username.lower() == target_input.lower():
                    target_user = user
                    break
        
        if not target_user:
            # Buscar por chat_id
            target_user = self.users_manager.get_user(target_input)
        
        if not target_user:
            await update.message.reply_text(f"❌ Usuario '{target_input}' no encontrado. Usa @username, nombre o chat_id")
            return
        
        target_user.nivel = "premium"
        target_user.is_permanent_premium = True
        self.users_manager.save_users()
        
        username_display = target_user.username or f"ID:{target_user.chat_id}"
        await update.message.reply_text(f"✅ @{username_display} (ID: {target_user.chat_id}) ahora es Premium")
        logger.info(f"Admin activó premium para @{username_display}")
    
    async def handle_marcar_pago(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /pago @username o ID o nombre"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        if len(context.args) == 0:
            await update.message.reply_text("Uso: /pago @username o /pago chat_id o /pago nombre")
            return
        
        target_input = context.args[0].replace("@", "")
        
        # Buscar usuario (username, nombre o ID)
        target_user = self.users_manager.get_user_by_username(target_input)
        
        if not target_user:
            for user in self.users_manager.users.values():
                if user.username and user.username.lower() == target_input.lower():
                    target_user = user
                    break
        
        if not target_user:
            target_user = self.users_manager.get_user(target_input)
        
        if not target_user:
            await update.message.reply_text(f"❌ Usuario '{target_input}' no encontrado")
            return
        
        amount = target_user.get_weekly_payment()
        target_user.accumulated_balance = 0.0
        target_user.payment_status = "paid"
        target_user.last_payment_date = datetime.now().strftime("%Y-%m-%d")
        
        # PROCESAR COMISIÓN DE REFERIDO (10% de 15€ = 1.50€)
        commission_paid = 0.0
        logger.info(f"🔍 DEBUG /pago - Usuario {target_user.chat_id}: tiene referrer_id={hasattr(target_user, 'referrer_id')}, valor={getattr(target_user, 'referrer_id', None)}")
        if hasattr(target_user, 'referrer_id') and target_user.referrer_id:
            referrer = self.users_manager.get_user(target_user.referrer_id)
            if referrer:
                commission = 15.0 * 0.10  # 10% de 15€
                
                # Sumar comisión al referente
                if not hasattr(referrer, 'saldo_comision'):
                    referrer.saldo_comision = 0.0
                if not hasattr(referrer, 'total_commission_earned'):
                    referrer.total_commission_earned = 0.0
                
                referrer.saldo_comision += commission
                referrer.total_commission_earned += commission
                commission_paid = commission
                
                logger.info(f"💰 Comisión de {commission:.2f}€ pagada a referente {referrer.chat_id}")
                
                # Notificar al referente
                try:
                    ref_username = target_user.username or f"ID:{target_user.chat_id}"
                    msg = f"💰 **¡Nueva comisión!**\n\n"
                    msg += f"Tu referido @{ref_username} pagó Premium\n"
                    msg += f"Comisión: {commission:.2f}€ (10%)\n\n"
                    msg += f"💵 Saldo actual: {referrer.saldo_comision:.2f}€\n"
                    msg += f"📊 Total ganado: {referrer.total_commission_earned:.2f}€"
                    await self.notifier.send_message(referrer.chat_id, msg)
                except Exception as e:
                    logger.error(f"Error notificando comisión a referente: {e}")
        
        self.users_manager.save_users()
        
        username_display = target_user.username or f"ID:{target_user.chat_id}"
        response = f"✅ Pago de {amount:.2f}€ marcado para @{username_display}\n\nSaldo reiniciado a 0€\nEstado: PAGADO ✅"
        
        if commission_paid > 0:
            response += f"\n\n💰 Comisión de referido: {commission_paid:.2f}€ pagada al referente"
        
        await update.message.reply_text(response)
        logger.info(f"Admin marcó pago de {amount:.2f}€ para @{username_display}")
    
    async def handle_reset_saldo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /reset_saldo @username"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        if len(context.args) == 0:
            await update.message.reply_text("Uso: /reset_saldo @username")
            return
        
        target_username = context.args[0].replace("@", "")
        target_user = self.users_manager.get_user_by_username(target_username)
        
        if not target_user:
            await update.message.reply_text(f"❌ Usuario @{target_username} no encontrado")
            return
        
        target_user.accumulated_balance = 0.0
        self.users_manager.save_users()
        
        await update.message.reply_text(f"✅ Saldo de @{target_username} reiniciado a 0€")
        logger.info(f"Admin reinició saldo de @{target_username}")
    
    async def handle_reset_alertas(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /reset_alertas @username"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        if len(context.args) == 0:
            await update.message.reply_text("Uso: /reset_alertas @username")
            return
        
        target_username = context.args[0].replace("@", "")
        target_user = self.users_manager.get_user_by_username(target_username)
        
        if not target_user:
            await update.message.reply_text(f"❌ Usuario @{target_username} no encontrado")
            return
        
        target_user.alerts_sent_today = 0
        target_user.last_reset_date = datetime.now().strftime("%Y-%m-%d")
        self.users_manager.save_users()
        
        await update.message.reply_text(f"✅ Contador de alertas de @{target_username} reiniciado")
        logger.info(f"Admin reinició alertas de @{target_username}")
    
    async def handle_lista_premium(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /lista_premium - muestra todos los usuarios premium con deudas"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        # Obtener todos los usuarios
        all_users = list(self.users_manager.users.values())
        premium_users = [u for u in all_users if u.is_premium_active()]
        
        if not premium_users:
            await update.message.reply_text("No hay usuarios premium actualmente.")
            return
        
        # Crear reporte detallado
        report = "💎 **LISTA DE USUARIOS PREMIUM**\n"
        report += f"Total: {len(premium_users)} usuarios\n"
        report += "━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        total_adeudado = 0.0
        paid_count = 0
        pending_count = 0
        
        for i, user in enumerate(premium_users, 1):
            username = user.username or f"ID:{user.chat_id}"
            pago_base = 15.0  # PREMIUM_PRICE_EUR
            comision_refs = user.accumulated_balance
            total_user = pago_base + comision_refs
            
            # Determinar estado de pago
            payment_status = getattr(user, 'payment_status', 'pending')
            status_emoji = "✅" if payment_status == "paid" else "❌"
            
            if payment_status == "paid":
                paid_count += 1
            else:
                pending_count += 1
                total_adeudado += total_user
            
            report += f"**{i}. @{username}** {status_emoji}\n"
            report += f"   • ID: `{user.chat_id}`\n"
            report += f"   • Pago base: {pago_base:.2f}€\n"
            report += f"   • Comisión refs: {comision_refs:.2f}€\n"
            report += f"   • **Total: {total_user:.2f}€**\n"
            report += f"   • Estado: {'PAGADO ✅' if payment_status == 'paid' else 'PENDIENTE ❌'}\n"
            report += f"   • Referidos: {len(user.referrals)}\n\n"
        
        report += "━━━━━━━━━━━━━━━━━━━━━\n"
        report += f"✅ Pagados: {paid_count}\n"
        report += f"❌ Pendientes: {pending_count}\n"
        report += f"💰 **TOTAL A COBRAR: {total_adeudado:.2f}€**\n"
        report += f"\n📅 Próximo reset: Lunes 06:00 AM"
        
        # Enviar reporte (dividir si es muy largo)
        if len(report) > 4000:
            # Dividir en mensajes más pequeños
            parts = []
            current_part = "💎 **LISTA DE USUARIOS PREMIUM**\n"
            current_part += f"Total: {len(premium_users)} usuarios\n"
            current_part += "━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, user in enumerate(premium_users, 1):
                username = user.username or f"ID:{user.chat_id}"
                pago_base = 15.0
                comision_refs = user.accumulated_balance
                total_user = pago_base + comision_refs
                
                user_info = f"**{i}. @{username}**\n"
                user_info += f"   • ID: `{user.chat_id}`\n"
                user_info += f"   • Total: {total_user:.2f}€ (base: {pago_base:.2f}€ + refs: {comision_refs:.2f}€)\n\n"
                
                if len(current_part) + len(user_info) > 3800:
                    parts.append(current_part)
                    current_part = ""
                
                current_part += user_info
            
            if current_part:
                current_part += "━━━━━━━━━━━━━━━━━━━━━\n"
                current_part += f"💰 **TOTAL A COBRAR: {total_adeudado:.2f}€**"
                parts.append(current_part)
            
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(report)
        
        logger.info(f"Admin solicitó lista premium: {len(premium_users)} usuarios, total: {total_adeudado:.2f}€")
    
    async def handle_stats_reales(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /stats_reales - muestra performance real verificada"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        tracker = get_alerts_tracker()
        stats = tracker.get_global_stats()
        
        if stats['total'] == 0:
            await update.message.reply_text("📊 Aún no hay alertas enviadas para analizar.")
            return
        
        # Crear reporte
        report = "📊 **PERFORMANCE REAL VERIFICADA**\n"
        report += "━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        report += f"📈 **RESUMEN GENERAL**\n"
        report += f"Total alertas: {stats['total']}\n"
        report += f"Verificadas: {stats['won'] + stats['lost'] + stats['push']}\n"
        report += f"Pendientes: {stats['pending']}\n\n"
        
        if stats['won'] + stats['lost'] > 0:
            report += f"✅ Ganadoras: {stats['won']} ({stats['win_rate']:.1f}%)\n"
            report += f"❌ Perdidas: {stats['lost']}\n"
            report += f"🔄 Push: {stats['push']}\n\n"
            
            report += f"💰 **FINANCIERO**\n"
            report += f"Total apostado: {stats['total_staked']:.2f}€\n"
            report += f"Profit/Loss: {stats['total_profit']:+.2f}€\n"
            report += f"ROI: {stats['roi']:+.1f}%\n\n"
        
        # Stats por deporte
        if stats['by_sport']:
            report += f"🏆 **POR DEPORTE**\n"
            for sport, sport_stats in stats['by_sport'].items():
                sport_name = translate_sport(sport)
                report += f"{sport_name}: {sport_stats['won']}/{sport_stats['total']} "
                report += f"({sport_stats['win_rate']:.1f}%)\n"
        
        await update.message.reply_text(report)
        logger.info(f"Admin solicitó stats reales: {stats['won']}W-{stats['lost']}L, ROI: {stats['roi']:.1f}%")
    
    async def handle_aprobar_canje(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /aprobar_canje - aprueba canje de semana gratis"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        if not context.args or len(context.args) < 1:
            await update.message.reply_text("❌ Uso: /aprobar_canje <user_id>")
            return
        
        target_user_id = context.args[0]
        target_user = self.users_manager.get_user(target_user_id)
        
        if not target_user:
            await update.message.reply_text(f"❌ Usuario {target_user_id} no encontrado")
            return
        
        # Verificar que tenga semanas disponibles
        target_user.update_free_weeks()
        free_weeks = getattr(target_user, 'free_weeks_available', 0)
        
        if free_weeks <= 0:
            await update.message.reply_text(f"❌ @{target_user.username} no tiene semanas gratis disponibles")
            return
        
        # Activar premium por 1 semana
        target_user.nivel = "premium"
        target_user.is_permanent_premium = True  # Temporal durante 1 semana
        
        # Descontar semana gratis
        if not hasattr(target_user, 'free_weeks_redeemed'):
            target_user.free_weeks_redeemed = 0
        target_user.free_weeks_redeemed += 1
        target_user.free_weeks_available = max(0, free_weeks - 1)
        target_user.pending_redemption = False
        
        self.users_manager.save()
        
        # Notificar al usuario
        try:
            user_msg = """
🎉 **¡CANJE APROBADO!** ✅

Tu semana premium GRATIS ha sido activada.

💎 **Beneficios activos:**
• 5 picks premium al día
• Filtros ultra-profesionales
• Alertas prioritarias
• Sistema de referidos

📅 **Duración:** 7 días desde ahora

¡Disfruta tu semana premium! 🚀
"""
            await self.notifier.send_message(target_user_id, user_msg)
        except Exception as e:
            logger.error(f"Error notificando usuario {target_user_id}: {e}")
        
        # Confirmar al admin
        await update.message.reply_text(
            f"✅ Canje aprobado para @{target_user.username}\n"
            f"Premium activado por 1 semana\n"
            f"Semanas restantes: {target_user.free_weeks_available}"
        )
        logger.info(f"Admin aprobó canje de semana gratis para {target_user_id}")
    
    async def handle_rechazar_canje(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /rechazar_canje - rechaza canje de semana gratis"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        if not context.args or len(context.args) < 1:
            await update.message.reply_text("❌ Uso: /rechazar_canje <user_id>")
            return
        
        target_user_id = context.args[0]
        target_user = self.users_manager.get_user(target_user_id)
        
        if not target_user:
            await update.message.reply_text(f"❌ Usuario {target_user_id} no encontrado")
            return
        
        # Limpiar solicitud pendiente
        target_user.pending_redemption = False
        self.users_manager.save()
        
        # Notificar al usuario
        try:
            user_msg = """
❌ **Canje No Aprobado**

Tu solicitud de canje de semana gratis no fue aprobada.

Posibles razones:
• No cumples requisitos actuales
• Error en el conteo de referidos
• Otra razón específica

📞 Contacta al admin para más información.
"""
            await self.notifier.send_message(target_user_id, user_msg)
        except Exception as e:
            logger.error(f"Error notificando usuario {target_user_id}: {e}")
        
        # Confirmar al admin
        await update.message.reply_text(f"✅ Canje rechazado para @{target_user.username}")
        logger.info(f"Admin rechazó canje de semana gratis para {target_user_id}")
    
    async def handle_aprobar_retiro(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /aprobar_retiro - aprueba retiro de ganancias"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        if not context.args or len(context.args) < 1:
            await update.message.reply_text("❌ Uso: /aprobar_retiro <user_id>")
            return
        
        target_user_id = context.args[0]
        target_user = self.users_manager.get_user(target_user_id)
        
        if not target_user:
            await update.message.reply_text(f"❌ Usuario {target_user_id} no encontrado")
            return
        
        if not getattr(target_user, 'pending_withdrawal', False):
            await update.message.reply_text(f"❌ @{target_user.username} no tiene retiro pendiente")
            return
        
        withdrawal_amount = getattr(target_user, 'withdrawal_amount', 0.0)
        
        # Registrar retiro en historial
        if not hasattr(target_user, 'withdrawal_history'):
            target_user.withdrawal_history = []
        
        target_user.withdrawal_history.append({
            'date': datetime.now(timezone.utc).isoformat(),
            'amount': withdrawal_amount,
            'status': 'approved'
        })
        
        # Reiniciar saldo a 0
        target_user.accumulated_balance = 0.0
        target_user.pending_withdrawal = False
        target_user.withdrawal_amount = 0.0
        
        self.users_manager.save()
        
        # Notificar al usuario
        try:
            user_msg = f"""
✅ **¡RETIRO APROBADO!**

💰 **Monto:** {withdrawal_amount:.2f}€

El pago ha sido procesado.
Tu saldo se ha reiniciado a 0€.

¡Sigue invitando amigos para seguir ganando! 🚀

💡 Tu link de referidos está en "💰 Mis Referidos"
"""
            await self.notifier.send_message(target_user_id, user_msg)
        except Exception as e:
            logger.error(f"Error notificando usuario {target_user_id}: {e}")
        
        # Confirmar al admin
        await update.message.reply_text(
            f"✅ Retiro aprobado para @{target_user.username}\n"
            f"💰 Monto: {withdrawal_amount:.2f}€\n"
            f"Saldo reiniciado a 0€"
        )
        logger.info(f"Admin aprobó retiro de {withdrawal_amount:.2f}€ para {target_user_id}")
    
    async def handle_asignar_referido(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /asignar_referido - asigna manualmente un referido"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Uso: /asignar_referido @usuario_referido @referente\n\n"
                "Ejemplo: `/asignar_referido @juan123 @admin`"
            )
            return
        
        referred_input = context.args[0].replace("@", "")
        referrer_input = context.args[1].replace("@", "")
        
        # Buscar usuario referido
        referred_user = self.users_manager.get_user_by_username(referred_input)
        if not referred_user:
            referred_user = self.users_manager.get_user(referred_input)
        
        if not referred_user:
            await update.message.reply_text(f"❌ Usuario referido '{referred_input}' no encontrado")
            return
        
        # Buscar referente
        referrer_user = self.users_manager.get_user_by_username(referrer_input)
        if not referrer_user:
            referrer_user = self.users_manager.get_user(referrer_input)
        
        if not referrer_user:
            await update.message.reply_text(f"❌ Referente '{referrer_input}' no encontrado")
            return
        
        # Asignar referido
        referred_user.referrer_id = referrer_user.chat_id
        
        # Agregar a lista de referidos del referente
        if not hasattr(referrer_user, 'referred_users'):
            referrer_user.referred_users = []
        
        if referred_user.chat_id not in referrer_user.referred_users:
            referrer_user.referred_users.append(referred_user.chat_id)
        
        self.users_manager.save()
        
        await update.message.reply_text(
            f"✅ Referido asignado correctamente\n\n"
            f"👤 Usuario: @{referred_user.username}\n"
            f"🔗 Referente: @{referrer_user.username}\n\n"
            f"Total referidos de @{referrer_user.username}: {len(referrer_user.referred_users)}"
        )
        logger.info(f"Admin asignó @{referred_user.username} como referido de @{referrer_user.username}")
        
        # Notificar al referente
        try:
            msg = f"🎉 **¡Nuevo referido asignado!**\n\n"
            msg += f"👤 Usuario: @{referred_user.username}\n"
            msg += f"💰 Ganarás 10% de comisión cuando active Premium\n"
            msg += f"📊 Total referidos: {len(referrer_user.referred_users)}"
            await self.notifier.send_message(referrer_user.chat_id, msg)
        except Exception as e:
            logger.error(f"Error notificando a referente {referrer_user.chat_id}: {e}")
    
    async def handle_rechazar_retiro(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /rechazar_retiro - rechaza retiro de ganancias"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        if not context.args or len(context.args) < 1:
            await update.message.reply_text("❌ Uso: /rechazar_retiro <user_id>")
            return
        
        target_user_id = context.args[0]
        target_user = self.users_manager.get_user(target_user_id)
        
        if not target_user:
            await update.message.reply_text(f"❌ Usuario {target_user_id} no encontrado")
            return
        
        if not getattr(target_user, 'pending_withdrawal', False):
            await update.message.reply_text(f"❌ @{target_user.username} no tiene retiro pendiente")
            return
        
        # Limpiar solicitud pendiente
        target_user.pending_withdrawal = False
        target_user.withdrawal_amount = 0.0
        self.users_manager.save()
        
        # Notificar al usuario
        try:
            user_msg = """
❌ **Retiro No Aprobado**

Tu solicitud de retiro no fue aprobada.

Posibles razones:
• Verificación de datos pendiente
• Información incorrecta
• Otra razón específica

📞 Contacta al admin para más información.
Tu saldo sigue disponible.
"""
            await self.notifier.send_message(target_user_id, user_msg)
        except Exception as e:
            logger.error(f"Error notificando usuario {target_user_id}: {e}")
        
        # Confirmar al admin
        await update.message.reply_text(f"✅ Retiro rechazado para @{target_user.username}")
        logger.info(f"Admin rechazó retiro para {target_user_id}")
    
    async def handle_limpiar_usuarios(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /limpiar_usuarios - BORRA TODOS LOS USUARIOS"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        # Confirmación de seguridad
        if not context.args or context.args[0] != "CONFIRMAR":
            await update.message.reply_text(
                "⚠️ **ADVERTENCIA: Esto borrará TODOS los usuarios**\n\n"
                "Para confirmar escribe:\n"
                "`/limpiar_usuarios CONFIRMAR`"
            )
            return
        
        try:
            # Limpiar memoria
            count = len(self.users_manager.users)
            self.users_manager.users.clear()
            
            # Limpiar JSON
            self.users_manager.save()
            
            # Limpiar Supabase
            from data.users import supabase
            if supabase:
                supabase.table('users').delete().neq('chat_id', 'imposible').execute()
                await update.message.reply_text(
                    f"✅ **Base de datos limpiada**\n\n"
                    f"🗑️ {count} usuarios borrados de memoria y JSON\n"
                    f"🗑️ Tabla Supabase limpiada\n\n"
                    f"Ahora todos deben hacer `/start` de nuevo"
                )
            else:
                await update.message.reply_text(
                    f"✅ **Memoria limpiada**\n\n"
                    f"🗑️ {count} usuarios borrados\n"
                    f"⚠️ Supabase no disponible\n\n"
                    f"Ahora todos deben hacer `/start` de nuevo"
                )
            
            logger.info(f"Admin limpió base de datos: {count} usuarios borrados")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error limpiando usuarios: {e}")
            logger.error(f"Error en limpiar_usuarios: {e}")
    
    def setup_telegram_handlers(self):
        """Configura los handlers de Telegram para botones y comandos"""
        if not self.telegram_app:
            self.telegram_app = Application.builder().token(BOT_TOKEN).build()
        
        # Handlers de comandos
        self.telegram_app.add_handler(CommandHandler("start", self.handle_start))
        self.telegram_app.add_handler(CommandHandler("activar", self.handle_activar_premium))
        self.telegram_app.add_handler(CommandHandler("pago", self.handle_marcar_pago))
        self.telegram_app.add_handler(CommandHandler("reset_saldo", self.handle_reset_saldo))
        self.telegram_app.add_handler(CommandHandler("reset_alertas", self.handle_reset_alertas))
        self.telegram_app.add_handler(CommandHandler("lista_premium", self.handle_lista_premium))
        self.telegram_app.add_handler(CommandHandler("stats_reales", self.handle_stats_reales))
        self.telegram_app.add_handler(CommandHandler("aprobar_canje", self.handle_aprobar_canje))
        self.telegram_app.add_handler(CommandHandler("rechazar_canje", self.handle_rechazar_canje))
        self.telegram_app.add_handler(CommandHandler("aprobar_retiro", self.handle_aprobar_retiro))
        self.telegram_app.add_handler(CommandHandler("rechazar_retiro", self.handle_rechazar_retiro))
        self.telegram_app.add_handler(CommandHandler("asignar_referido", self.handle_asignar_referido))
        self.telegram_app.add_handler(CommandHandler("limpiar_usuarios", self.handle_limpiar_usuarios))
        
        # Handler para mensajes de botones
        self.telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_button_message))
        
        # Keep-alive job: ping cada 10 minutos para evitar hibernación en Render
        async def keep_alive_ping(context):
            """Auto-ping para mantener el servicio activo en Render free tier"""
            try:
                import aiohttp
                render_url = os.getenv("RENDER_EXTERNAL_URL", "https://value-bets-bot.onrender.com")
                async with aiohttp.ClientSession() as session:
                    async with session.get(render_url, timeout=10) as response:
                        if response.status == 200:
                            logger.info("⏰ Keep-alive ping OK")
                        else:
                            logger.warning(f"⚠️ Keep-alive ping: {response.status}")
            except Exception as e:
                logger.debug(f"Keep-alive error (normal): {e}")
        
        # Programar keep-alive cada 10 minutos
        job_queue = self.telegram_app.job_queue
        if job_queue:
            job_queue.run_repeating(
                keep_alive_ping,
                interval=600,  # 10 minutos
                first=60,      # Primer ping después de 1 minuto
                name="keep_alive"
            )
            logger.info("✅ Keep-alive activado: auto-ping cada 10 minutos")
        
        logger.info("[OK] Handlers de Telegram configurados")

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
        
        logger.info(f"✅ {len(events_soon)} eventos encontrados que empiezan en <{max_hours}h")
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
        Garantiza MIN_DAILY_PICKS a MAX_DAILY_PICKS picks diarios
        """
        try:
            # Usar scanner mejorado si estÃƒÂ¡ disponible
            if ENHANCED_SYSTEM_AVAILABLE and EnhancedValueScanner and isinstance(self.scanner, EnhancedValueScanner):
                # Scanner con anÃƒÂ¡lisis de line movement
                candidates = self.scanner.find_value_bets_with_movement(events)
                
                logger.info(f"🎯 Found {len(candidates)} initial candidates with movement analysis")
                
                # FILTRO ULTRA-PROFESIONAL 1: Confidence Score mínimo
                candidates = [c for c in candidates if c.get('confidence_score', 0) >= MIN_CONFIDENCE_SCORE]
                logger.info(f"📊 After confidence filter (>={MIN_CONFIDENCE_SCORE}): {len(candidates)} candidates")
                
                # FILTRO ULTRA-PROFESIONAL 2: Requerir line movement data
                if REQUIRE_LINE_MOVEMENT:
                    candidates = [c for c in candidates if c.get('line_movement') is not None]
                    logger.info(f"📈 After line movement filter: {len(candidates)} candidates")
                
                # FILTRO ULTRA-PROFESIONAL 3: Solo movimientos favorables (RLM)
                if REQUIRE_FAVORABLE_MOVEMENT:
                    candidates = [c for c in candidates 
                                if c.get('line_movement', {}).get('is_favorable', False) == True]
                    logger.info(f"✅ After favorable movement filter: {len(candidates)} candidates")
                
                # FILTRO ULTRA-PROFESIONAL 4: Value mínimo global
                candidates = [c for c in candidates if c.get('value', 0) >= MIN_VALUE_THRESHOLD]
                logger.info(f"💎 After value threshold (>={MIN_VALUE_THRESHOLD}): {len(candidates)} candidates")
                
                # FILTRO ULTRA-PROFESIONAL 5: Priorizar steam moves
                steam_candidates = [c for c in candidates if c.get('has_steam_move', False)]
                if len(steam_candidates) >= MIN_DAILY_PICKS:
                    candidates = steam_candidates
                    logger.info(f"🔥 Using only STEAM MOVES: {len(candidates)} candidates")
                
                # Log detallado de candidatos FINALES
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
                
                logger.info(f"📊 Found {len(candidates)} value candidates (basic scan)")
                
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
            
            # Sistema adaptativo: garantizar 5 picks bajando probabilidad gradualmente
            target_picks = 5
            min_confidence_adaptive = MIN_CONFIDENCE_SCORE  # Iniciar con 60
            
            if len(candidates) < target_picks:
                logger.warning(f"⚠️  Solo {len(candidates)} picks al 60%")
                logger.info(f"🔧 BAJANDO PROBABILIDAD GRADUALMENTE para alcanzar {target_picks} picks...")
                
                # Bajar de 60% → 58% → 56% → 54% → 52%
                # Y bajar confianza: 60 → 58 → 55 → 52 → 50 (mínimo 50)
                prob_levels = [0.58, 0.56, 0.54, 0.52]
                confidence_levels = [58, 55, 52, 50]
                
                for prob_level, conf_level in zip(prob_levels, confidence_levels):
                    if len(candidates) >= target_picks:
                        break
                    
                    logger.info(f"📊 Intentando con prob mínima: {prob_level*100:.0f}%...")
                    min_confidence_adaptive = conf_level  # Actualizar umbral de confianza
                    if len(candidates) >= target_picks:
                        break
                    
                    logger.info(f"📊 Intentando con prob mínima: {prob_level*100:.0f}%...")
                    
                    relaxed_scanner = EnhancedValueScanner(
                        min_odd=MIN_ODD,
                        max_odd=MAX_ODD,
                        min_prob=prob_level
                    ) if ENHANCED_SYSTEM_AVAILABLE else ValueScanner(
                        min_odd=MIN_ODD,
                        max_odd=MAX_ODD,
                        min_prob=prob_level
                    )
                    
                    if ENHANCED_SYSTEM_AVAILABLE:
                        new_candidates = relaxed_scanner.find_value_bets_with_movement(events)
                    else:
                        new_candidates = relaxed_scanner.find_value_bets(events)
                    
                    # Añadir solo los que no están ya en la lista
                    for c in new_candidates:
                        if c not in candidates:
                            candidates.append(c)
                    
                    logger.info(f"   ✅ Total acumulado: {len(candidates)} picks")
                
                logger.info(f"🎯 RESULTADO FINAL: {len(candidates)} picks encontrados")
            
            # Guardar el umbral de confianza adaptado en cada candidato
            for candidate in candidates:
                candidate['min_confidence_used'] = min_confidence_adaptive
            
            # Filtrar solo picks con confianza ≥55 (calidad mínima)
            quality_candidates = [c for c in candidates if c.get('confidence_score', 0) >= 55]
            
            if not quality_candidates:
                logger.info(f"📊 {len(candidates)} picks encontrados pero ninguno cumple umbral de confianza ≥55")
                logger.info(f"⏭️ No se enviará ningún pick. Esperando siguiente check...")
                return []
            
            # Ordenar por valor (enviar solo el mejor)
            quality_candidates.sort(key=lambda x: x.get('value', 0), reverse=True)
            
            # Enviar SOLO el mejor pick cada 30 minutos
            best_pick = quality_candidates[0]
            logger.info(f"📊 {len(quality_candidates)} picks con confianza ≥55")
            logger.info(f"🎯 Enviando SOLO el mejor pick (valor: {best_pick.get('value', 0):.3f}, confianza: {best_pick.get('confidence_score', 0):.1f})")
            
            return [best_pick]  # Solo el mejor
            
        except Exception as e:
            logger.error(f"Ã¢ÂÅ’ Error finding value opportunities: {e}")
            return []

    async def send_alert_to_user(self, user: User, candidate: Dict) -> bool:
        """
        Enva alerta a un usuario especfico con DOUBLE-CHECK ultra-profesional
        """
        try:
            # DEBUG: Log candidato recibido
            logger.info(f"DEBUG: Attempting to send alert - User: {user.chat_id}, Candidate: {candidate.get('selection', 'N/A')}, Odds: {candidate.get('odds', 'N/A')}")
            
            # DOUBLE-CHECK 1: Verificar límites de usuario
            if not user.can_send_alert():
                logger.info(f"DEBUG: User {user.chat_id} REJECTED - reached daily limit")
                return False
            
            # DOUBLE-CHECK 2: Verificar premium (excepto para picks gratis)
            if not user.is_premium_active() and user.alerts_sent_today >= FREE_PICKS_PER_DAY:
                logger.info(f"DEBUG: User {user.chat_id} REJECTED - not premium and already received free pick")
                return False
            
            # DOUBLE-CHECK 3: Re-verificar que el pick cumple criterios mínimos
            odds = candidate.get('odds', 0)
            prob = candidate.get('prob', 0)
            value = candidate.get('value', 0)
            confidence = candidate.get('confidence_score', 0)
            min_conf_threshold = candidate.get('min_confidence_used', MIN_CONFIDENCE_SCORE)  # Usar umbral adaptado
            
            if odds < MIN_ODD or odds > MAX_ODD:
                logger.warning(f"⚠️ REJECTED: Odds {odds} fuera de rango ({MIN_ODD}-{MAX_ODD})")
                return False
            
            if prob < MIN_PROB:
                logger.warning(f"⚠️ REJECTED: Prob {prob:.1%} menor que mínimo {MIN_PROB:.1%}")
                return False
            
            if value < MIN_VALUE_THRESHOLD:
                logger.warning(f"⚠️ REJECTED: Value {value:.3f} menor que mínimo {MIN_VALUE_THRESHOLD}")
                return False
            
            if confidence < min_conf_threshold:
                logger.warning(f"⚠️ REJECTED: Confidence {confidence} menor que mínimo adaptado {min_conf_threshold}")
                return False
            
            # DOUBLE-CHECK 4: Verificar que el evento no ha empezado
            commence_time = candidate.get('commence_time')
            if commence_time:
                if isinstance(commence_time, str):
                    commence_time = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
                if commence_time <= datetime.now(timezone.utc):
                    logger.warning(f"⚠️ REJECTED: Evento ya comenzó")
                    return False
            
            logger.info(f"✅ DOUBLE-CHECK PASSED - User {user.chat_id}")
            
            # Calcular stake recomendado
            stake = user.calculate_stake(odds, prob)
            
            logger.info(f"DEBUG: Stake calculated: {stake}")
            
            # Formatear mensaje premium
            try:
                message = format_premium_alert(candidate, user, stake)
                logger.info(f"DEBUG: Message formatted successfully, length: {len(message)}")
            except Exception as e:
                logger.error(f"DEBUG: ERROR formatting message: {e}")
                return False
            
            # Enviar mensaje
            try:
                await self.notifier.send_message(user.chat_id, message)
                logger.info(f"DEBUG: Message sent successfully to {user.chat_id}")
            except Exception as e:
                logger.error(f"DEBUG: ERROR sending message: {e}")
                return False
            
            # Registrar alerta enviada
            user.record_alert_sent()
            self.users_manager.save()
            
            # Registrar alerta en el tracker para verificación posterior
            tracker = get_alerts_tracker()
            
            # Usar línea y cuota ajustadas si existen
            final_odds = candidate.get('odds', odds)
            final_point = candidate.get('point')
            final_selection = candidate.get('selection', '')
            
            # Guardar también info de línea original si fue ajustada
            original_info = {}
            if candidate.get('was_adjusted'):
                original_info = {
                    'original_odds': candidate.get('original_odds'),
                    'original_point': candidate.get('original_point'),
                    'was_adjusted': True
                }
            
            tracker.add_alert(
                user_id=user.chat_id,
                event_id=candidate.get('id', ''),
                sport=candidate.get('sport_key', ''),
                pick_type=candidate.get('market', 'h2h'),
                selection=final_selection,
                odds=final_odds,  # Usar cuota ajustada
                stake=stake,
                point=final_point,  # Usar punto ajustado
                game_time=candidate.get('commence_time'),
                **original_info  # Añadir info de ajuste si existe
            )
            logger.info(f"✅ Alert tracked for verification: {final_selection} @ {final_odds:.2f}")
            if candidate.get('was_adjusted'):
                logger.info(f"   📊 Línea ajustada desde {candidate.get('original_point')} @ {candidate.get('original_odds'):.2f}")
            
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
            logger.info(f"DEBUG: About to return True")
            return True
            
        except Exception as e:
            logger.error(f" Error sending alert to {user.chat_id}: {e}")
            logger.error(f"DEBUG: Exception details: {type(e).__name__}: {str(e)}")
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
        
        # Añadir información de bookmakers completa a cada candidato
        for candidate in value_candidates:
            event_id = candidate.get('id')
            if event_id:
                # Buscar evento original en monitored_events para obtener bookmakers completos
                for monitored_event in imminent_events:
                    if monitored_event.get('id') == event_id:
                        candidate['event_bookmakers'] = monitored_event.get('bookmakers', [])
                        break
        
        # Ajustar líneas si cuotas > 2.1
        from utils.line_adjuster import adjust_line_if_needed
        adjusted_candidates = []
        for candidate in value_candidates:
            event_bookmakers = candidate.get('event_bookmakers', [])
            adjusted = adjust_line_if_needed(candidate, event_bookmakers)
            adjusted_candidates.append(adjusted)
        
        value_candidates = adjusted_candidates
        
        # Obtener usuarios premium y gratuitos
        users = list(self.users_manager.users.values())
        
        # Forzar check de reset diario para todos los usuarios
        for user in users:
            user._check_reset()
        
        premium_users = [user for user in users if user.is_premium_active()]
        free_users = [user for user in users if not user.is_premium_active()]
        
        logger.info(f"📊 {len(premium_users)} premium users, {len(free_users)} free users available")
        
        total_alerts_sent = 0
        
        # Enviar solo el mejor pick encontrado (confianza ≥55)
        if not value_candidates:
            logger.info("⏭️ No hay picks de calidad para enviar")
            return 0
        
        best_pick = value_candidates[0]  # Solo el mejor
        logger.info(f"📤 Enviando mejor pick: {best_pick.get('selection')} @ {best_pick.get('odds')} (valor: {best_pick.get('value', 0):.3f})")
        
        # Verificar si ya enviamos esta alerta
        candidate_key = f"{best_pick.get('id', '')}_{best_pick.get('selection', '')}"
        
        # 1. Enviar a PREMIUM users
        for user in premium_users:
            # Verificar límites (premium puede recibir hasta 5 al día)
            if user.alerts_sent_today >= 5:
                continue
            
            # Verificar duplicados
            alert_key = f"{user.chat_id}_{candidate_key}"
            if alert_key in self.sent_alerts:
                continue
            
            # Enviar alerta
            success = await self.send_alert_to_user(user, best_pick)
            if success:
                total_alerts_sent += 1
        
        # 2. Enviar a FREE users (mismo pick, máximo 1 al día)
        for user in free_users:
            # Usuarios gratis: MÁXIMO 1 al día
            if user.alerts_sent_today >= 1:
                continue
            
            best_pick_key = f"{best_pick.get('id', '')}_{best_pick.get('selection', '')}"
            
            # Verificar duplicados
            alert_key = f"{user.chat_id}_{best_pick_key}"
            if alert_key in self.sent_alerts:
                continue
            
            # Enviar alerta
            success = await self.send_alert_to_user(user, best_pick)
            if success:
                total_alerts_sent += 1
        
        logger.info(f"✅ Total alerts sent: {total_alerts_sent}")
        return total_alerts_sent

    async def daily_initialization(self):
        """
        Inicializacin diaria a las 6 AM
        """
        logger.info("DAILY INITIALIZATION - 6 AM America")
        
        # Reset del estado de alertas diarias
        self.alerts_state.reset_if_needed()
        
        # Reset de usuarios (contadores diarios)
        users = list(self.users_manager.users.values())
        for user in users:
            user._check_reset()  # Reset contadores diarios
        
        # Verificar si es lunes para reset semanal
        now = datetime.now(AMERICA_TZ)
        if now.weekday() == 0:  # 0 = Lunes
            await self.weekly_reset()
        
        # Limpiar sent_alerts del da anterior
        self.sent_alerts.clear()
        
        # SISTEMA MEJORADO: Actualizar lesiones
        if ENHANCED_SYSTEM_AVAILABLE and injury_scraper:
            logger.info("Actualizando lesiones de deportes...")
            try:
                # Actualizar lesiones de NBA
                nba_injuries = injury_scraper.get_injuries('nba')
                if nba_injuries:
                    for injury in nba_injuries:
                        injury['sport_key'] = 'basketball_nba'
                    saved = historical_db.save_injuries(nba_injuries)
                    logger.info(f"{saved} lesiones NBA guardadas")
                
                # Actualizar lesiones de NFL
                nfl_injuries = injury_scraper.get_injuries('nfl')
                if nfl_injuries:
                    for injury in nfl_injuries:
                        injury['sport_key'] = 'americanfootball_nfl'
                    saved = historical_db.save_injuries(nfl_injuries)
                    logger.info(f"{saved} lesiones NFL guardadas")
                
                # Actualizar lesiones de MLB
                mlb_injuries = injury_scraper.get_injuries('mlb')
                if mlb_injuries:
                    for injury in mlb_injuries:
                        injury['sport_key'] = 'baseball_mlb'
                    saved = historical_db.save_injuries(mlb_injuries)
                    logger.info(f"{saved} lesiones MLB guardadas")
                    
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
                logger.info(f"{len(events)} eventos guardados en BD")
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
        
        logger.info(f"Daily initialization complete - monitoring {len(events)} events")
    
    async def weekly_reset(self):
        """
        Reset semanal (lunes 06:00 AM):
        - Quitar premium a usuarios que no pagaron
        - Resetear estados de pago a 'pending'
        - Calcular 20% de ganancias semanales
        - Distribuir 50% a admin y 50% a top 3 referrers
        - Resetear saldos de comisiones
        """
        logger.info("🔄 WEEKLY RESET - Lunes 06:00 AM")
        
        users = list(self.users_manager.users.values())
        premium_users = [u for u in users if u.is_premium_active()]
        
        removed_count = 0
        reset_count = 0
        total_profit_share = 0.0
        
        # Calcular 20% de ganancias de todos los usuarios premium
        for user in premium_users:
            # Calcular ganancia semanal (bank actual - bank inicio semana)
            current_bank = getattr(user, 'dynamic_bank', 200.0)
            week_start = getattr(user, 'week_start_bank', 200.0)
            weekly_profit = current_bank - week_start
            
            if weekly_profit > 0:
                # 20% de las ganancias
                fee_due = weekly_profit * 0.20
                user.weekly_fee_due = fee_due
                user.weekly_profit = weekly_profit
                total_profit_share += fee_due
                logger.info(f"💰 @{user.username} ganó {weekly_profit:.2f}€ → debe {fee_due:.2f}€ (20%)")
            else:
                user.weekly_fee_due = 0.0
                user.weekly_profit = weekly_profit
                logger.info(f"📊 @{user.username} profit: {weekly_profit:.2f}€ (sin cargo)")
            
            # Resetear bank inicio semana para nueva semana
            user.week_start_bank = current_bank
        
        # Distribuir 50% a admin y 50% a top 3 referrers
        if total_profit_share > 0:
            bot_share = total_profit_share * 0.50
            referrers_share = total_profit_share * 0.50
            
            logger.info(f"💵 Total 20% ganancias: {total_profit_share:.2f}€")
            logger.info(f"🤖 Bot share (50%): {bot_share:.2f}€")
            logger.info(f"👥 Referrers share (50%): {referrers_share:.2f}€")
            
            # Calcular top 3 referrers por cantidad de referidos premium
            referrers_stats = []
            for user in users:
                if user.referred_users:
                    premium_referrals = [
                        u for u in user.referred_users 
                        if self.users_manager.get_user(u) and self.users_manager.get_user(u).is_premium_active()
                    ]
                    if premium_referrals:
                        referrers_stats.append({
                            'user': user,
                            'premium_count': len(premium_referrals),
                            'referred_ids': premium_referrals
                        })
            
            # Ordenar por cantidad de premium referrals
            referrers_stats.sort(key=lambda x: x['premium_count'], reverse=True)
            top_3 = referrers_stats[:3]
            
            if top_3:
                # Distribuir con incentivos: 50%, 30%, 20%
                percentages = [0.50, 0.30, 0.20]
                medals = ["🥇", "🥈", "🥉"]
                
                logger.info(f"🏆 TOP 3 REFERRERS:")
                for i, ref_stat in enumerate(top_3):
                    ref_user = ref_stat['user']
                    percentage = percentages[i]
                    earnings = referrers_share * percentage
                    ref_user.weekly_referral_earnings = earnings
                    
                    logger.info(f"   {i+1}. @{ref_user.username}: {ref_stat['premium_count']} premium → {earnings:.2f}€ ({int(percentage*100)}%)")
                    
                    # Notificar al referrer
                    try:
                        msg = f"{medals[i]} **¡Felicidades! Eres TOP {i+1} Referrer**\n\n"
                        msg += f"📊 Referidos Premium activos: {ref_stat['premium_count']}\n"
                        msg += f"💰 Tu parte: {int(percentage*100)}% = {earnings:.2f}€\n\n"
                        if i == 0:
                            msg += f"🏆 ¡Increíble! Como #1 te llevas el 50% del reparto\n"
                        elif i == 1:
                            msg += f"💪 ¡Muy bien! Como #2 ganas el 30% del reparto\n"
                        else:
                            msg += f"👏 ¡Excelente! Como #3 obtienes el 20% del reparto\n"
                        msg += f"\nSigue invitando usuarios premium para seguir ganando! 🚀"
                        await self.notifier.send_message(ref_user.chat_id, msg)
                    except Exception as e:
                        logger.error(f"Error notificando a referrer {ref_user.chat_id}: {e}")
            else:
                logger.info("ℹ️ No hay referrers activos con premium referrals")
        
        # Procesar usuarios premium (remover o resetear)
        for user in premium_users:
            payment_status = getattr(user, 'payment_status', 'pending')
            
            # Si NO pagó, quitar premium
            if payment_status != 'paid':
                user.nivel = "gratis"
                user.is_permanent_premium = False
                removed_count += 1
                logger.info(f"❌ Premium removido: @{user.username} (ID: {user.chat_id}) - No pagó")
                
                # Notificar al usuario
                try:
                    msg = "⚠️ **Tu suscripción Premium ha expirado**\n\n"
                    msg += "No se detectó el pago semanal de 15€.\n\n"
                    msg += "Para reactivar Premium:\n"
                    msg += "1. Realiza el pago de 15€\n"
                    msg += "2. Contacta al admin\n\n"
                    msg += "💡 Vuelve a tener acceso premium en cuanto pagues."
                    await self.notifier.send_message(user.chat_id, msg)
                except Exception as e:
                    logger.error(f"Error notificando a {user.chat_id}: {e}")
            else:
                # Si pagó, resetear estado para nueva semana
                user.payment_status = 'pending'
                user.weekly_fee_paid = False
                reset_count += 1
                logger.info(f"✅ Estado reseteado: @{user.username} (ID: {user.chat_id}) - Sigue activo")
        
        # Guardar cambios
        self.users_manager.save_users()
        
        logger.info(f"🔄 Weekly reset completado:")
        logger.info(f"   - Premiums removidos: {removed_count}")
        logger.info(f"   - Estados reseteados: {reset_count}")
        logger.info(f"   - Premiums activos: {reset_count}")
    
    async def verify_pending_results(self):
        """
        Verifica resultados de alertas pendientes y actualiza bankrolls
        Se ejecuta cada 3 horas para verificar partidos completados
        """
        logger.info("🔍 Verificando resultados de alertas pendientes...")
        
        tracker = get_alerts_tracker()
        pending = tracker.get_pending_alerts(hours_old=3)
        
        if not pending:
            logger.info("   No hay alertas pendientes para verificar")
            return
        
        verified_count = 0
        won_count = 0
        lost_count = 0
        push_count = 0
        
        for alert in pending:
            alert_id = alert['alert_id']
            
            try:
                # Verificar resultado usando la API
                result = verify_pick_result(
                    event_id=alert['event_id'],
                    sport=alert['sport'],
                    pick_type=alert['pick_type'],
                    selection=alert['selection'],
                    point=alert.get('point')
                )
                
                if result is None:
                    continue
                
                verified_count += 1
                
                # Calcular profit/loss CON CUOTA AJUSTADA
                stake = alert['stake']
                odds = alert['odds']  # Esta es la cuota ajustada que se envió
                
                if result == 'won':
                    profit_loss = stake * (odds - 1)
                    won_count += 1
                    emoji = "✅"
                elif result == 'lost':
                    profit_loss = -stake
                    lost_count += 1
                    emoji = "❌"
                else:
                    profit_loss = 0
                    push_count += 1
                    emoji = "🔄"
                
                # Log si era línea ajustada
                if alert.get('was_adjusted'):
                    logger.info(f"   📊 Línea ajustada verificada: {alert['selection']} @ {odds:.2f} (original: {alert.get('original_odds'):.2f})")
                
                # Actualizar tracker
                tracker.update_alert_result(alert_id, result, profit_loss)
                
                # Actualizar bankroll del usuario CON PROFIT/LOSS DE CUOTA AJUSTADA
                user = self.users_manager.get_user(alert['user_id'])
                if user and hasattr(user, 'dynamic_bank'):
                    old_bank = user.dynamic_bank
                    user.dynamic_bank += profit_loss
                    logger.info(f"   💰 User {alert['user_id']}: {result.upper()} @ {odds:.2f} → {profit_loss:+.2f}€ (Bank: {old_bank:.2f} → {user.dynamic_bank:.2f})")
                    if alert.get('was_adjusted'):
                        logger.info(f"      🔧 Resultado basado en línea ajustada (no original)")
                
                # Notificar resultado
                try:
                    if result == 'won':
                        msg = f"✅ **PICK GANADOR**\n\n🎯 {alert['selection']}"
                        if alert.get('point'):
                            msg += f" {alert['point']}"
                        msg += f"\n💰 Cuota: {odds:.2f}"
                        msg += f"\n💵 Ganancia: +{profit_loss:.2f}€"
                        if alert.get('was_adjusted'):
                            msg += f"\n📊 (Línea ajustada desde {alert.get('original_point')} @ {alert.get('original_odds'):.2f})"
                    elif result == 'lost':
                        msg = f"❌ **PICK PERDIDO**\n\n🎯 {alert['selection']}"
                        if alert.get('point'):
                            msg += f" {alert['point']}"
                        msg += f"\n💰 Cuota: {odds:.2f}"
                        msg += f"\n💸 Pérdida: {profit_loss:.2f}€"
                    else:
                        msg = f"🔄 **EMPATE (Push)**\n\n🎯 {alert['selection']}"
                        if alert.get('point'):
                            msg += f" {alert['point']}"
                        msg += f"\n💰 Stake devuelto: {stake:.2f}€"
                    
                    if user and hasattr(user, 'dynamic_bank'):
                        msg += f"\n\n📊 **Bankroll actual:** {user.dynamic_bank:.2f}€"
                    
                    await self.notifier.send_message(alert['user_id'], msg)
                except Exception as e:
                    logger.error(f"Error notificando: {e}")
                
            except Exception as e:
                logger.error(f"Error verificando alerta {alert_id}: {e}")
        
        self.users_manager.save()
        
        logger.info(f"✅ Verificación completada: {verified_count} verificadas ({won_count}W-{lost_count}L-{push_count}P)")
    
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
        
        # Configurar handlers de Telegram
        self.setup_telegram_handlers()
        
        # Iniciar el bot de Telegram (inicializar y empezar)
        logger.info("Iniciando bot de Telegram para comandos...")
        
        # ESPERA LARGA en Render para que instancia anterior termine completamente
        if os.getenv('RENDER'):
            wait_time = 60  # 1 minuto completo
            logger.info(f"⏳ RENDER: Esperando {wait_time}s para que instancia anterior termine...")
            await asyncio.sleep(wait_time)
        
        # Iniciar con polling simple
        try:
            await self.telegram_app.initialize()
            await self.telegram_app.start()
            await self.telegram_app.updater.start_polling(drop_pending_updates=True)
            logger.info("✅ Bot de Telegram activo")
        except Exception as e:
            logger.error(f"❌ Error iniciando bot: {e}")
            raise
        
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
                
                # Verificar resultados de picks cada 3 horas
                if now.hour % 3 == 0 and now.minute < 5:
                    await self.verify_pending_results()
                
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
