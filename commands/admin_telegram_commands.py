"""
Comandos de Telegram para administración
"""

import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from data.users import get_users_manager

logger = logging.getLogger(__name__)


async def cmd_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /usuarios - Lista todos los usuarios registrados (solo admin)
    """
    chat_id = update.effective_user.id
    
    # Verificar que es admin
    admin_id = os.getenv('CHAT_ID')
    if str(chat_id) != str(admin_id):
        await update.message.reply_text("❌ Solo el administrador puede usar este comando")
        return
    
    users_manager = get_users_manager()
    all_users = list(users_manager.users.values())
    
    if not all_users:
        await update.message.reply_text("📭 No hay usuarios registrados")
        return
    
    # Ordenar por fecha de registro (más recientes primero)
    all_users.sort(key=lambda u: getattr(u, 'join_date', ''), reverse=True)
    
    # Estadísticas generales
    total = len(all_users)
    premium = sum(1 for u in all_users if u.is_premium_active())
    free = total - premium
    con_referrer = sum(1 for u in all_users if hasattr(u, 'referrer_id') and u.referrer_id)
    con_referidos = sum(1 for u in all_users if hasattr(u, 'referred_users') and len(u.referred_users) > 0)
    
    msg = f"👥 **USUARIOS REGISTRADOS**\n\n"
    msg += f"📊 **Total:** {total} usuarios\n"
    msg += f"💎 Premium: {premium}\n"
    msg += f"🆓 Free: {free}\n"
    msg += f"🔗 Con referrer: {con_referrer}\n"
    msg += f"👨‍👩‍👧‍👦 Con referidos: {con_referidos}\n\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    await update.message.reply_text(msg)
    
    # Enviar usuarios en grupos de 20
    for i in range(0, len(all_users), 20):
        batch = all_users[i:i+20]
        user_msg = f"**Usuarios {i+1}-{min(i+20, total)}:**\n\n"
        
        for idx, user in enumerate(batch, start=i+1):
            username = f"@{user.username}" if user.username else user.chat_id
            status = "💎" if user.is_premium_active() else "🆓"
            
            # Info adicional
            referidos_count = len(getattr(user, 'referred_users', []))
            saldo = getattr(user, 'saldo_comision', 0)
            
            user_msg += f"{idx}. {status} {username}\n"
            user_msg += f"   ID: `{user.chat_id}`\n"
            
            if user.is_premium_active():
                end_date = getattr(user, 'suscripcion_fin', '')
                if end_date:
                    try:
                        expiry = datetime.fromisoformat(end_date)
                        user_msg += f"   ⏰ Vence: {expiry.strftime('%d/%m/%Y')}\n"
                    except:
                        pass
            
            if referidos_count > 0:
                user_msg += f"   👥 Referidos: {referidos_count}\n"
            
            if saldo > 0:
                user_msg += f"   💰 Saldo: ${saldo:.2f}\n"
            
            if hasattr(user, 'referrer_id') and user.referrer_id:
                referrer = users_manager.get_user(user.referrer_id)
                if referrer:
                    user_msg += f"   🔗 Referido por: @{referrer.username}\n"
            
            user_msg += "\n"
        
        await update.message.reply_text(user_msg)
        
    # Resumen final
    summary = f"━━━━━━━━━━━━━━━━━━━━━━\n"
    summary += f"✅ Mostrando {total} usuarios"
    await update.message.reply_text(summary)


async def cmd_pagar_referidos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /pagar_referidos - Lista usuarios con saldo pendiente
    """
    chat_id = update.effective_user.id
    
    # Verificar que es admin
    admin_id = os.getenv('CHAT_ID')
    if str(chat_id) != str(admin_id):
        await update.message.reply_text("❌ Solo el administrador puede usar este comando")
        return
    
    users_manager = get_users_manager()
    pending_users = []
    
    # Buscar usuarios con saldo
    for user in users_manager.users.values():
        saldo = getattr(user, 'saldo_comision', 0)
        weekly_fee = getattr(user, 'weekly_fee_due', 0)
        weekly_earnings = getattr(user, 'weekly_referral_earnings', 0)
        withdrawal = getattr(user, 'withdrawal_amount', 0)
        
        total_pending = saldo + weekly_fee + weekly_earnings + withdrawal
        
        if total_pending > 0:
            pending_users.append({
                'user_id': user.chat_id,
                'username': user.username,
                'saldo': saldo,
                'weekly_fee': weekly_fee,
                'weekly_earnings': weekly_earnings,
                'withdrawal': withdrawal,
                'total': total_pending,
                'referrals': len(getattr(user, 'referred_users', []))
            })
    
    if not pending_users:
        await update.message.reply_text("✅ No hay comisiones pendientes de pago")
        return
    
    # Ordenar por total pendiente descendente
    pending_users.sort(key=lambda x: x['total'], reverse=True)
    
    msg = "💰 **PAGOS PENDIENTES**\n\n"
    
    total_all = 0
    for i, user_data in enumerate(pending_users[:10], 1):
        user_id = user_data['user_id']
        username = user_data['username']
        total = user_data['total']
        total_all += total
        
        msg += f"{i}. @{username} (ID: {user_id})\n"
        
        # Desglose
        if user_data['saldo'] > 0:
            msg += f"   💰 Comisiones: ${user_data['saldo']:.2f}\n"
        if user_data['weekly_fee'] > 0:
            msg += f"   📊 Bank (50%): ${user_data['weekly_fee']:.2f}\n"
        if user_data['weekly_earnings'] > 0:
            msg += f"   👥 Semanales: ${user_data['weekly_earnings']:.2f}\n"
        if user_data['withdrawal'] > 0:
            msg += f"   💵 Retiro: ${user_data['withdrawal']:.2f}\n"
        
        msg += f"   **💵 TOTAL: ${total:.2f} USD**\n"
        msg += f"   👥 Referidos: {user_data['referrals']}\n\n"
        
        # Botón para marcar como pagado
        keyboard = [[
            InlineKeyboardButton("✅ Marcar como PAGADO", callback_data=f"pagar_{user_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        detail_msg = f"👤 **@{username}**\n\n"
        if user_data['saldo'] > 0:
            detail_msg += f"💰 Comisiones: ${user_data['saldo']:.2f}\n"
        if user_data['weekly_fee'] > 0:
            detail_msg += f"📊 Bank (50%): ${user_data['weekly_fee']:.2f}\n"
        if user_data['weekly_earnings'] > 0:
            detail_msg += f"👥 Semanales: ${user_data['weekly_earnings']:.2f}\n"
        if user_data['withdrawal'] > 0:
            detail_msg += f"💵 Retiro: ${user_data['withdrawal']:.2f}\n"
        detail_msg += f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        detail_msg += f"💵 **TOTAL: ${total:.2f} USD**"
        
        await update.message.reply_text(
            detail_msg,
            reply_markup=reply_markup
        )
    
    if len(pending_users) > 10:
        msg += f"\n... y {len(pending_users) - 10} más"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💰 **TOTAL PENDIENTE:** ${total_all:.2f} USD\n"
    msg += f"👥 **{len(pending_users)} usuarios** con saldo"
    
    await update.message.reply_text(msg)


async def handle_pagar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler para botón de pagar comisión
    """
    query = update.callback_query
    await query.answer()
    
    # Parse callback data
    parts = query.data.split('_')
    if len(parts) != 2 or parts[0] != 'pagar':
        await query.edit_message_text("❌ Error: Formato de callback inválido")
        return
    
    user_id = parts[1]
    
    # Obtener usuario
    users_manager = get_users_manager()
    user = users_manager.get_user(user_id)
    
    if not user:
        await query.edit_message_text(f"❌ Usuario {user_id} no encontrado")
        return
    
    if not hasattr(user, 'saldo_comision') or user.saldo_comision <= 0:
        await query.edit_message_text(f"❌ Usuario sin saldo pendiente")
        return
    
    # Obtener saldo antes de pagar
    amount_paid = user.saldo_comision
    weekly_fee = getattr(user, 'weekly_fee_due', 0)
    weekly_earnings = getattr(user, 'weekly_referral_earnings', 0)
    withdrawal = getattr(user, 'withdrawal_amount', 0)
    
    total_to_pay = amount_paid + weekly_fee + weekly_earnings + withdrawal
    
    # Marcar como pagado y resetear TODOS los saldos pendientes
    if hasattr(user, 'pagar_comision'):
        user.pagar_comision()
    else:
        # Fallback manual
        user.saldo_comision = 0
        if not hasattr(user, 'total_commission_paid'):
            user.total_commission_paid = 0
        user.total_commission_paid += amount_paid
    
    # Resetear accumulated_balance (alias del saldo)
    user.accumulated_balance = 0.0
    
    # Resetear ganancias semanales de referidos
    if hasattr(user, 'weekly_referral_earnings'):
        user.weekly_referral_earnings = 0.0
    
    # Resetear fee semanal pendiente (50% ganancias bank)
    if hasattr(user, 'weekly_fee_due'):
        user.weekly_fee_due = 0.0
    
    # Resetear solicitud de retiro pendiente
    if hasattr(user, 'pending_withdrawal'):
        user.pending_withdrawal = False
    if hasattr(user, 'withdrawal_amount'):
        user.withdrawal_amount = 0.0
    
    # Guardar cambios
    users_manager.save()
    
    logger.info(f"💰 Admin pagó a usuario {user_id}:")
    logger.info(f"  - Comisiones referidos: ${amount_paid:.2f}")
    logger.info(f"  - Fee semanal (50% bank): ${weekly_fee:.2f}")
    logger.info(f"  - Ganancias semanales: ${weekly_earnings:.2f}")
    logger.info(f"  - Retiro pendiente: ${withdrawal:.2f}")
    logger.info(f"  💵 TOTAL PAGADO: ${total_to_pay:.2f}")
    
    # Notificar usuario
    try:
        from notifier.telegram import TelegramNotifier
        notifier = TelegramNotifier(os.getenv('BOT_TOKEN'))
        
        user_msg = f"✅ **PAGO PROCESADO**\n\n"
        
        # Desglose de pago
        if amount_paid > 0:
            user_msg += f"💰 Comisiones referidos: ${amount_paid:.2f}\n"
        if weekly_fee > 0:
            user_msg += f"📊 50% ganancias bank: ${weekly_fee:.2f}\n"
        if weekly_earnings > 0:
            user_msg += f"👥 Ganancias semanales: ${weekly_earnings:.2f}\n"
        if withdrawal > 0:
            user_msg += f"💵 Retiro pendiente: ${withdrawal:.2f}\n"
        
        user_msg += f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        user_msg += f"💵 **TOTAL PAGADO: ${total_to_pay:.2f} USD**\n"
        user_msg += f"📅 Fecha: {query.message.date.strftime('%d/%m/%Y')}\n\n"
        user_msg += f"El pago ha sido enviado a tu cuenta.\n"
        user_msg += f"Tu saldo ahora es $0.00\n\n"
        user_msg += f"¡Gracias por confiar en nosotros! 🎉"
        
        await notifier.send_message(user_id, user_msg)
        logger.info(f"📤 Notificación de pago enviada a {user_id}")
    except Exception as e:
        logger.error(f"Error notificando usuario: {e}")
    
    # Actualizar mensaje del admin
    updated_msg = f"✅ **PAGADO**\n\n"
    updated_msg += f"👤 @{user.username} (ID: {user_id})\n\n"
    
    if amount_paid > 0:
        updated_msg += f"💰 Comisiones: ${amount_paid:.2f}\n"
    if weekly_fee > 0:
        updated_msg += f"📊 Bank (50%): ${weekly_fee:.2f}\n"
    if weekly_earnings > 0:
        updated_msg += f"👥 Semanales: ${weekly_earnings:.2f}\n"
    if withdrawal > 0:
        updated_msg += f"💵 Retiro: ${withdrawal:.2f}\n"
    
    updated_msg += f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
    updated_msg += f"💵 **TOTAL: ${total_to_pay:.2f} USD**\n"
    updated_msg += f"📅 {query.message.date.strftime('%d/%m/%Y %H:%M')}\n\n"
    updated_msg += f"✅ Todos los saldos reseteados a $0"
    
    await query.edit_message_text(updated_msg)


async def cmd_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /saldo - Muestra saldo de comisiones del usuario
    """
    chat_id = update.effective_user.id
    users_manager = get_users_manager()
    user = users_manager.get_user(str(chat_id))
    
    if not user:
        await update.message.reply_text("❌ Usuario no encontrado. Usa /start primero")
        return
    
    saldo_comision = getattr(user, 'saldo_comision', 0)
    weekly_fee = getattr(user, 'weekly_fee_due', 0)
    weekly_earnings = getattr(user, 'weekly_referral_earnings', 0)
    withdrawal = getattr(user, 'withdrawal_amount', 0)
    
    total_pendiente = saldo_comision + weekly_fee + weekly_earnings + withdrawal
    
    total_ganado = getattr(user, 'total_commission_earned', 0)
    total_pagado = getattr(user, 'total_commission_paid', 0)
    referidos = len(getattr(user, 'referred_users', []))
    
    msg = "💰 **TU SALDO**\n\n"
    
    # Desglose detallado
    if saldo_comision > 0:
        msg += f"💰 Comisiones referidos: ${saldo_comision:.2f}\n"
    if weekly_fee > 0:
        msg += f"📊 50% ganancias bank: ${weekly_fee:.2f}\n"
    if weekly_earnings > 0:
        msg += f"👥 Ganancias semanales: ${weekly_earnings:.2f}\n"
    if withdrawal > 0:
        msg += f"💵 Retiro solicitado: ${withdrawal:.2f}\n"
    
    if total_pendiente == 0:
        msg += "✅ No tienes saldo pendiente\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💵 **TOTAL DISPONIBLE: ${total_pendiente:.2f} USD**\n\n"
    msg += f"📊 Total ganado histórico: ${total_ganado:.2f}\n"
    msg += f"✅ Total cobrado: ${total_pagado:.2f}\n\n"
    msg += f"👥 Referidos activos: {referidos}\n\n"
    
    if total_pendiente >= 10:
        msg += "✅ **Puedes solicitar retiro**\n"
        msg += "📱 Contacta al admin para cobrar:\n"
        msg += f"   /pagar @{user.username}"
    else:
        msg += f"⚠️ Mínimo para retiro: $10.00 USD\n"
        msg += f"💪 Te faltan: ${10 - total_pendiente:.2f} USD"
    
    await update.message.reply_text(msg)
