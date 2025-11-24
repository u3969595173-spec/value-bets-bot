"""
Comandos de verificación manual de resultados y estadísticas mejoradas
"""

import logging
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from data.users import get_users_manager
from data.alerts_tracker import get_alerts_tracker

logger = logging.getLogger(__name__)


async def handle_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler para botones de verificación manual ✅❌🔄
    
    Callback data format: verify_{result}_{user_id}_{event_id}
    """
    query = update.callback_query
    await query.answer()
    
    # Parse callback data
    parts = query.data.split('_')
    if len(parts) < 4:
        await query.edit_message_text("❌ Error: Formato de callback inválido")
        return
    
    result = parts[1]  # 'won', 'lost', 'push'
    user_id = parts[2]
    event_id = '_'.join(parts[3:])  # El event_id puede tener guiones bajos
    
    logger.info(f"📊 Verificación manual: {result} para user {user_id}, event {event_id}")
    
    # Obtener managers
    users_manager = get_users_manager()
    tracker = get_alerts_tracker()
    
    # Buscar la alerta pendiente
    pending_alerts = tracker.get_pending_alerts(hours_old=168)  # Última semana
    target_alert = None
    
    for alert in pending_alerts:
        if str(alert['user_id']) == str(user_id) and alert['event_id'] == event_id:
            target_alert = alert
            break
    
    if not target_alert:
        await query.edit_message_text(
            f"❌ No se encontró alerta pendiente para este usuario/evento\\n"
            f"User: {user_id}, Event: {event_id}"
        )
        return
    
    # Obtener usuario
    user = users_manager.get_user(user_id)
    if not user:
        await query.edit_message_text(f"❌ Usuario {user_id} no encontrado")
        return
    
    # Calcular profit/loss
    stake = target_alert['stake']
    odds = target_alert['odds']
    
    if result == 'won':
        profit_loss = stake * (odds - 1)
        emoji = "✅"
        status_text = "GANÓ"
    elif result == 'lost':
        profit_loss = -stake
        emoji = "❌"
        status_text = "PERDIÓ"
    else:  # push
        profit_loss = 0
        emoji = "🔄"
        status_text = "EMPATE (Push)"
    
    # Actualizar bankroll dinámico
    old_bank = user.dynamic_bank
    user.dynamic_bank += profit_loss
    new_bank = user.dynamic_bank
    
    logger.info(f"💰 Bank actualizado: {old_bank:.2f}€ → {new_bank:.2f}€ ({profit_loss:+.2f}€)")
    
    # Actualizar historial de apuestas
    for bet in user.bet_history:
        if bet.get('event_id') == event_id and bet.get('status') == 'pending':
            bet['status'] = result
            bet['result_verified_at'] = datetime.now(timezone.utc).isoformat()
            bet['profit'] = profit_loss
            logger.info(f"📝 Apuesta actualizada en historial: {result}")
            break
    
    # Actualizar tracker
    alert_id = target_alert.get('alert_id', f"{user_id}_{event_id}_manual")
    tracker.update_alert_result(alert_id, result, profit_loss)
    
    # Guardar cambios
    users_manager.save()
    
    # Notificar usuario
    try:
        user_msg = f"{emoji} **RESULTADO: {status_text}**\\n\\n"
        user_msg += f"🎯 Pick: {target_alert['selection']}\\n"
        if target_alert.get('point'):
            user_msg += f"📊 Línea: {target_alert['point']}\\n"
        user_msg += f"💰 Cuota: {odds:.2f}\\n"
        user_msg += f"💵 Stake: {stake:.2f}€\\n\\n"
        
        if result == 'won':
            user_msg += f"✅ **Ganancia: +{profit_loss:.2f}€**\\n"
        elif result == 'lost':
            user_msg += f"❌ **Pérdida: {profit_loss:.2f}€**\\n"
        else:
            user_msg += f"🔄 **Devolución: {stake:.2f}€**\\n"
        
        user_msg += f"\\n🏦 **Bank actualizado:**\\n"
        user_msg += f"Anterior: {old_bank:.2f}€\\n"
        user_msg += f"Nuevo: {new_bank:.2f}€"
        
        from notifier.telegram import TelegramNotifier
        import os
        notifier = TelegramNotifier(os.getenv('BOT_TOKEN'))
        await notifier.send_message(user_id, user_msg)
        logger.info(f"📤 Notificación enviada al usuario {user_id}")
    except Exception as e:
        logger.error(f"Error notificando usuario: {e}")
    
    # Actualizar mensaje del admin
    updated_msg = query.message.text + f"\\n\\n{emoji} **{status_text}** - Verificado por admin\\n"
    updated_msg += f"💰 Profit/Loss: {profit_loss:+.2f}€\\n"
    updated_msg += f"🏦 Bank: {old_bank:.2f}€ → {new_bank:.2f}€"
    
    try:
        await query.edit_message_text(updated_msg)
    except:
        await query.message.reply_text(updated_msg)
    
    logger.info(f"✅ Verificación manual completada: {result}")


async def cmd_pendientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /pendientes - Muestra todas las alertas sin verificar con botones
    """
    chat_id = update.effective_user.id
    
    # Verificar que es admin
    import os
    admin_id = os.getenv('CHAT_ID')
    if str(chat_id) != str(admin_id):
        await update.message.reply_text("❌ Solo el administrador puede usar este comando")
        return
    
    tracker = get_alerts_tracker()
    pending = tracker.get_pending_alerts(hours_old=168)  # Última semana
    
    if not pending:
        await update.message.reply_text("✅ No hay alertas pendientes de verificar")
        return
    
    users_manager = get_users_manager()
    
    msg = f"📋 **ALERTAS PENDIENTES DE VERIFICAR** ({len(pending)})\\n\\n"
    
    for i, alert in enumerate(pending[:20], 1):  # Máximo 20 para no saturar
        user = users_manager.get_user(alert['user_id'])
        username = user.username if user else "Usuario desconocido"
        
        msg += f"{i}. **{username}** (ID: {alert['user_id']})\\n"
        msg += f"   🎯 {alert['selection']}"
        if alert.get('point'):
            msg += f" {alert['point']}"
        msg += f" @ {alert['odds']:.2f}\\n"
        msg += f"   💵 Stake: {alert['stake']:.2f}€\\n"
        msg += f"   📅 {alert['sent_at'][:16]}\\n\\n"
        
        # Agregar botones para verificar
        keyboard = [[
            InlineKeyboardButton("✅ Ganó", callback_data=f"verify_won_{alert['user_id']}_{alert['event_id']}"),
            InlineKeyboardButton("❌ Perdió", callback_data=f"verify_lost_{alert['user_id']}_{alert['event_id']}"),
            InlineKeyboardButton("🔄 Push", callback_data=f"verify_push_{alert['user_id']}_{alert['event_id']}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await update.message.reply_text(msg, reply_markup=reply_markup)
            msg = ""  # Reset para la siguiente
        except:
            continue
    
    if msg:  # Si queda mensaje sin enviar
        await update.message.reply_text(msg)


async def cmd_stats_pro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /stats_pro - Panel de estadísticas mejorado con bank dinámico y ROI
    """
    logger.info(f"📊 /stats_pro ejecutado por {update.effective_user.id}")
    chat_id = update.effective_user.id
    users_manager = get_users_manager()
    user = users_manager.get_user(str(chat_id))
    
    if not user:
        logger.warning(f"❌ Usuario {chat_id} no encontrado en /stats_pro")
        await update.message.reply_text("❌ Usuario no encontrado. Usa /start primero")
        return
    
    logger.info(f"✅ Generando estadísticas para {user.username}...")
    # Calcular estadísticas del historial
    total_bets = len(user.bet_history)
    won = sum(1 for bet in user.bet_history if bet.get('status') == 'won')
    lost = sum(1 for bet in user.bet_history if bet.get('status') == 'lost')
    push = sum(1 for bet in user.bet_history if bet.get('status') == 'push')
    pending = sum(1 for bet in user.bet_history if bet.get('status') == 'pending')
    
    # ROI y profit
    total_staked = sum(bet.get('stake', 0) for bet in user.bet_history if bet.get('status') in ['won', 'lost'])
    total_profit = sum(bet.get('profit', 0) for bet in user.bet_history if bet.get('profit') is not None)
    roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
    
    # Estadísticas por período
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Semanal
    weekly_bets = [bet for bet in user.bet_history if datetime.fromisoformat(bet.get('date', '2020-01-01')) > week_ago]
    weekly_profit = sum(bet.get('profit', 0) for bet in weekly_bets if bet.get('profit') is not None)
    weekly_staked = sum(bet.get('stake', 0) for bet in weekly_bets if bet.get('status') in ['won', 'lost'])
    weekly_roi = (weekly_profit / weekly_staked * 100) if weekly_staked > 0 else 0
    
    # Mensual
    monthly_bets = [bet for bet in user.bet_history if datetime.fromisoformat(bet.get('date', '2020-01-01')) > month_ago]
    monthly_profit = sum(bet.get('profit', 0) for bet in monthly_bets if bet.get('profit') is not None)
    monthly_staked = sum(bet.get('stake', 0) for bet in monthly_bets if bet.get('status') in ['won', 'lost'])
    monthly_roi = (monthly_profit / monthly_staked * 100) if monthly_staked > 0 else 0
    
    # Win rate
    win_rate = (won / (won + lost) * 100) if (won + lost) > 0 else 0
    
    # Formatear mensaje
    msg = "📊 **TUS ESTADÍSTICAS PROFESIONALES**\\n\\n"
    
    # Bank dinámico
    msg += "🏦 **BANKROLL DINÁMICO**\\n"
    msg += f"💰 Bank actual: **{user.dynamic_bank:.2f}€**\\n"
    msg += f"📈 Profit total: **{total_profit:+.2f}€**\\n\\n"
    
    # ROI por período
    msg += "📈 **ROI POR PERÍODO**\\n"
    msg += f"📅 Semanal: **{weekly_roi:+.1f}%** ({weekly_profit:+.2f}€)\\n"
    msg += f"📅 Mensual: **{monthly_roi:+.1f}%** ({monthly_profit:+.2f}€)\\n"
    msg += f"📅 Histórico: **{roi:+.1f}%** ({total_profit:+.2f}€)\\n\\n"
    
    # Estadísticas generales
    msg += "🎯 **ESTADÍSTICAS GENERALES**\\n"
    msg += f"📊 Total apuestas: {total_bets}\\n"
    msg += f"✅ Ganadas: {won}\\n"
    msg += f"❌ Perdidas: {lost}\\n"
    msg += f"🔄 Empates: {push}\\n"
    msg += f"⏳ Pendientes: {pending}\\n"
    msg += f"🎯 Win Rate: **{win_rate:.1f}%**\\n\\n"
    
    # Gráfico ASCII simple
    if won + lost > 0:
        won_bar = '█' * int(won / (won + lost) * 20)
        lost_bar = '░' * int(lost / (won + lost) * 20)
        msg += f"📊 {won_bar}{lost_bar}\\n"
        msg += f"   {won}W / {lost}L\\n\\n"
    
    # Botón para ver historial
    keyboard = [[
        InlineKeyboardButton("📜 Ver Historial Completo", callback_data="show_full_history")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, reply_markup=reply_markup)


async def show_full_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback para mostrar historial completo de apuestas
    """
    query = update.callback_query
    await query.answer()
    
    chat_id = query.from_user.id
    users_manager = get_users_manager()
    user = users_manager.get_user(str(chat_id))
    
    if not user or not user.bet_history:
        await query.edit_message_text("❌ No tienes historial de apuestas")
        return
    
    # Ordenar por fecha (más reciente primero)
    sorted_history = sorted(
        user.bet_history,
        key=lambda x: x.get('date', ''),
        reverse=True
    )
    
    msg = "📜 **HISTORIAL COMPLETO DE APUESTAS**\\n\\n"
    
    for i, bet in enumerate(sorted_history[:30], 1):  # Últimas 30
        status = bet.get('status', 'pending')
        if status == 'won':
            emoji = "✅"
        elif status == 'lost':
            emoji = "❌"
        elif status == 'push':
            emoji = "🔄"
        else:
            emoji = "⏳"
        
        msg += f"{i}. {emoji} **{bet.get('selection', 'N/A')}**\\n"
        msg += f"   💰 {bet.get('odds', 0):.2f} | Stake: {bet.get('stake', 0):.2f}€"
        
        if bet.get('profit') is not None:
            msg += f" | P/L: **{bet.get('profit', 0):+.2f}€**"
        
        msg += f"\\n   📅 {bet.get('date', '')[:16]}\\n\\n"
        
        # Telegram tiene límite de 4096 caracteres
        if len(msg) > 3500:
            await query.message.reply_text(msg)
            msg = ""
    
    if msg:
        await query.message.reply_text(msg)
    
    # Botón para volver a estadísticas
    keyboard = [[
        InlineKeyboardButton("◀️ Volver a Estadísticas", callback_data="back_to_stats")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("📊 Fin del historial", reply_markup=reply_markup)


async def back_to_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volver al panel de estadísticas"""
    query = update.callback_query
    await query.answer()
    
    # Llamar a cmd_stats_pro simulando un update normal
    await cmd_stats_pro(update, context)
