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
MIN_PROB = float(os.getenv("MIN_PROB", "0.58"))  # 58% mínimo ultra-profesional
MAX_ALERTS_PER_DAY = int(os.getenv("MAX_ALERTS_PER_DAY", "5"))  # Exactamente 5 para premium
MIN_DAILY_PICKS = int(os.getenv("MIN_DAILY_PICKS", "3"))  # Mínimo garantizado: 3
MAX_DAILY_PICKS = int(os.getenv("MAX_DAILY_PICKS", "5"))  # Máximo: 5 picks
FREE_PICKS_PER_DAY = int(os.getenv("FREE_PICKS_PER_DAY", "1"))  # 1 pick para usuarios gratis

# Configuración ultra-profesional (reduce fallos)
MIN_CONFIDENCE_SCORE = float(os.getenv("MIN_CONFIDENCE_SCORE", "60"))  # Mínimo 60/100 de confianza
REQUIRE_LINE_MOVEMENT = os.getenv("REQUIRE_LINE_MOVEMENT", "true").lower() == "true"  # Obligar análisis de línea
REQUIRE_FAVORABLE_MOVEMENT = os.getenv("REQUIRE_FAVORABLE_MOVEMENT", "true").lower() == "true"  # Solo RLM favorable
MIN_VALUE_THRESHOLD = float(os.getenv("MIN_VALUE_THRESHOLD", "1.12"))  # Value mínimo global

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
                [KeyboardButton("💎 Lista Premium")]
            ]
        else:
            keyboard = [
                [KeyboardButton("📊 Mis Stats"), KeyboardButton("💰 Mis Referidos")],
                [KeyboardButton("👤 Mi Perfil"), KeyboardButton("💳 Estado Premium")]
            ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /start - muestra botones permanentes"""
        chat_id = str(update.effective_chat.id)
        username = update.effective_user.username or update.effective_user.first_name
        
        # Registrar usuario si no existe
        user = self.users_manager.get_user(chat_id)
        if not user:
            user = self.users_manager.add_user(chat_id, username)
            logger.info(f"Nuevo usuario registrado: {username} ({chat_id})")
        
        is_admin = (chat_id == CHAT_ID)
        keyboard = self.get_main_keyboard(is_admin)
        
        welcome_msg = f"""
🎯 ¡Bienvenido a Value Bets Bot!

👋 Hola @{username}

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
            referral_link = f"https://t.me/{context.bot.username}?start={chat_id}"
            total_refs = len(user.referrals)
            
            refs_list = "\n".join([f"• @{r}" for r in user.referrals[:10]]) if user.referrals else "Ninguno aún"
            
            msg = f"""
💰 **Sistema de Referidos**

🔗 **Tu link personal:**
`{referral_link}`

👥 Referidos totales: {total_refs}
💵 Ganancia acumulada: {user.accumulated_balance:.2f}€

📋 **Tus referidos:**
{refs_list}

💡 **Beneficios:**
• 20% de las ganancias de cada referido
• Se acumula semanalmente
• Pago junto con tu tarifa base
"""
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
        
        # Estado Premium
        elif text == "💳 Estado Premium":
            if user.is_premium_active():
                msg = f"""
💳 **Estado Premium Activo** ✅

🎯 Beneficios activos:
• 5 picks premium al día
• Filtros ultra-profesionales
• Alertas prioritarias
• Sistema de referidos 20%

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
• Sistema de referidos (20%)
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
        """Handler para /activar @username"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        if len(context.args) == 0:
            await update.message.reply_text("Uso: /activar @username")
            return
        
        target_username = context.args[0].replace("@", "")
        target_user = self.users_manager.get_user_by_username(target_username)
        
        if not target_user:
            await update.message.reply_text(f"❌ Usuario @{target_username} no encontrado")
            return
        
        target_user.nivel = "premium"
        target_user.is_permanent_premium = True
        self.users_manager.save_users()
        
        await update.message.reply_text(f"✅ @{target_username} ahora es Premium")
        logger.info(f"Admin activó premium para @{target_username}")
    
    async def handle_marcar_pago(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para /pago @username"""
        chat_id = str(update.effective_chat.id)
        
        if chat_id != CHAT_ID:
            await update.message.reply_text("❌ Solo el admin puede usar este comando")
            return
        
        if len(context.args) == 0:
            await update.message.reply_text("Uso: /pago @username")
            return
        
        target_username = context.args[0].replace("@", "")
        target_user = self.users_manager.get_user_by_username(target_username)
        
        if not target_user:
            await update.message.reply_text(f"❌ Usuario @{target_username} no encontrado")
            return
        
        amount = target_user.get_weekly_payment()
        target_user.accumulated_balance = 0.0
        target_user.payment_status = "paid"
        target_user.last_payment_date = datetime.now().strftime("%Y-%m-%d")
        self.users_manager.save_users()
        
        await update.message.reply_text(f"✅ Pago de {amount:.2f}€ marcado para @{target_username}\n\nSaldo reiniciado a 0€\nEstado: PAGADO ✅")
        logger.info(f"Admin marcó pago de {amount:.2f}€ para @{target_username}")
    
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
        
        # Handler para mensajes de botones
        self.telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_button_message))
        
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
            
            # Sistema de selección de picks: garantizar MIN_DAILY_PICKS (3) a MAX_DAILY_PICKS (5)
            if len(candidates) < MIN_DAILY_PICKS:
                logger.warning(f"⚠️  Solo {len(candidates)} picks con filtros ultra-profesionales")
                logger.info(f"🔧 RELAJACIÓN PROGRESIVA para alcanzar mínimo {MIN_DAILY_PICKS}...")
                
                # NIVEL 1: Relajar confidence a 50 (mantener line movement)
                if len(candidates) < MIN_DAILY_PICKS:
                    logger.info("📊 Nivel 1: Relajando confidence a 50...")
                    relaxed_candidates = self.scanner.find_value_bets_with_movement(events) if ENHANCED_SYSTEM_AVAILABLE else self.scanner.find_value_bets(events)
                    
                    # Filtrar con confidence 50 (en vez de 60)
                    level1_candidates = [c for c in relaxed_candidates if c.get('confidence_score', 0) >= 50]
                    if REQUIRE_LINE_MOVEMENT:
                        level1_candidates = [c for c in level1_candidates if c.get('line_movement') is not None]
                    
                    logger.info(f"   Resultado Nivel 1: {len(level1_candidates)} picks")
                    candidates.extend([c for c in level1_candidates if c not in candidates])
                
                # NIVEL 2: Relajar line movement (opcional en vez de obligatorio)
                if len(candidates) < MIN_DAILY_PICKS:
                    logger.info("📊 Nivel 2: Line movement opcional...")
                    relaxed_scanner = EnhancedValueScanner(
                        min_odd=1.5,
                        max_odd=3.0,
                        min_prob=0.55  # Mantener 55%
                    ) if ENHANCED_SYSTEM_AVAILABLE else ValueScanner(
                        min_odd=1.5,
                        max_odd=3.0,
                        min_prob=0.55
                    )
                    
                    if ENHANCED_SYSTEM_AVAILABLE:
                        level2_candidates = relaxed_scanner.find_value_bets_with_movement(events)
                    else:
                        level2_candidates = relaxed_scanner.find_value_bets(events)
                    
                    # Filtrar solo por confidence >=50 y value >=1.10
                    level2_candidates = [c for c in level2_candidates 
                                       if c.get('confidence_score', 0) >= 50 
                                       and c.get('value', 0) >= 1.10]
                    
                    logger.info(f"   Resultado Nivel 2: {len(level2_candidates)} picks")
                    candidates.extend([c for c in level2_candidates if c not in candidates])
                
                # NIVEL 3: Filtros básicos (si aún falta)
                if len(candidates) < MIN_DAILY_PICKS:
                    logger.info("📊 Nivel 3: Filtros básicos profesionales...")
                    basic_scanner = ValueScanner(
                        min_odd=1.4,
                        max_odd=3.5,
                        min_prob=0.52  # 52% mínimo
                    )
                    level3_candidates = basic_scanner.find_value_bets(events)
                    
                    # Solo añadir los mejores por EV
                    for c in level3_candidates:
                        c['expected_value'] = (c.get('prob', 0) * c.get('odds', 0)) - 1
                    
                    level3_candidates.sort(key=lambda x: x.get('expected_value', 0), reverse=True)
                    logger.info(f"   Resultado Nivel 3: {len(level3_candidates)} picks")
                    candidates.extend([c for c in level3_candidates[:10] if c not in candidates])
                
                logger.info(f"✅ Total después de relajación: {len(candidates)} picks")
                
                # Ordenar todos por EV y tomar los mejores
                for c in candidates:
                    if 'expected_value' not in c:
                        c['expected_value'] = (c.get('prob', 0) * c.get('odds', 0)) - 1
                
                candidates.sort(key=lambda x: x.get('expected_value', 0), reverse=True)
                selected_candidates = candidates[:MAX_DAILY_PICKS]
                
            elif len(candidates) > MAX_DAILY_PICKS:
                logger.info(f"📈 {len(candidates)} picks disponibles, seleccionando top {MAX_DAILY_PICKS} por EV")
                # Calcular EV real para cada candidato
                for c in candidates:
                    odds = c.get('odds', 0)
                    prob = c.get('prob', 0)
                    c['expected_value'] = (prob * odds) - 1  # EV real
                    c['ev_percent'] = c['expected_value'] * 100
                
                # Ordenar por EV descendente y tomar top MAX_DAILY_PICKS
                candidates.sort(key=lambda x: x.get('expected_value', 0), reverse=True)
                selected_candidates = candidates[:MAX_DAILY_PICKS]
                
                # Log de picks descartados
                discarded = candidates[MAX_DAILY_PICKS:]
                logger.info(f"❌ Descartados {len(discarded)} picks por límite máximo:")
                for i, pick in enumerate(discarded[:5], 1):
                    logger.info(f"   [{i}] {pick.get('selection')} @ {pick.get('odds'):.2f} - EV: {pick.get('ev_percent', 0):.2f}%")
            else:
                logger.info(f"✅ {len(candidates)} picks en rango óptimo ({MIN_DAILY_PICKS}-{MAX_DAILY_PICKS})")
                selected_candidates = candidates
            
            logger.info(f"📤 Returning {len(selected_candidates)} picks for alerts")
            return selected_candidates
            
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
            
            if odds < MIN_ODD or odds > MAX_ODD:
                logger.warning(f"⚠️ REJECTED: Odds {odds} fuera de rango ({MIN_ODD}-{MAX_ODD})")
                return False
            
            if prob < MIN_PROB:
                logger.warning(f"⚠️ REJECTED: Prob {prob:.1%} menor que mínimo {MIN_PROB:.1%}")
                return False
            
            if value < MIN_VALUE_THRESHOLD:
                logger.warning(f"⚠️ REJECTED: Value {value:.3f} menor que mínimo {MIN_VALUE_THRESHOLD}")
                return False
            
            if confidence < MIN_CONFIDENCE_SCORE:
                logger.warning(f"⚠️ REJECTED: Confidence {confidence} menor que mínimo {MIN_CONFIDENCE_SCORE}")
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
            tracker.add_alert(
                user_id=user.chat_id,
                event_id=candidate.get('id', ''),
                sport=candidate.get('sport_key', ''),
                pick_type=candidate.get('market', 'h2h'),
                selection=candidate.get('selection', ''),
                odds=odds,
                stake=stake,
                point=candidate.get('point'),
                game_time=candidate.get('commence_time')
            )
            logger.info(f"✅ Alert tracked for verification: {candidate.get('selection')}")
            
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
        
        # Obtener usuarios premium y gratuitos
        users = list(self.users_manager.users.values())
        
        # Forzar check de reset diario para todos los usuarios
        for user in users:
            user._check_reset()
        
        premium_users = [user for user in users if user.is_premium_active()]
        free_users = [user for user in users if not user.is_premium_active()]
        
        logger.info(f"📊 {len(premium_users)} premium users, {len(free_users)} free users available")
        
        total_alerts_sent = 0
        
        # 1. USUARIOS PREMIUM: reciben exactamente 5 picks (los mejores ordenados por value)
        premium_picks = value_candidates[:5]  # Siempre 5 picks para premium
        logger.info(f"📤 Enviando exactamente {len(premium_picks)} picks a usuarios premium")
        
        for candidate in premium_picks:
            # Verificar si ya enviamos esta alerta
            candidate_key = f"{candidate.get('id', '')}_{candidate.get('selection', '')}"
            
            alerts_sent_for_candidate = 0
            
            for user in premium_users:
                # Verificar límites (premium puede recibir hasta 5 al día)
                if user.alerts_sent_today >= 5:
                    continue
                
                # Verificar duplicados
                alert_key = f"{user.chat_id}_{candidate_key}"
                if alert_key in self.sent_alerts:
                    continue
                
                # Enviar alerta
                success = await self.send_alert_to_user(user, candidate)
                logger.info(f"DEBUG: send_alert_to_user returned: {success}")
                if success:
                    alerts_sent_for_candidate += 1
                    total_alerts_sent += 1
                    logger.info(f"DEBUG: Incremented counters - candidate: {alerts_sent_for_candidate}, total: {total_alerts_sent}")
                
                # Limitar alertas por candidato (evitar spam)
                if alerts_sent_for_candidate >= len(premium_users):
                    break
        
        # 2. USUARIOS GRATIS: reciben SOLO 1 pick (el de MAYOR value de los 5)
        if free_users and value_candidates:
            best_pick = value_candidates[0]  # El #1 con mayor EV
            logger.info(f"🎁 Enviando 1 pick GRATIS (máximo value) a {len(free_users)} usuarios gratis")
            
            best_pick_key = f"{best_pick.get('id', '')}_{best_pick.get('selection', '')}"
            
            for user in free_users:
                # Usuarios gratis: MÁXIMO 1 al día
                if user.alerts_sent_today >= 1:
                    continue
                
                # Verificar duplicados
                alert_key = f"{user.chat_id}_{best_pick_key}"
                if alert_key in self.sent_alerts:
                    continue
                
                # Enviar alerta
                success = await self.send_alert_to_user(user, best_pick)
                if success:
                    total_alerts_sent += 1
                    logger.info(f"✅ Pick gratis enviado a usuario {user.chat_id}")
        
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
        - Resetear saldos de comisiones
        """
        logger.info("🔄 WEEKLY RESET - Lunes 06:00 AM")
        
        users = list(self.users_manager.users.values())
        premium_users = [u for u in users if u.is_premium_active()]
        
        removed_count = 0
        reset_count = 0
        
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
                
                # Calcular profit/loss
                stake = alert['stake']
                odds = alert['odds']
                
                if result == 'won':
                    profit_loss = stake * (odds - 1)
                    won_count += 1
                elif result == 'lost':
                    profit_loss = -stake
                    lost_count += 1
                else:
                    profit_loss = 0
                    push_count += 1
                
                # Actualizar tracker
                tracker.update_alert_result(alert_id, result, profit_loss)
                
                # Actualizar bankroll del usuario
                user = self.users_manager.get_user(alert['user_id'])
                if user and hasattr(user, 'dynamic_bank'):
                    user.dynamic_bank += profit_loss
                    logger.info(f"   💰 User {alert['user_id']}: {result.upper()} → {profit_loss:+.2f}€")
                
                # Notificar resultado
                try:
                    if result == 'won':
                        msg = f"✅ **PICK GANADOR**\n\n🎯 {alert['selection']}\n💰 Ganancia: +{profit_loss:.2f}€"
                    elif result == 'lost':
                        msg = f"❌ **PICK PERDIDO**\n\n🎯 {alert['selection']}\n💸 Pérdida: {profit_loss:.2f}€"
                    else:
                        msg = f"🔄 **EMPATE (Push)**\n\n🎯 {alert['selection']}\n💰 Stake devuelto"
                    
                    if user and hasattr(user, 'dynamic_bank'):
                        msg += f"\n📊 Bankroll: {user.dynamic_bank:.2f}€"
                    
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
