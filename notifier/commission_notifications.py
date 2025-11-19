"""
notifier/commission_notifications.py - Notificaciones del sistema de comisiones.
"""
from typing import Dict
from data.users import get_users_manager, PREMIUM_PRICE_EUR, COMMISSION_PERCENTAGE, PAID_REFERRALS_FOR_FREE_WEEK


def format_commission_notification(user_id: str, commission_info: Dict) -> str:
    """
    Genera notificación cuando un usuario gana comisión.
    
    Args:
        user_id: ID del usuario que gana comisión
        commission_info: Dict con info de add_paid_referral()
    
    Returns:
        Mensaje de notificación
    """
    commission = commission_info['commission']
    new_balance = commission_info['new_balance']
    payment_amount = commission_info['payment_amount']
    total_referrals = commission_info['total_paid_referrals']
    
    return (
        f"🎉 ¡Tu referido ha pagado la suscripción premium!\n"
        f"💰 Comisión ganada: {commission:.2f} €\n"
        f"💵 Saldo total acumulado: {new_balance:.2f} €\n\n"
        f"Para retirar tu saldo, por favor escribe al soporte/admin."
    )


def format_free_week_notification(user_id: str, commission_info: Dict) -> str:
    """
    Genera notificación cuando un usuario gana semana gratis.
    
    Args:
        user_id: ID del usuario
        commission_info: Dict con info de add_paid_referral()
    
    Returns:
        Mensaje de notificación
    """
    total_referrals = commission_info['total_paid_referrals']
    users_manager = get_users_manager()
    user = users_manager.get_user(user_id)
    
    return (
        f"🎉 ¡Felicidades! Has alcanzado 3 referidos pagos.\n"
        f"⏳ Has recibido 1 semana gratis de suscripción Premium."
    )


def format_payment_processed_notification(user_id: str, amount: float) -> str:
    """
    Genera notificación cuando se procesa un pago de suscripción.
    
    Args:
        user_id: ID del usuario que pagó
        amount: Monto pagado
    
    Returns:
        Mensaje de notificación
    """
    users_manager = get_users_manager()
    user = users_manager.get_user(user_id)
    
    return (
        f"✅ PAGO PROCESADO ✅\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 Pago recibido: {amount:.2f} €\n"
        f"⭐ PREMIUM ACTIVADO por 1 semana\n\n"
        f"📅 Tu suscripción termina: {user.suscripcion_fin[:10] if user.suscripcion_fin else 'Error'}\n\n"
        f"🌟 BENEFICIOS PREMIUM:\n"
        f"✅ Alertas ILIMITADAS de valor\n"
        f"✅ Análisis completo con estadísticas\n"
        f"✅ Stakes recomendados\n"
        f"✅ Gestión automática de bankroll\n"
        f"✅ Tracking de ROI y resultados\n\n"
        f"💡 GANA DINERO:\n"
        f"👥 Refiere amigos y gana {PREMIUM_PRICE_EUR * (COMMISSION_PERCENTAGE/100):.2f} € por cada uno\n"
        f"🎁 Cada {PAID_REFERRALS_FOR_FREE_WEEK} referidos pagos = 1 semana gratis\n"
        f"💬 Usa /mi_link para obtener tu enlace de referido"
    )


def format_referrer_earned_notification(referrer_id: str, referred_user_id: str, amount: float) -> str:
    """
    Genera notificación para el referidor cuando su referido paga.
    
    Args:
        referrer_id: ID del usuario que refirió
        referred_user_id: ID del usuario que pagó
        amount: Monto pagado por el referido
    
    Returns:
        Mensaje de notificación
    """
    commission = amount * (COMMISSION_PERCENTAGE / 100)
    
    return (
        f"🚨 ¡REFERIDO PAGÓ! 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Tu referido acaba de pagar su suscripción\n"
        f"💰 Monto: {amount:.2f} €\n"
        f"📈 Comisión ganada: {commission:.2f} €\n\n"
        f"⏰ Comisión agregada automáticamente\n"
        f"💬 Usa /mis_comisiones para ver tu saldo\n\n"
        f"🔥 ¡Sigue refiriendo para ganar más!"
    )


def format_commission_withdrawal_notification(user_id: str, amount: float) -> str:
    """
    Genera notificación cuando se procesa un retiro de comisiones.
    
    Args:
        user_id: ID del usuario
        amount: Monto retirado
    
    Returns:
        Mensaje de notificación
    """
    return (
        f"💸 RETIRO PROCESADO 💸\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Retiro completado\n"
        f"💰 Monto: {amount:.2f} €\n"
        f"📱 El dinero se enviará según el método acordado\n\n"
        f"📊 Tu saldo de comisiones ahora es: 0.00 €\n\n"
        f"🔄 ¡Sigue refiriendo para ganar más!\n"
        f"👥 Cada referido que pague = {PREMIUM_PRICE_EUR * (COMMISSION_PERCENTAGE/100):.2f} €\n"
        f"💬 Usa /mi_link para obtener tu enlace"
    )


def format_subscription_expiry_warning(user_id: str, days_left: int) -> str:
    """
    Genera notificación de advertencia cuando la suscripción está por expirar.
    
    Args:
        user_id: ID del usuario
        days_left: Días restantes de suscripción
    
    Returns:
        Mensaje de advertencia
    """
    if days_left == 1:
        urgency = "⚠️ ¡ÚLTIMO DÍA!"
        message = "Tu suscripción premium expira MAÑANA"
    elif days_left <= 3:
        urgency = "⏰ ¡POCOS DÍAS!"
        message = f"Tu suscripción premium expira en {days_left} días"
    else:
        urgency = "📅 Recordatorio"
        message = f"Tu suscripción premium expira en {days_left} días"
    
    return (
        f"{urgency}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 {message}\n\n"
        f"🔄 RENOVAR SUSCRIPCIÓN:\n"
        f"💳 {PREMIUM_PRICE_EUR:.0f} € por 1 semana\n"
        f"💬 Contacta al administrador para pagar\n\n"
        f"🆓 O GANA SEMANA GRATIS:\n"
        f"👥 Refiere {PAID_REFERRALS_FOR_FREE_WEEK} amigos que paguen\n"
        f"🎁 = 1 semana premium gratis automática\n\n"
        f"💰 PLUS: Gana {PREMIUM_PRICE_EUR * (COMMISSION_PERCENTAGE/100):.2f} € por cada referido\n"
        f"📲 Usa /mi_link para tu enlace de referido"
    )