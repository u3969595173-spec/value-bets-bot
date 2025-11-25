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
    
    # Obtener usuario primero
    user = users_manager.get_user(user_id)
    if not user:
        await query.edit_message_text(f"❌ Usuario {user_id} no encontrado")
        return
    
    target_alert = None
    
    # SIEMPRE buscar primero en bet_history del usuario
    logger.info(f"🔍 Buscando {event_id} en bet_history (total: {len(user.bet_history)} apuestas)")
    for bet in user.bet_history:
        if bet.get('event_id') == event_id:
            # Encontrada - permitir actualizar aunque ya esté verificada
            target_alert = {
                'user_id': user_id,
                'event_id': event_id,
                'stake': bet.get('stake', 0),
                'odds': bet.get('odds', 1.0),
                'selection': bet.get('selection', 'N/A'),
                'point': bet.get('point'),
                'alert_id': f"{user_id}_{event_id}",
                'current_status': bet.get('status', 'pending')
            }
            logger.info(f"✅ Apuesta encontrada en bet_history: {event_id} (status: {bet.get('status')})")
            break
    
    # Si no está en bet_history, buscar en alerts_tracker
    if not target_alert:
        logger.info(f"🔍 No encontrada en bet_history, buscando en alerts_tracker...")
        pending_alerts = tracker.get_pending_alerts(hours_old=168)
        for alert in pending_alerts:
            if str(alert['user_id']) == str(user_id) and alert['event_id'] == event_id:
                target_alert = alert
                logger.info(f"✅ Apuesta encontrada en alerts_tracker")
                break
    
    if not target_alert:
        logger.error(f"❌ No se encontró {event_id} en ningún lado")
        # Debug: mostrar todos los event_ids
        event_ids = [b.get('event_id') for b in user.bet_history]
        logger.info(f"📋 Event IDs en bet_history: {event_ids[:10]}")
        await query.edit_message_text(
            f"❌ No se encontró alerta pendiente\\n"
            f"Event: {event_id}"
        )
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
    
    # NO actualizar bank aquí - se hará después de revisar estado anterior
    
    # Actualizar historial de apuestas
    bet_updated = False
    old_bank = user.dynamic_bank
    
    for bet in user.bet_history:
        if bet.get('event_id') == event_id:
            # Calcular profit según el resultado anterior si existe
            previous_status = bet.get('status')
            previous_profit = bet.get('profit', 0)
            
            logger.info(f"🔍 Apuesta encontrada en historial: status={previous_status}, profit={previous_profit}")
            
            # Si ya tenía un resultado, revertir el profit anterior
            if previous_status in ['won', 'lost', 'push'] and previous_profit:
                user.dynamic_bank -= previous_profit
                logger.info(f"🔄 Revirtiendo profit anterior: {previous_profit:+.2f}€")
            
            # Aplicar nuevo resultado
            bet['status'] = result
            bet['result_verified_at'] = datetime.now(timezone.utc).isoformat()
            bet['profit'] = profit_loss  # FORZAR guardar profit
            user.dynamic_bank += profit_loss
            
            logger.info(f"📝 Apuesta actualizada: {previous_status} → {result}, profit: {profit_loss:+.2f}€")
            logger.info(f"💰 Bank después de actualizar: {user.dynamic_bank:.2f}€")
            bet_updated = True
            break
    
    if not bet_updated:
        logger.warning(f"⚠️ No se pudo actualizar la apuesta {event_id} en bet_history")
    
    # Recalcular bank final
    new_bank = user.dynamic_bank
    logger.info(f"💰 Bank final antes de guardar: {new_bank:.2f}€")
    
    # Actualizar tracker
    alert_id = target_alert.get('alert_id', f"{user_id}_{event_id}_manual")
    tracker.update_alert_result(alert_id, result, profit_loss)
    
    # Guardar cambios
    users_manager.save()
    logger.info(f"💾 Cambios guardados. User {user_id} bet_history tiene {len(user.bet_history)} apuestas")
    
    # Debug: contar cuántas pendientes quedan
    pending_count = sum(1 for b in user.bet_history if b.get('status') == 'pending')
    verified_count = sum(1 for b in user.bet_history if b.get('status') in ['won', 'lost', 'push'])
    logger.info(f"📊 Después de guardar: {pending_count} pendientes, {verified_count} verificadas")
    
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


async def handle_verification_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler para verificación que actualiza TODOS los usuarios con esa apuesta
    
    Callback data format: verify_{result}_all_{event_id}
    """
    query = update.callback_query
    await query.answer()
    
    # Parse callback data
    parts = query.data.split('_')
    if len(parts) < 4:
        await query.edit_message_text("❌ Error: Formato de callback inválido")
        return
    
    result = parts[1]  # 'won', 'lost', 'push'
    # parts[2] = 'all'
    event_id = '_'.join(parts[3:])  # El event_id puede tener guiones bajos
    
    logger.info(f"📊 Verificación GLOBAL: {result} para event {event_id}")
    
    # Obtener managers
    users_manager = get_users_manager()
    tracker = get_alerts_tracker()
    
    # Buscar TODOS los usuarios que tienen esta apuesta
    users_with_bet = []
    all_users = users_manager.get_all_users()
    
    for user in all_users:
        for bet in user.bet_history:
            if bet.get('event_id') == event_id:
                users_with_bet.append({
                    'user': user,
                    'bet': bet
                })
                break
    
    if not users_with_bet:
        await query.edit_message_text(f"❌ No se encontró ningún usuario con la apuesta {event_id}")
        return
    
    logger.info(f"✅ Encontrados {len(users_with_bet)} usuarios con el event {event_id}")
    
    # Actualizar cada usuario
    updated_count = 0
    total_profit_loss = 0
    
    for item in users_with_bet:
        user = item['user']
        bet = item['bet']
        
        stake = bet.get('stake', 0)
        odds = bet.get('odds', 1.0)
        
        # Calcular profit/loss
        if result == 'won':
            profit_loss = stake * (odds - 1)
            status_text = "GANÓ"
            emoji = "✅"
        elif result == 'lost':
            profit_loss = -stake
            status_text = "PERDIÓ"
            emoji = "❌"
        else:  # push
            profit_loss = 0
            status_text = "EMPATE"
            emoji = "🔄"
        
        # Revertir resultado anterior si existe
        previous_status = bet.get('status')
        previous_profit = bet.get('profit', 0)
        
        if previous_status in ['won', 'lost', 'push'] and previous_profit:
            user.dynamic_bank -= previous_profit
            logger.info(f"🔄 Usuario {user.chat_id}: Revirtiendo profit anterior {previous_profit:+.2f}€")
        
        old_bank = user.dynamic_bank
        
        # Aplicar nuevo resultado
        bet['status'] = result
        bet['result_verified_at'] = datetime.now(timezone.utc).isoformat()
        bet['profit'] = profit_loss
        user.dynamic_bank += profit_loss
        
        new_bank = user.dynamic_bank
        total_profit_loss += profit_loss
        updated_count += 1
        
        logger.info(f"✅ Usuario {user.chat_id}: {previous_status} → {result}, profit: {profit_loss:+.2f}€, bank: {old_bank:.2f}€ → {new_bank:.2f}€")
        
        # Notificar al usuario
        try:
            user_msg = f"{emoji} <b>RESULTADO: {status_text}</b>\\n\\n"
            user_msg += f"🎯 Pick: {bet.get('selection', 'N/A')}\\n"
            if bet.get('point'):
                user_msg += f"📊 Línea: {bet['point']}\\n"
            user_msg += f"💰 Cuota: {odds:.2f}\\n"
            user_msg += f"💵 Stake: {stake:.2f}€\\n\\n"
            
            if result == 'won':
                user_msg += f"✅ <b>Ganancia: +{profit_loss:.2f}€</b>\\n"
            elif result == 'lost':
                user_msg += f"❌ <b>Pérdida: {profit_loss:.2f}€</b>\\n"
            else:
                user_msg += f"🔄 <b>Devolución: {stake:.2f}€</b>\\n"
            
            user_msg += f"\\n🏦 <b>Bank actualizado:</b>\\n"
            user_msg += f"💵 Anterior: {old_bank:.2f}€\\n"
            user_msg += f"💰 Nuevo: {new_bank:.2f}€"
            
            from notifier.telegram import TelegramNotifier
            import os
            notifier = TelegramNotifier(os.getenv('BOT_TOKEN'))
            await notifier.send_message(user.chat_id, user_msg)
            logger.info(f"📤 Notificación enviada al usuario {user.chat_id}")
        except Exception as e:
            logger.error(f"❌ Error notificando usuario {user.chat_id}: {e}")
    
    # Guardar todos los cambios
    users_manager.save()
    logger.info(f"💾 Cambios guardados para {updated_count} usuarios")
    
    # Actualizar mensaje del admin
    if result == 'won':
        emoji = "✅"
        status_text = "GANADO"
    elif result == 'lost':
        emoji = "❌"
        status_text = "PERDIDO"
    else:
        emoji = "🔄"
        status_text = "EMPATE"
    
    updated_msg = query.message.text + f"\\n\\n{emoji} <b>{status_text}</b> - Verificado por admin\\n"
    updated_msg += f"👥 {updated_count} usuarios actualizados\\n"
    updated_msg += f"💰 Profit/Loss total: {total_profit_loss:+.2f}€"
    
    try:
        await query.edit_message_text(updated_msg)
    except:
        await query.message.reply_text(updated_msg)
    
    logger.info(f"✅ Verificación GLOBAL completada: {result} para {updated_count} usuarios")


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
    
    # Helper para parsear fechas con timezone
    def parse_date(date_str):
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    
    # Semanal
    weekly_bets = [bet for bet in user.bet_history if parse_date(bet.get('date', '2020-01-01T00:00:00+00:00')) > week_ago]
    weekly_profit = sum(bet.get('profit', 0) for bet in weekly_bets if bet.get('profit') is not None)
    weekly_staked = sum(bet.get('stake', 0) for bet in weekly_bets if bet.get('status') in ['won', 'lost'])
    weekly_roi = (weekly_profit / weekly_staked * 100) if weekly_staked > 0 else 0
    
    # Mensual
    monthly_bets = [bet for bet in user.bet_history if parse_date(bet.get('date', '2020-01-01T00:00:00+00:00')) > month_ago]
    monthly_profit = sum(bet.get('profit', 0) for bet in monthly_bets if bet.get('profit') is not None)
    monthly_staked = sum(bet.get('stake', 0) for bet in monthly_bets if bet.get('status') in ['won', 'lost'])
    monthly_roi = (monthly_profit / monthly_staked * 100) if monthly_staked > 0 else 0
    
    # Win rate
    win_rate = (won / (won + lost) * 100) if (won + lost) > 0 else 0
    
    # Formatear mensaje
    msg = "📊 *TUS ESTADÍSTICAS PROFESIONALES*\n\n"
    
    # Bank dinámico
    msg += "🏦 *BANKROLL DINÁMICO*\n"
    msg += f"💰 Bank actual: *{user.dynamic_bank:.2f}€*\n"
    msg += f"📈 Profit total: *{total_profit:+.2f}€*\n\n"
    
    # ROI por período
    msg += "📈 *ROI POR PERÍODO*\n"
    msg += f"📅 Semanal: *{weekly_roi:+.1f}%* ({weekly_profit:+.2f}€)\n"
    msg += f"📅 Mensual: *{monthly_roi:+.1f}%* ({monthly_profit:+.2f}€)\n"
    msg += f"📅 Histórico: *{roi:+.1f}%* ({total_profit:+.2f}€)\n\n"
    
    # Estadísticas generales
    msg += "🎯 *ESTADÍSTICAS GENERALES*\n"
    msg += f"📊 Total apuestas: {total_bets}\n"
    msg += f"✅ Ganadas: {won}\n"
    msg += f"❌ Perdidas: {lost}\n"
    msg += f"🔄 Empates: {push}\n"
    msg += f"⏳ Pendientes: {pending}\n"
    msg += f"🎯 Win Rate: *{win_rate:.1f}%*\n\n"
    
    # Gráfico ASCII simple
    if won + lost > 0:
        won_bar = '█' * int(won / (won + lost) * 20)
        lost_bar = '░' * int(lost / (won + lost) * 20)
        msg += f"📊 {won_bar}{lost_bar}\n"
        msg += f"   {won}W / {lost}L\n\n"
    
    # Botones para ver historial
    keyboard = [
        [InlineKeyboardButton("⏳ Ver Pendientes", callback_data="show_pending_history")],
        [InlineKeyboardButton("📜 Ver Historial Completo", callback_data="show_full_history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, reply_markup=reply_markup)


async def show_pending_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback para mostrar solo las apuestas pendientes del historial
    """
    query = update.callback_query
    await query.answer()
    
    chat_id = query.from_user.id
    users_manager = get_users_manager()
    user = users_manager.get_user(str(chat_id))
    
    if not user:
        await query.edit_message_text("❌ Usuario no encontrado")
        return
    
    # Filtrar solo apuestas pendientes
    pending_bets = [bet for bet in user.bet_history if bet.get('status') == 'pending']
    
    if not pending_bets:
        await query.edit_message_text("✅ No tienes apuestas pendientes")
        return
    
    # Ordenar por fecha (más reciente primero)
    sorted_pending = sorted(
        pending_bets,
        key=lambda x: x.get('date', ''),
        reverse=True
    )
    
    msg = f"⏳ *APUESTAS PENDIENTES* ({len(pending_bets)})\n\n"
    
    for i, bet in enumerate(sorted_pending[:20], 1):  # Máximo 20
        # Información completa
        home = bet.get('home_team', 'Team A')
        away = bet.get('away_team', 'Team B')
        sport = bet.get('sport', '')
        market = bet.get('market', '')
        selection = bet.get('selection', 'N/A')
        point = bet.get('point', '')
        odds = bet.get('odds', 0)
        stake = bet.get('stake', 0)
        
        # Formatear fecha
        game_time = bet.get('commence_time', bet.get('date', ''))
        if game_time:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%d/%m/%Y %H:%M')
            except:
                formatted_date = game_time[:16]
        else:
            formatted_date = "N/A"
        
        # Tipo de apuesta
        if 'spread' in market.lower() or 'handicap' in market.lower():
            bet_type = "HANDICAP"
        elif 'total' in market.lower() or 'over' in selection.lower() or 'under' in selection.lower():
            bet_type = "TOTALES"
        elif 'h2h' in market.lower() or 'moneyline' in market.lower():
            bet_type = "GANADOR"
        else:
            bet_type = market.upper() if market else "APUESTA"
        
        msg += f"{i}. ⏳ *{bet_type}*\n"
        msg += f"   🏟️ {home} vs {away}\n"
        if sport:
            msg += f"   ⚽ {sport.upper()}\n"
        msg += f"   🎯 {selection}"
        if point:
            msg += f" ({point})"
        msg += f"\n   💰 {odds:.2f} | 💵 {stake:.2f}€"
        msg += f"\n   📅 {formatted_date}\n\n"
        
        # Telegram tiene límite de 4096 caracteres
        if len(msg) > 3500:
            await query.message.reply_text(msg)
            msg = ""
    
    if msg:
        await query.message.reply_text(msg)
    
    # Botones para volver
    keyboard = [[
        InlineKeyboardButton("◀️ Volver a Estadísticas", callback_data="back_to_stats")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        f"📊 Total: {len(pending_bets)} apuestas pendientes\n"
        f"💡 Usa /verificar para marcar resultados", 
        reply_markup=reply_markup
    )


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
    
    msg = "📜 *HISTORIAL COMPLETO DE APUESTAS*\n\n"
    
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
        
        # Información completa
        home = bet.get('home_team', 'Team A')
        away = bet.get('away_team', 'Team B')
        sport = bet.get('sport', '')
        market = bet.get('market', '')
        selection = bet.get('selection', 'N/A')
        point = bet.get('point', '')
        odds = bet.get('odds', 0)
        stake = bet.get('stake', 0)
        profit = bet.get('profit')
        
        # Formatear fecha
        game_time = bet.get('commence_time', bet.get('date', ''))
        if game_time:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%d/%m/%Y %H:%M')
            except:
                formatted_date = game_time[:16]
        else:
            formatted_date = "N/A"
        
        # Tipo de apuesta
        if 'spread' in market.lower() or 'handicap' in market.lower():
            bet_type = "HANDICAP"
        elif 'total' in market.lower() or 'over' in selection.lower() or 'under' in selection.lower():
            bet_type = "TOTALES"
        elif 'h2h' in market.lower() or 'moneyline' in market.lower():
            bet_type = "GANADOR"
        else:
            bet_type = market.upper() if market else "APUESTA"
        
        msg += f"{i}. {emoji} *{bet_type}*\n"
        msg += f"   🏟️ {home} vs {away}\n"
        if sport:
            msg += f"   ⚽ {sport.upper()}\n"
        msg += f"   🎯 {selection}"
        if point:
            msg += f" ({point})"
        msg += f"\n   💰 {odds:.2f} | 💵 {stake:.2f}€"
        
        if profit is not None:
            msg += f" | P/L: *{profit:+.2f}€*"
        
        msg += f"\n   📅 {formatted_date}\n\n"
        
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


async def cmd_verificar_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /verificar_historial - Muestra apuestas pendientes del historial con botones
    """
    chat_id = update.effective_user.id
    users_manager = get_users_manager()
    user = users_manager.get_user(str(chat_id))
    
    if not user:
        await update.message.reply_text("❌ Usuario no encontrado. Usa /start primero")
        return
    
    # Filtrar solo apuestas pendientes
    pending_bets = [bet for bet in user.bet_history if bet.get('status') == 'pending']
    
    logger.info(f"🔍 /verificar - Usuario {chat_id} tiene {len(user.bet_history)} apuestas totales")
    logger.info(f"⏳ Apuestas pendientes: {len(pending_bets)}")
    
    # Debug: mostrar primeros 3 status
    for i, bet in enumerate(user.bet_history[:3], 1):
        logger.info(f"  {i}. event_id={bet.get('event_id')[:8]}... status={bet.get('status')}")
    
    if not pending_bets:
        await update.message.reply_text("✅ No tienes apuestas pendientes de verificar")
        return
    
    msg = f"⏳ **APUESTAS PENDIENTES** ({len(pending_bets)})\n\n"
    msg += "Marca el resultado de cada apuesta:\n\n"
    
    await update.message.reply_text(msg)
    
    # Enviar cada apuesta pendiente con botones
    for i, bet in enumerate(pending_bets[:20], 1):  # Máximo 20
        # Construir mensaje detallado
        home = bet.get('home_team', 'Team A')
        away = bet.get('away_team', 'Team B')
        sport = bet.get('sport', 'Sport')
        market = bet.get('market', '')
        selection = bet.get('selection', 'N/A')
        point = bet.get('point', '')
        odds = bet.get('odds', 0)
        stake = bet.get('stake', 0)
        
        # Usar commence_time si existe, sino date
        game_time = bet.get('commence_time', bet.get('date', ''))
        if game_time:
            # Formatear fecha de manera legible
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
                formatted_date = dt.strftime('%d/%m/%Y %H:%M')
            except:
                formatted_date = game_time[:16]
        else:
            formatted_date = "Fecha no disponible"
        
        # Determinar tipo de apuesta
        if 'spread' in market.lower() or 'handicap' in market.lower():
            bet_type = "🔢 HANDICAP"
        elif 'total' in market.lower() or 'over' in selection.lower() or 'under' in selection.lower():
            bet_type = "📊 TOTALES"
        elif 'h2h' in market.lower() or 'moneyline' in market.lower():
            bet_type = "🏆 GANADOR"
        else:
            bet_type = "🎯 APUESTA"
        
        bet_msg = f"**{i}. {bet_type}**\n\n"
        bet_msg += f"🏟️ {home} vs {away}\n"
        bet_msg += f"⚽ Deporte: {sport.upper()}\n\n"
        bet_msg += f"🎯 Pick: {selection}\n"
        if point:
            bet_msg += f"📊 Línea: {point}\n"
        bet_msg += f"💰 Cuota: {odds:.2f}\n"
        bet_msg += f"💵 Stake: {stake:.2f}€\n"
        bet_msg += f"📅 Partido: {formatted_date}\n"
        
        # Botones de verificación
        event_id = bet.get('event_id', bet.get('id', f"hist_{i}"))
        keyboard = [[
            InlineKeyboardButton("✅ Ganó", callback_data=f"verify_won_{chat_id}_{event_id}"),
            InlineKeyboardButton("❌ Perdió", callback_data=f"verify_lost_{chat_id}_{event_id}"),
            InlineKeyboardButton("🔄 Push", callback_data=f"verify_push_{chat_id}_{event_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(bet_msg, reply_markup=reply_markup)


async def cmd_limpiar_pendientes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /limpiar_pendientes [N] - Mantiene solo las últimas N apuestas (total o pendientes)
    Uso: /limpiar [N] [all]
    - /limpiar 10 → mantiene últimas 10 pendientes
    - /limpiar 50 all → mantiene últimas 50 apuestas en total (borra historial antiguo)
    """
    chat_id = update.effective_user.id
    
    # Verificar que es admin
    import os
    admin_id = os.getenv('CHAT_ID')
    if str(chat_id) != str(admin_id):
        await update.message.reply_text("❌ Solo el administrador puede usar este comando")
        return
    
    users_manager = get_users_manager()
    user = users_manager.get_user(str(chat_id))
    
    if not user:
        await update.message.reply_text("❌ Usuario no encontrado")
        return
    
    # Parsear argumentos
    clean_all = 'all' in [arg.lower() for arg in context.args] if context.args else False
    try:
        keep_last = int(context.args[0]) if context.args and context.args[0].isdigit() else 10
    except:
        keep_last = 10
    
    if clean_all:
        # Limpiar TODO el historial, mantener solo últimas N apuestas
        total_bets = len(user.bet_history)
        if total_bets <= keep_last:
            await update.message.reply_text(
                f"ℹ️ Solo tienes {total_bets} apuestas en total.\n"
                f"No es necesario limpiar."
            )
            return
        
        # Mantener solo las últimas N
        user.bet_history = user.bet_history[-keep_last:]
        deleted = total_bets - keep_last
        
        users_manager.save()
        
        msg = f"🗑️ **HISTORIAL LIMPIADO**\n\n"
        msg += f"📊 Total anterior: {total_bets}\n"
        msg += f"❌ Eliminadas: {deleted}\n"
        msg += f"✅ Mantenidas: {keep_last}\n"
        
        await update.message.reply_text(msg)
        logger.info(f"🗑️ Admin {chat_id} limpió historial: {deleted} apuestas eliminadas")
    else:
        # Solo marcar pendientes como canceladas
        pending_bets = [bet for bet in user.bet_history if bet.get('status') == 'pending']
        
        if not pending_bets:
            await update.message.reply_text("✅ No tienes apuestas pendientes")
            return
        
        total_pending = len(pending_bets)
        
        if total_pending <= keep_last:
            await update.message.reply_text(
                f"ℹ️ Solo tienes {total_pending} apuestas pendientes.\n"
                f"No es necesario limpiar (quieres mantener {keep_last})."
            )
            return
        
        # Mantener solo las últimas N pendientes, marcar el resto como "cancelled"
        to_cancel = total_pending - keep_last
        cancelled_count = 0
        
        for bet in user.bet_history:
            if bet.get('status') == 'pending':
                if cancelled_count < to_cancel:
                    bet['status'] = 'cancelled'
                    bet['result_verified_at'] = datetime.now(timezone.utc).isoformat()
                    cancelled_count += 1
        
        # Guardar cambios
        users_manager.save()
        
        msg = f"🗑️ **LIMPIEZA COMPLETADA**\n\n"
        msg += f"📊 Total pendientes: {total_pending}\n"
        msg += f"❌ Canceladas: {cancelled_count}\n"
        msg += f"✅ Mantenidas: {keep_last}\n\n"
        msg += f"Las apuestas canceladas ya no aparecerán en /verificar"
        
        await update.message.reply_text(msg)
        logger.info(f"🗑️ Admin {chat_id} limpió {cancelled_count} apuestas pendientes")


async def cmd_reset_historial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /reset_historial - BORRA TODO y resetea bank a 200€
    """
    chat_id = update.effective_user.id
    
    # Verificar que es admin
    import os
    admin_id = os.getenv('CHAT_ID')
    if str(chat_id) != str(admin_id):
        await update.message.reply_text("❌ Solo el administrador puede usar este comando")
        return
    
    users_manager = get_users_manager()
    user = users_manager.get_user(str(chat_id))
    
    if not user:
        await update.message.reply_text("❌ Usuario no encontrado")
        return
    
    # Guardar info antes de borrar
    total_bets = len(user.bet_history)
    old_bank = user.dynamic_bank
    
    # RESETEAR TODO
    user.bet_history = []
    user.dynamic_bank = 200.0
    
    users_manager.save()
    
    msg = f"🔥 **RESET COMPLETO**\n\n"
    msg += f"❌ Eliminadas: {total_bets} apuestas\n"
    msg += f"💰 Bank reseteado: {old_bank:.2f}€ → 200.00€\n\n"
    msg += f"✅ Historial limpio - Empezar de nuevo"
    
    await update.message.reply_text(msg)
    logger.info(f"🔥 Admin {chat_id} reseteó completamente el historial")
