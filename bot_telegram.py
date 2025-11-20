"""
bot_telegram.py - Bot de comandos de Telegram con sistema de referidos

Este archivo maneja todos los comandos interactivos del bot usando python-telegram-bot.
Se ejecuta en paralelo con main.py para el monitoreo de value bets.
"""

import os
import asyncio
import logging
import shutil
import pytz
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from telegram.error import TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Cargar variables de entorno
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Importar sistemas
from referrals import ReferralSystem, format_referral_stats
from data.users import UsersManager
from payments import PremiumPaymentProcessor
from analytics.performance_tracker import performance_tracker

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_CHAT_ID = os.getenv('CHAT_ID', '5901833301')
BOT_USERNAME = "Valueapuestasbot"

# --- Protección y backup de archivos JSON críticos ---
def safe_json_backup(path):
    try:
        if not Path(path).exists():
            logger.warning(f"[STARTUP] Archivo {path} no existe. Se creará uno nuevo.")
            Path(path).write_text('{}', encoding='utf-8')
        # Backup automático
        backup_path = Path(path).with_suffix(f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(path, backup_path)
        logger.info(f"[STARTUP] Backup creado: {backup_path}")
    except Exception as e:
        logger.error(f"[STARTUP] Error al respaldar {path}: {e}")

safe_json_backup("data/referrals.json")
safe_json_backup("data/users.json")

# Inicializar sistemas
referral_system = ReferralSystem("data/referrals.json")
users_manager = UsersManager("data/users.json")
payment_processor = PremiumPaymentProcessor(referral_system, users_manager)

# Variable global para la aplicación (se inicializa en main)
application = None

# ========== RESET SEMANAL Y NOTIFICACIONES =============
async def weekly_reset_and_notify(context: ContextTypes.DEFAULT_TYPE):
    """
    Ejecuta cada lunes:
    1. Calcula ganancias de la semana para todos los usuarios premium
    2. Registra deudas (20% si hubo profit)
    3. Reinicia bank a 200€
    4. Notifica a usuarios sobre pagos pendientes
    """
    logger.info("🔄 Ejecutando reset semanal...")
    
    for user in users_manager.users.values():
        if user.nivel != "premium":
            continue
        
        # Calcular stats de la semana
        user.calculate_weekly_stats()
        
        # Notificar al usuario
        try:
            payment_status = user.get_payment_status()
            
            message = "📅 *RESUMEN SEMANAL*\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message += f"Bank inicio: {payment_status['week_start_bank']:.2f} €\n"
            message += f"Bank final: {payment_status['dynamic_bank_current']:.2f} €\n"
            
            if payment_status['weekly_profit'] > 0:
                message += f"\n✅ Ganancia: +{payment_status['weekly_profit']:.2f} €\n"
                message += f"💰 Comisión (20%): {payment_status['weekly_fee_due']:.2f} €\n"
            elif payment_status['weekly_profit'] < 0:
                message += f"\n📉 Pérdida: {payment_status['weekly_profit']:.2f} €\n"
                message += f"💰 Comisión (20%): 0.00 € (no se cobra)\n"
            else:
                message += f"\n➖ Sin cambios esta semana\n"
            
            message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            message += f"💳 *PAGO PRÓXIMA SEMANA:*\n"
            message += f"• Base: 15.00 €\n"
            message += f"• Plus: {payment_status['weekly_fee_due']:.2f} €\n"
            message += f"• *TOTAL: {15.0 + payment_status['weekly_fee_due']:.2f} €*\n\n"
            message += f"Usa /mi_deuda para ver detalles\n"
            message += f"💬 Contacta al admin para pagar"
            
            await context.bot.send_message(
                chat_id=user.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Notificación semanal enviada a {user.chat_id}")
            
        except Exception as e:
            logger.error(f"Error notificando a {user.chat_id}: {e}")
        
        # Resetear ciclo para nueva semana
        user.reset_weekly_cycle()
    
    # Guardar cambios
    users_manager.save()
    logger.info("✅ Reset semanal completado")

# ========== RECOMPENSA SEMANAL AUTOMÁTICA =============
async def send_weekly_referral_rewards(context: ContextTypes.DEFAULT_TYPE):
    """
    Calcula el top 3 de referidores premium de la semana y reparte el 50% de las comisiones variables (20%) generadas.
    """
    logger.info("🏆 Calculando Top 3 semanal...")
    
    # Calcular pool: 50% de todas las comisiones del 20% cobradas esta semana
    total_fees_collected = 0.0
    for user in users_manager.users.values():
        if user.nivel == "premium" and user.weekly_fee_due > 0:
            total_fees_collected += user.weekly_fee_due
    
    pool = total_fees_collected * 0.5  # 50% del total de comisiones
    
    if pool <= 0:
        message = "🏆 *TOP 3 REFERIDORES DE LA SEMANA*\n\n"
        message += "No hubo comisiones para repartir esta semana.\n"
        message += "¡Sigue invitando amigos premium!"
    else:
        # Calcular ranking por cantidad de referidos premium activos
        ranking = []
        for user in users_manager.users.values():
            # Contar referidos premium activos
            premium_refs = 0
            for ref_id in getattr(user, 'referred_users', []):
                ref = users_manager.users.get(ref_id)
                if ref and ref.nivel == "premium":
                    premium_refs += 1
            
            if premium_refs > 0:
                ranking.append({
                    'user_id': user.chat_id,
                    'username': getattr(user, 'username', user.chat_id),
                    'count': premium_refs
                })
        
        ranking.sort(key=lambda x: x['count'], reverse=True)
        
        # Calcular premios: 50%, 30%, 20%
        premios = [0, 0, 0]
        if len(ranking) > 0:
            premios[0] = round(pool * 0.5, 2)
        if len(ranking) > 1:
            premios[1] = round(pool * 0.3, 2)
        if len(ranking) > 2:
            premios[2] = round(pool * 0.2, 2)
        
        message = "🏆 *TOP 3 REFERIDORES DE LA SEMANA*\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n\n"
        message += f"💰 Pool total: {pool:.2f} €\n\n"
        
        for i, r in enumerate(ranking[:3]):
            medal = ["🥇", "🥈", "🥉"][i]
            message += f"{medal} *{i+1}º lugar:* {r['username']}\n"
            message += f"   👥 {r['count']} referidos premium\n"
            message += f"   💰 Premio: {premios[i]:.2f} €\n\n"
        
        message += "¡Sigue trayendo referidos para el próximo ranking!"
        
        # Pagar a los ganadores
        for i, r in enumerate(ranking[:3]):
            if premios[i] > 0:
                user = users_manager.users.get(r['user_id'])
                if user:
                    # Agregar premio a saldo de comisiones
                    user.saldo_comision += premios[i]
                    logger.info(f"Premio Top {i+1} a {r['user_id']}: {premios[i]:.2f} €")
    
    # Enviar mensaje a todos los usuarios premium
    for user in users_manager.users.values():
        if user.nivel == "premium":
            try:
                await context.bot.send_message(
                    chat_id=user.chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.warning(f"No se pudo enviar Top 3 a {user.chat_id}: {e}")
    
    users_manager.save()
    logger.info("✅ Top 3 semanal completado")


def schedule_weekly_referral_rewards():
    """Programa el envío semanal de recompensas de referidos los lunes a las 12:00."""
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Madrid'))
    scheduler.add_job(lambda: asyncio.create_task(send_weekly_referral_rewards()), 'cron', day_of_week='mon', hour=12, minute=0)
    scheduler.start()
async def mi_posicion_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /mi_posicion - Ranking de referidos premium activos en tiempo real
    """
    user_id = str(update.effective_user.id)
    users = list(users_manager.users.values())
    # Contar solo referidos premium activos
    ranking = []
    for user in users:
        # Contar referidos premium activos
        premium_refs = [ref for ref in getattr(user, 'referred_users', [])
                        if ref in users_manager.users and users_manager.users[ref].is_premium_active()]
        ranking.append({
            'user_id': user.chat_id,
            'username': getattr(user, 'username', user.chat_id),
            'count': len(premium_refs)
        })
    # Ordenar de mayor a menor
    ranking.sort(key=lambda x: x['count'], reverse=True)
    # Buscar posición del usuario
    pos = next((i for i, r in enumerate(ranking) if r['user_id'] == user_id), None)
    if pos is None:
        await update.message.reply_text("No tienes referidos registrados.")
        return
    user_count = ranking[pos]['count']
    leader = ranking[0]
    leader_name = leader['username'] if leader['user_id'] != user_id else 'Tú'
    leader_count = leader['count']
    next_goal = leader_count + 1 if pos == 0 else ranking[pos-1]['count'] + 1
    msg = (
        f"🏆 Tu posición en el ranking de referidos: {pos+1}º\n"
        f"🔹 Referidos premium activos: {user_count}\n"
        f"🔹 Referido líder: {leader_name} ({leader_count} referidos)\n"
        f"🔹 Tu próxima meta: {next_goal} referidos para superar al líder"
    )
    await update.message.reply_text(msg)
# ========== ENVÍO AUTOMÁTICO DE RESÚMENES DIARIOS Y SEMANALES =============
async def send_global_summary_to_all_users(summary_type: str = 'daily'):
    """
    Envía el resumen global (diario o semanal) a todos los usuarios registrados.
    summary_type: 'daily' o 'weekly'
    """
    days = 1 if summary_type == 'daily' else 7
    stats = performance_tracker.get_global_stats(days=days)
    if stats['total_predictions'] == 0:
        message = f"📊 RESUMEN {'DIARIO' if days==1 else 'SEMANAL'}\n\nNo hubo pronósticos verificados en este periodo."
    else:
        message = (
            f"📊 *RESUMEN {'DIARIO' if days==1 else 'SEMANAL'} DEL BOT*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Total pronósticos: {stats['total_predictions']}\n"
            f"✅ Aciertos: {stats['won']}\n"
            f"❌ Fallos: {stats['lost']}\n"
            f"⏳ Pendientes: {stats['pending']}\n"
            f"Win Rate: {stats['win_rate']}%\n"
            f"ROI: {stats['roi']}%\n"
            f"Ganancia/Pérdida: {stats['total_profit']}\n"
        )
    # Enviar a todos los usuarios
    all_users = users_manager.users.keys()
    for user_id in all_users:
        try:
            await application.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
        except TelegramError as e:
            logger.warning(f"No se pudo enviar resumen a {user_id}: {e}")

def schedule_summaries():
    """Programa el envío diario y semanal de resúmenes a las 12:00."""
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Madrid'))
    # Diario: todos los días a las 12:00
    scheduler.add_job(lambda: asyncio.create_task(send_global_summary_to_all_users('daily')), 'cron', hour=12, minute=0)
    # Semanal: lunes a las 12:00
    scheduler.add_job(lambda: asyncio.create_task(send_global_summary_to_all_users('weekly')), 'cron', day_of_week='mon', hour=12, minute=0)
    scheduler.start()



# ============================================================================
# COMANDOS PARA USUARIOS
# ============================================================================

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /stats - Muestra estadísticas de performance del bot
    """
    try:
        # Obtener estadísticas globales de Supabase
        stats = performance_tracker.get_global_stats(days=30)
        if stats['total_predictions'] == 0:
            await update.message.reply_text(
                "📊 **ESTADÍSTICAS DEL BOT**\n\n"
                "⏳ Aún no hay predicciones verificadas.\n"
                "El bot está recopilando datos...\n\n"
                "Vuelve en 24-48 horas para ver estadísticas reales."
            )
            return

        # Formatear mensaje
        message = (
            "📊 PERFORMANCE DEL BOT (Últimos 30 días)\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 RENDIMIENTO GLOBAL:\n"
            f"  Total pronósticos: {stats['total_predictions']}\n"
            f"  ✅ Aciertos: {stats['won']}\n"
            f"  ❌ Fallos: {stats['lost']}\n"
            f"  ⏳ Pendientes: {stats['pending']}\n\n"
            f"🎯 EFECTIVIDAD:\n"
            f"  Win Rate: {stats['win_rate']:.1f}%\n"
            f"  ROI: {stats['roi']:+.1f}%\n\n"
            f"💰 FINANCIERO:\n"
            f"  Stake total: ${stats['total_stake']:.2f}\n"
            f"  Ganancia/Pérdida: ${stats['total_profit']:+.2f}\n\n"
            f"📊 ANÁLISIS:\n"
            f"  Cuota promedio: {stats['avg_odd']:.2f}\n"
            f"  Mejor deporte: {stats['best_sport']}\n\n"
        )
        if stats['win_rate'] >= 55:
            message += "✅ Rendimiento EXCELENTE - Por encima del umbral de rentabilidad\n"
        elif stats['win_rate'] >= 50:
            message += "📊 Rendimiento BUENO - En zona de rentabilidad\n"
        else:
            message += "⚠️ Rendimiento en desarrollo - Se optimiza continuamente\n"
        message += "\n💡 Nota: Los resultados se verifican automáticamente tras finalizar cada evento."
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error en comando /stats: {e}")
        await update.message.reply_text(
            f"❌ Error al obtener estadísticas: {e}. Intenta de nuevo o contacta soporte."
        )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /start [CODIGO_REFERIDO]
    Registra al usuario y muestra su código de referido
    """
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or update.effective_user.first_name or "Usuario"
    
    # Extraer código de referido si existe
    referrer_code = None
    if context.args and len(context.args) > 0:
        referrer_code = context.args[0].upper()
        logger.info(f"Usuario {user_id} inicio con codigo de referido: {referrer_code}")
    
    # Registrar en sistema de referidos
    result = referral_system.register_user(user_id, referrer_code)
    
    # Registrar en sistema de usuarios si no existe
    if not users_manager.get_user(user_id):
        users_manager.add_user(user_id)
    
    # Construir mensaje de bienvenida
    welcome_text = f"*Bienvenido al Bot de Value Bets, {username}!*\n\n"
    welcome_text += (
        "🤖 *QUE HACE ESTE BOT:*\n"
        "• Analiza odds de +30 casas de apuestas en tiempo real\n"
        "• Calcula probabilidades reales con IA avanzada\n"
        "• Detecta value bets (disparidades de mercado)\n"
        "• Optimiza stakes con Kelly Criterion\n"
        "• Cubre 33 deportes (NBA, Champions, NFL, etc)\n"
        "• Solo usuarios Premium reciben alertas\n\n"
    )
    
    # Obtener código y enlace
    referral_code = result.get('referral_code')
    referral_link = result.get('referral_link')
    
    if result['success']:
        if result.get('referred_by'):
            welcome_text += (
                "✅ Te has registrado usando un codigo de referido!\n"
                "Tu amigo recibira una recompensa cuando te suscribas a Premium.\n\n"
            )
        
        welcome_text += (
            f"*TU CODIGO DE REFERIDO:* `{referral_code}`\n"
            f"*Tu enlace:*\n"
            f"`{referral_link}`\n\n"
            "💰 *SISTEMA DE REFERIDOS:*\n"
            "• Ganas el *10% de comisión* (1,5 €) por cada amigo que pague Premium (15 €)\n"
            "• Ganas *1 semana gratis* por cada 3 amigos que paguen\n"
            "• Retiros desde 5 €\n"
            "• Sin límite de ganancias\n\n"
        )
    else:
        # Ya estaba registrado, obtener stats
        stats = referral_system.get_user_stats(user_id)
        if stats:
            referral_code = stats['referral_code']
            referral_link = stats['referral_link']
            welcome_text += (
                f"*Tu codigo de referido:* `{referral_code}`\n"
                f"*Tu enlace:*\n"
                f"`{referral_link}`\n\n"
                "💰 *Comparte y gana:* 10% comisión (1,5 €) + 1 semana gratis cada 3 referidos\n\n"
            )
    
    welcome_text += (
        "*COMANDOS DISPONIBLES:*\n"
        "/referidos - Ver tus estadisticas\n"
        "/estadisticas - Ver rendimiento del bot\n"
        "/canjear - Canjear semana gratis\n"
        "/retirar [monto] - Solicitar retiro\n"
        "/premium - Info de suscripcion Premium\n"
    )

    # Botones
    keyboard = [
        [
            InlineKeyboardButton("📊 Mis Referidos", callback_data="ver_referidos"),
            InlineKeyboardButton("⭐ Premium", callback_data="info_premium")
        ],
        [
            InlineKeyboardButton("📈 Estadísticas Bot", callback_data="ver_estadisticas"),
            InlineKeyboardButton("🔗 Compartir enlace", url=referral_link)
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Si fue referido, notificar al referrer
    if result.get('referred_by'):
        await notify_new_referral(context, result['referred_by'], username)


async def cmd_referidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /referidos
    Muestra estadísticas completas de referidos
    """
    user_id = str(update.effective_user.id)
    
    stats = referral_system.get_user_stats(user_id)
    
    if not stats:
        await update.message.reply_text(
            "❌ No estás registrado en el sistema de referidos.\n"
            "Usa /start para registrarte. Si el problema persiste, contacta soporte."
        )
        return
    
    # Formatear estadísticas con Markdown
    stats_text = (
        "*TUS ESTADISTICAS DE REFERIDOS*\n"
        "="*40 + "\n\n"
        f"*Tu codigo:* `{stats['referral_code']}`\n"
        f"*Tu enlace:*\n`{stats['referral_link']}`\n\n"
        "*REFERIDOS:*\n"
        f"  Total invitados: {stats['total_referrals']}\n"
        f"  Pagaron Premium: {stats['paid_referrals']}\n"
        f"  Pendientes: {stats['pending_referrals']}\n\n"
        "*GANANCIAS:*\n"
        f"  Saldo actual: {stats['balance_usd']:.2f} €\n"
        f"  Total ganado: {stats['total_earned']:.2f} €\n\n"
        "*SEMANAS GRATIS:*\n"
        f"  Ganadas: {stats['free_weeks_earned']}\n"
        f"  Disponibles: {stats['free_weeks_pending']}\n"
        f"  Próxima en: {stats['next_free_week_in']} referidos más\n\n"
        "*RECOMPENSAS:*\n"
        f"  Por cada referido: 1,5 €\n"
        f"  Cada 3 pagos: 1 semana Premium gratis\n"
    )
    
    # Botones
    keyboard = [
        [InlineKeyboardButton("🔗 Compartir enlace", url=stats['referral_link'])],
        [
            InlineKeyboardButton("🎁 Canjear semana", callback_data="canjear_semana"),
            InlineKeyboardButton("💵 Solicitar retiro", callback_data="solicitar_retiro")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def cmd_canjear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /canjear
    Canjea una semana Premium gratis
    """
    user_id = str(update.effective_user.id)
    
    # Intentar canjear
    success, message = referral_system.redeem_free_week(user_id)
    
    if success:
        user = users_manager.get_user(user_id)
        if user:
            user.add_free_premium_week()
            users_manager.update_user(user)
            message += "\n\n✅ Tu suscripción Premium ha sido extendida por 7 días!"
            logger.info(f"Usuario {user_id} canjeó semana Premium gratis")
        else:
            message += "\n\n⚠️ Error activando Premium. Contacta al administrador o soporte."
    else:
        message += "\n\n❌ No tienes semanas gratis disponibles o hubo un error. Si crees que es un error, contacta soporte."
    await update.message.reply_text(message)


async def cmd_retirar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /retirar [monto]
    Solicita retiro de saldo
    """
    user_id = str(update.effective_user.id)
    
    # Validar argumentos
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "❌ Debes indicar el monto a retirar.\n"
            "*Uso:* `/retirar [monto]`\n\n"
            "*Ejemplo:* `/retirar 25.50`\n\n"
            "Tu saldo será verificado y el retiro procesado por el administrador.\n"
            "*Monto mínimo:* $5.00 USD",
            parse_mode='Markdown'
        )
        return
    
    # Parsear monto
    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Monto invalido. Usa numeros con punto decimal.\n"
            "Ejemplo: `/retirar 25.50`",
            parse_mode='Markdown'
        )
        return
    
    # Verificar monto mínimo
    if amount < 5.0:
        await update.message.reply_text(
            "❌ El monto minimo de retiro es *$5.00 USD*",
            parse_mode='Markdown'
        )
        return
    
    # Solicitar retiro
    success, message = referral_system.withdraw_balance(user_id, amount)
    
    if success:
        # Notificar al admin
        await notify_admin_withdrawal(context, user_id, amount)
        
        message += (
            "\n\n⏳ El administrador procesara tu solicitud en las proximas 24-48 horas.\n"
            "*Metodos de pago:* PayPal, Transferencia, Criptomonedas."
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def cmd_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /premium
    Muestra información de la suscripción Premium
    """
    premium_text = (
        "*SUSCRIPCIÓN PREMIUM* ⭐\n\n"
        "*Precio:* 15 € por semana\n\n"
        "*¿QUÉ HACE EL BOT?*\n\n"
        "🔍 *Analisis de Mercado:*\n"
        "• Escanea odds de multiples casas de apuestas\n"
        "• Detecta disparidades y oportunidades de valor\n"
        "• Compara precios en tiempo real (arbitraje)\n\n"
        "🧠 *Sistema de Prediccion:*\n"
        "• Calcula probabilidades reales con IA\n"
        "• Analiza alineaciones y lesiones en vivo\n"
        "• Considera descanso, racha y H2H\n"
        "• Ajusta por clima y condiciones del juego\n\n"
        "💰 *Gestion de Bankroll:*\n"
        "• Calcula stakes optimos con Kelly Criterion\n"
        "• Analiza EV (Expected Value) y edge\n"
        "• Categoriza riesgo (BAJO/MEDIO/ALTO)\n"
        "• Limita apuestas al 0.5%-5% del bankroll\n\n"
        "📊 *Tracking y Validacion:*\n"
        "• Registra todas las predicciones\n"
        "• Calcula accuracy y ROI real\n"
        "• Compara EV esperado vs resultados\n"
        "• Genera reportes de rendimiento\n\n"
        "⚡ *Sistema de Alertas:*\n"
        "• Monitoreo continuo 24/7\n"
        "• Actualizaciones cada hora\n"
        "• Alertas 4h antes del evento\n"
        "• De 3 a 5 mejores picks del dia (calidad ultra-selectiva)\n\n"
        "*Incluye:*\n"
        "✅ 3-5 alertas diarias de maxima calidad\n"
        "✅ Analisis completo de cada pronostico\n"
        "✅ Stake recomendado y nivel de riesgo\n"
        "✅ Seguimiento de resultados\n"
        "✅ Soporte prioritario\n\n"
        "*Como suscribirte:*\n"
        "Contacta al administrador\n\n"
        "*Gana Premium gratis:*\n"
        "Invita 3 amigos que paguen = 1 semana gratis!\n"
        "Usa /referidos para ver tu enlace."
    )
    
    keyboard = [[InlineKeyboardButton("📊 Ver mis referidos", callback_data="ver_referidos")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_text(
            premium_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error mostrando info premium: {e}")
        await update.message.reply_text(
            "❌ Error mostrando la información de Premium. Intenta de nuevo o contacta soporte."
        )


async def cmd_estadisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /estadisticas
    Muestra estadísticas globales del bot
    """
    try:
        # Obtener estadísticas globales
        stats = performance_tracker.get_global_stats(days=30)
        
        # Formatear mensaje
        stats_text = (
            "📊 *ESTADÍSTICAS DEL BOT* (Últimos 30 días)\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 *RENDIMIENTO GLOBAL:*\n"
            f"  Total pronósticos: {stats['total_predictions']}\n"
            f"  ✅ Aciertos: {stats['won']}\n"
            f"  ❌ Fallos: {stats['lost']}\n"
            f"  ⏳ Pendientes: {stats['pending']}\n\n"
            f"🎯 *EFECTIVIDAD:*\n"
            f"  Win Rate: {stats['win_rate']}%\n"
            f"  ROI: {stats['roi']:+.1f}%\n\n"
            f"💰 *FINANCIERO:*\n"
            f"  Stake total: ${stats['total_stake']:.2f}\n"
            f"  Ganancia/Pérdida: ${stats['total_profit']:+.2f}\n\n"
            f"📊 *ANÁLISIS:*\n"
            f"  Cuota promedio: {stats['avg_odd']:.2f}\n"
            f"  Mejor deporte: {stats['best_sport']}\n\n"
        )
        
        # Agregar interpretación
        if stats['win_rate'] >= 55:
            stats_text += "✅ *Rendimiento EXCELENTE* - Por encima del umbral de rentabilidad\n"
        elif stats['win_rate'] >= 50:
            stats_text += "📊 *Rendimiento BUENO* - En zona de rentabilidad\n"
        else:
            stats_text += "⚠️ *Rendimiento en desarrollo* - Se optimiza continuamente\n"
        
        stats_text += "\n💡 *Nota:* Los resultados se verifican automáticamente tras finalizar cada evento."
        
        # Botón para actualizar
        keyboard = [[InlineKeyboardButton("🔄 Actualizar", callback_data="ver_estadisticas")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error en cmd_estadisticas: {e}")
        await update.message.reply_text(
            "❌ Error al cargar estadísticas. Intenta de nuevo más tarde."
        )


# ============================================================================
# COMANDOS DE ADMINISTRADOR
# ============================================================================

def is_admin(user_id: str) -> bool:
    """Verifica si el usuario es administrador"""
    return user_id == ADMIN_CHAT_ID


async def cmd_aprobar_retiro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /aprobar_retiro USER_ID MONTO
    Aprueba un retiro de saldo (solo admin)
    """
    admin_id = str(update.effective_user.id)
    
    if not is_admin(admin_id):
        await update.message.reply_text("❌ Acceso denegado. Solo administradores.")
        return
    
    # Validar argumentos
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "*Uso:* `/aprobar_retiro [user_id] [monto]`\n\n"
            "*Ejemplo:* `/aprobar_retiro 123456789 25.50`",
            parse_mode='Markdown'
        )
        return
    
    user_id = context.args[0]
    
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Monto invalido")
        return
    
    # Aprobar retiro
    success, message = referral_system.approve_withdrawal(user_id, amount, admin_id)
    
    await update.message.reply_text(
        f"*{'✅ RETIRO APROBADO' if success else '❌ ERROR'}*\n\n{message}",
        parse_mode='Markdown'
    )
    
    # Notificar al usuario
    if success:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Tu retiro de *${amount:.2f}* ha sido aprobado y procesado!",
                parse_mode='Markdown'
            )
            logger.info(f"Retiro aprobado: {user_id} - ${amount:.2f}")
        except Exception as e:
            logger.error(f"Error notificando al usuario {user_id}: {e}")


async def cmd_reporte_referidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /reporte_referidos
    Genera reporte completo del sistema (solo admin)
    """
    admin_id = str(update.effective_user.id)
    
    if not is_admin(admin_id):
        await update.message.reply_text("❌ Acceso denegado. Solo administradores.")
        return
    
    # Generar reporte
    report = referral_system.generate_report()
    
    await update.message.reply_text(
        f"```\n{report}\n```",
        parse_mode='Markdown'
    )


async def cmd_detectar_fraude(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /detectar_fraude USER_ID
    Analiza un usuario para detectar fraude (solo admin)
    """
    admin_id = str(update.effective_user.id)
    
    if not is_admin(admin_id):
        await update.message.reply_text("❌ Acceso denegado. Solo administradores.")
        return
    
    # Validar argumentos
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "*Uso:* `/detectar_fraude [user_id]`\n\n"
            "*Ejemplo:* `/detectar_fraude 123456789`",
            parse_mode='Markdown'
        )
        return
    
    user_id = context.args[0]
    
    # Analizar fraude
    analysis = referral_system.detect_fraud(user_id)
    
    message = (
        "*ANALISIS DE FRAUDE* 🔍\n\n"
        f"*Usuario:* `{user_id}`\n"
        f"*Nivel de riesgo:* {analysis['risk_level']}\n"
        f"*Score:* {analysis['risk_score']}/10\n\n"
        f"*Total referidos:* {analysis['total_referrals']}\n"
        f"*Referidos pagos:* {analysis['paid_referrals']}\n"
        f"*Total ganado:* ${analysis['total_earned']:.2f}\n\n"
    )
    
    if analysis['risk_factors']:
        message += "*FACTORES DE RIESGO:*\n"
        for factor in analysis['risk_factors']:
            message += f"⚠️ {factor}\n"
    else:
        message += "✅ No se detectaron factores de riesgo."
    
    await update.message.reply_text(message, parse_mode='Markdown')


# ============================================================================
# CALLBACK QUERIES (BOTONES)
# ============================================================================

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja los callback queries de los botones inline
    """
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    data = query.data
    
    if data == "ver_referidos":
        # Mostrar estadísticas
        stats = referral_system.get_user_stats(user_id)
        if stats:
            stats_text = (
                "*TUS ESTADISTICAS DE REFERIDOS*\n\n"
                f"*Codigo:* `{stats['referral_code']}`\n"
                f"*Total referidos:* {stats['total_referrals']}\n"
                f"*Referidos pagos:* {stats['paid_referrals']}\n"
                f"*Saldo:* ${stats['balance_usd']:.2f}\n"
                f"*Semanas gratis:* {stats['free_weeks_pending']}\n\n"
                "Usa /referidos para ver detalles completos"
            )
            await query.edit_message_text(stats_text, parse_mode='Markdown')
    
    elif data == "canjear_semana":
        # Canjear semana gratis
        success, message = referral_system.redeem_free_week(user_id)
        
        if success:
            user = users_manager.get_user(user_id)
            if user:
                user.add_free_premium_week()
                users_manager.update_user(user)
                message += "\n\n✅ Premium extendido por 7 dias!"
        
        await query.edit_message_text(message)
    
    elif data == "solicitar_retiro":
        # Mostrar instrucciones
        await query.edit_message_text(
            "*Para solicitar un retiro:*\n\n"
            "`/retirar [monto]`\n\n"
            "*Ejemplo:* `/retirar 25.50`\n\n"
            "*Monto minimo:* $5.00 USD\n"
            "*Tiempo de proceso:* 24-48 horas",
            parse_mode='Markdown'
        )
    
    elif data == "info_premium":
        # Mostrar info de Premium
        await query.edit_message_text(
            "*SUSCRIPCIÓN PREMIUM* ⭐\n\n"
            "*Precio:* 15 € por semana\n\n"
            "*Incluye:*\n"
            "✅ 5 alertas diarias de calidad\n"
            "✅ Análisis con Kelly Criterion\n"
            "✅ Pronósticos con IA\n"
            "✅ Tracking de ROI\n\n"
            "Contacta al administrador para suscribirte.\n\n"
            "O invita 3 amigos y gana 1 semana gratis!",
            parse_mode='Markdown'
        )

    elif data == "ver_estadisticas":
        # Mostrar estadísticas globales
        try:
            stats = performance_tracker.get_global_stats(days=30)
            
            stats_text = (
                "📊 ESTADÍSTICAS DEL BOT (Últimos 30 días)\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📈 RENDIMIENTO GLOBAL:\n"
                f"  Total pronósticos: {stats['total_predictions']}\n"
                f"  ✅ Aciertos: {stats['won']}\n"
                f"  ❌ Fallos: {stats['lost']}\n"
                f"  ⏳ Pendientes: {stats['pending']}\n\n"
                f"🎯 EFECTIVIDAD:\n"
                f"  Win Rate: {stats['win_rate']:.1f}%\n"
                f"  ROI: {stats['roi']:+.1f}%\n\n"
                f"💰 FINANCIERO:\n"
                f"  Stake total: ${stats['total_stake']:.2f}\n"
                f"  Ganancia/Pérdida: ${stats['total_profit']:+.2f}\n\n"
                f"📊 ANÁLISIS:\n"
                f"  Cuota promedio: {stats['avg_odd']:.2f}\n"
                f"  Mejor deporte: {stats['best_sport']}\n\n"
            )
            
            if stats['win_rate'] >= 55:
                stats_text += "✅ Rendimiento EXCELENTE\n"
            elif stats['win_rate'] >= 50:
                stats_text += "📊 Rendimiento BUENO\n"
            else:
                stats_text += "⚠️ Optimizando modelo\n"
            
            stats_text += "\n💡 Resultados verificados automáticamente"
            
            await query.edit_message_text(stats_text)
            
        except Exception as e:
            logger.error(f"Error mostrando estadísticas: {e}")
            await query.edit_message_text(
                "❌ Error al cargar estadísticas. Intenta de nuevo."
            )


# ============================================================================
# FUNCIONES DE NOTIFICACION
# ============================================================================

async def notify_new_referral(context: ContextTypes.DEFAULT_TYPE, referrer_id: str, new_user_name: str):
    """Notifica al referrer que un nuevo usuario usó su código"""
    try:
        stats = referral_system.get_user_stats(referrer_id)
        if stats:
            message = (
                "🎉 *NUEVO REFERIDO!*\n\n"
                f"{new_user_name} se registro usando tu codigo.\n"
                "Cuando se suscriba a Premium, ganaras $5 USD!\n\n"
                f"*Total referidos:* {stats['total_referrals']}\n"
                f"*Han pagado:* {stats['paid_referrals']}"
            )
            
            await context.bot.send_message(
                chat_id=referrer_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Notificacion de referido enviada a {referrer_id}")
    except Exception as e:
        logger.error(f"Error notificando a referrer {referrer_id}: {e}")


async def notify_admin_withdrawal(context: ContextTypes.DEFAULT_TYPE, user_id: str, amount: float):
    """Notifica al admin sobre una solicitud de retiro"""
    try:
        admin_message = (
            "💵 *SOLICITUD DE RETIRO*\n\n"
            f"*Usuario:* `{user_id}`\n"
            f"*Monto:* ${amount:.2f} USD\n"
            f"*Fecha:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Usa `/aprobar_retiro {user_id} {amount}` para aprobar"
        )
        
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_message,
            parse_mode='Markdown'
        )
        
        logger.info(f"Solicitud de retiro notificada: {user_id} - ${amount:.2f}")
    except Exception as e:
        logger.error(f"Error notificando retiro al admin: {e}")


async def cmd_mi_deuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /mi_deuda - Muestra estado de pagos del usuario"""
    from commands.user_commands import handle_mi_deuda_command
    
    user_id = str(update.effective_user.id)
    
    try:
        response = await handle_mi_deuda_command(user_id)
        await update.message.reply_text(response, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error en /mi_deuda: {e}")
        await update.message.reply_text("❌ Error al obtener estado de pagos.")


async def cmd_marcar_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando admin /marcar_pago <user_id> <tipo>"""
    from commands.admin_commands import admin_marcar_pago
    
    admin_id = str(update.effective_user.id)
    
    # Verificar argumentos
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Uso: /marcar_pago <user_id> <tipo>\n"
            "Tipos: base, plus, ambos"
        )
        return
    
    user_id = context.args[0]
    payment_type = context.args[1]
    
    try:
        response = await admin_marcar_pago(admin_id, user_id, payment_type)
        await update.message.reply_text(response, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error en /marcar_pago: {e}")
        await update.message.reply_text(f"❌ Error al marcar pago: {e}")


async def cmd_activar_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando admin: /activar_premium <@username o user_id> [semanas]
    Activa premium cuando recibes comprobante de pago
    """
    admin_id = str(update.effective_user.id)
    
    # Solo admin puede usar este comando
    if admin_id != CHAT_ID:
        await update.message.reply_text("❌ Solo el administrador puede usar este comando")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "❌ Uso: /activar_premium <@username o user_id> [semanas]\n"
            "Ejemplos:\n"
            "  /activar_premium @juan_perez 1\n"
            "  /activar_premium 123456789 1"
        )
        return
    
    user_identifier = context.args[0]
    semanas = int(context.args[1]) if len(context.args) > 1 else 1
    
    try:
        # Si empieza con @, buscar por username
        if user_identifier.startswith('@'):
            username = user_identifier[1:]  # Quitar el @
            user = users_manager.get_user_by_username(username)
            if not user:
                await update.message.reply_text(f"❌ Usuario @{username} no encontrado")
                return
            user_id = user.user_id
        else:
            # Buscar por user_id directamente
            user_id = user_identifier
            user = users_manager.get_user(user_id)
            if not user:
                await update.message.reply_text(f"❌ Usuario {user_id} no encontrado")
                return
        
        # Activar premium
        user.add_free_premium_week(semanas)
        users_manager.save()
        
        # Notificar al usuario
        await application.bot.send_message(
            chat_id=user_id,
            text=f"🎉 ¡Tu suscripción Premium ha sido activada por {semanas} semana(s)!\n\n"
                 f"✅ Recibirás 3-5 pronósticos diarios de máxima calidad.\n"
                 f"📅 Válido hasta: {user.suscripcion_fin.strftime('%d/%m/%Y') if user.suscripcion_fin else 'N/A'}"
        )
        
        # Confirmar al admin
        await update.message.reply_text(
            f"✅ Premium activado para {user_id}\n"
            f"⏰ Duración: {semanas} semana(s)\n"
            f"📅 Expira: {user.suscripcion_fin.strftime('%d/%m/%Y') if user.suscripcion_fin else 'N/A'}"
        )
        
    except Exception as e:
        logger.error(f"Error activando premium: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_reiniciar_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando admin: /reiniciar_saldo <@username o user_id>
    Reinicia saldo de referidos a 0 después de pagar al usuario
    """
    admin_id = str(update.effective_user.id)
    
    # Solo admin puede usar este comando
    if admin_id != CHAT_ID:
        await update.message.reply_text("❌ Solo el administrador puede usar este comando")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "❌ Uso: /reiniciar_saldo <@username o user_id>\n"
            "Ejemplos:\n"
            "  /reiniciar_saldo @juan_perez\n"
            "  /reiniciar_saldo 123456789"
        )
        return
    
    user_identifier = context.args[0]
    
    try:
        # Si empieza con @, buscar por username
        if user_identifier.startswith('@'):
            username = user_identifier[1:]  # Quitar el @
            user = users_manager.get_user_by_username(username)
            if not user:
                await update.message.reply_text(f"❌ Usuario @{username} no encontrado")
                return
            user_id = user.user_id
        else:
            # Usar user_id directamente
            user_id = user_identifier
        
        stats = referral_system.get_user_stats(user_id)
        if not stats:
            await update.message.reply_text(f"❌ Usuario {user_id} no encontrado en sistema de referidos")
            return
        
        saldo_anterior = stats['balance_usd']
        
        if saldo_anterior <= 0:
            await update.message.reply_text(f"❌ Usuario {user_id} no tiene saldo disponible")
            return
        
        # Registrar pago y reiniciar saldo
        success, msg = referral_system.process_withdrawal(user_id, saldo_anterior, approved=True, admin_id=admin_id)
        
        if success:
            # Notificar al usuario
            await application.bot.send_message(
                chat_id=user_id,
                text=f"💰 Tu pago de ${saldo_anterior:.2f} USD ha sido procesado.\n\n"
                     f"✅ Saldo reiniciado a $0.00\n"
                     f"Gracias por tu confianza!"
            )
            
            # Confirmar al admin
            await update.message.reply_text(
                f"✅ Pago procesado y saldo reiniciado\n\n"
                f"👤 Usuario: {user_id}\n"
                f"💰 Monto: ${saldo_anterior:.2f} USD\n"
                f"📊 Saldo actual: $0.00"
            )
        else:
            await update.message.reply_text(f"❌ Error: {msg}")
        
    except Exception as e:
        logger.error(f"Error reiniciando saldo: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Versión sync del bot (compatibilidad)"""
    asyncio.run(main_async())

async def main_async():
    """Versión async del bot para correr en paralelo con main.py"""
    global application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Agregar handlers de comandos
    application.add_handler(CommandHandler("mi_posicion", mi_posicion_command))
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("referidos", cmd_referidos))
    application.add_handler(CommandHandler("canjear", cmd_canjear))
    application.add_handler(CommandHandler("retirar", cmd_retirar))
    application.add_handler(CommandHandler("premium", cmd_premium))
    application.add_handler(CommandHandler("estadisticas", cmd_estadisticas))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("mi_deuda", cmd_mi_deuda))
    
    # Comandos admin
    application.add_handler(CommandHandler("aprobar_retiro", cmd_aprobar_retiro))
    application.add_handler(CommandHandler("reporte_referidos", cmd_reporte_referidos))
    application.add_handler(CommandHandler("detectar_fraude", cmd_detectar_fraude))
    application.add_handler(CommandHandler("marcar_pago", cmd_marcar_pago))
    application.add_handler(CommandHandler("activar_premium", cmd_activar_premium))
    application.add_handler(CommandHandler("reiniciar_saldo", cmd_reiniciar_saldo))
    
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # Programar tareas semanales usando job_queue de telegram
    job_queue = application.job_queue
    
    # Keep-alive: cada 10 minutos para evitar suspensión en Render free tier
    async def keep_alive(context):
        """Mantiene el bot activo para evitar suspensión en Render"""
        logger.info("⏰ Keep-alive ping")
    
    job_queue.run_repeating(
        keep_alive,
        interval=600,  # 10 minutos = 600 segundos
        first=60,      # Primer ping después de 1 minuto
        name="keep_alive"
    )
    logger.info("✅ Keep-alive activado: ping cada 10 minutos")
    
    # Reset semanal: cada lunes a las 06:00 (hora del servidor)
    from datetime import time as dt_time
    job_queue.run_daily(
        weekly_reset_and_notify,
        time=dt_time(hour=6, minute=0),
        days=(0,),  # 0 = lunes
        name="weekly_reset"
    )
    logger.info("✅ Scheduler: Reset semanal programado para lunes 06:00")
    
    # Top 3 semanal: cada lunes a las 12:00 (después del reset)
    job_queue.run_daily(
        send_weekly_referral_rewards,
        time=dt_time(hour=12, minute=0),
        days=(0,),  # 0 = lunes
        name="weekly_top3"
    )
    logger.info("✅ Scheduler: Top 3 semanal programado para lunes 12:00")
    
    logger.info("Bot de comandos iniciado correctamente!")
    logger.info("Comandos disponibles: /start, /referidos, /canjear, /retirar, /premium, /stats, /mi_deuda")
    logger.info("Comandos admin: /aprobar_retiro, /reporte_referidos, /detectar_fraude, /marcar_pago")
    
    # Inicializar y arrancar bot de forma async
    try:
        await application.initialize()
        await application.start()
        
        # Agregar error handler para conflictos
        async def error_handler(update, context):
            """Maneja errores durante la ejecución del bot"""
            error = context.error
            if "Conflict" in str(error):
                logger.error("❌ CONFLICT: Otra instancia detectada. Deteniendo bot...")
                # Detener el updater y salir
                if application.updater.running:
                    await application.updater.stop()
                import sys
                sys.exit(1)
            else:
                logger.error(f"Error en bot: {error}", exc_info=context.error)
        
        application.add_error_handler(error_handler)
        
        await application.updater.start_polling(drop_pending_updates=True)
        
        logger.info("✅ Bot de comandos corriendo...")
        
        # Mantener el bot corriendo indefinidamente
        try:
            # Esperar indefinidamente mientras el bot está activo
            while True:
                await asyncio.sleep(3600)  # Sleep 1 hora, se despertará con las actualizaciones
        except (KeyboardInterrupt, SystemExit):
            logger.info("Deteniendo bot de comandos...")
        
    except Exception as e:
        if "Conflict" in str(e):
            logger.error("❌ CONFLICT ERROR: Otra instancia está corriendo. Cerrando esta instancia...")
            import sys
            sys.exit(1)
        else:
            raise
    finally:
        # Cleanup
        try:
            if application.updater.running:
                await application.updater.stop()
            if application.running:
                await application.stop()
            await application.shutdown()
        except Exception as e:
            logger.error(f"Error durante cleanup: {e}")

if __name__ == '__main__':
    main()
