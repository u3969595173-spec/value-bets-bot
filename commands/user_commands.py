"""
commands/user_commands.py - Comandos de Telegram para gestión de usuarios.

Comandos disponibles:
- /start - Registro inicial (con detección de referidos)
- /stats - Ver estadísticas (premium)
- /upgrade - Info sobre premium
- /bankroll <monto> - Ajustar bankroll (premium)
- /referir - Obtener link de referido
- /mis_referidos - Ver estadísticas de referidos
- /reset - Resetear contador de alertas
- /premium - Ver opciones de pago Premium
- /mi_link - Obtener enlace de referidos
- /mis_comisiones - Ver estadísticas de comisiones
- /pagar - Simular pago (testing)
"""
from typing import Dict
import logging
from data.users import get_users_manager
from referrals.referral_system import ReferralSystem
from notifier.alert_formatter import format_stats_message
from notifier.premium_messages import (
    format_free_vs_premium_message,
    get_payment_keyboard,
    format_payment_confirmation_message,
    format_premium_activated_message,
    format_usdt_payment_message,
    format_free_limit_message
)


async def handle_start_command(chat_id: str, args: str = "") -> str:
    """Comando /start - Registra o saluda al usuario, procesando referidos."""
    users_manager = get_users_manager()
    
    # Extraer código de referido si existe
    referral_code = None
    if args.startswith("ref_"):
        referral_code = args[4:]  # Quitar "ref_"
    
    # Verificar si es usuario existente
    is_new_user = chat_id not in users_manager.users
    
    user = users_manager.get_user(chat_id, referral_code if is_new_user else None)
    
    # Mensaje para nuevos usuarios con referido
    if is_new_user and user.referrer_id:
        return (
            f"🎉 ¡Bienvenido al Bot de Value Bets!\n\n"
            f"👥 Has sido referido por un usuario\n"
            f"🎁 ¡Tu referidor ganará beneficios por invitarte!\n\n"
            f"🆓 Cuenta GRATUITA activada\n"
            f"📬 Recibirás 1 alerta diaria\n\n"
            f"✨ ¿Quieres MAS alertas?\n"
            f"👥 ¡Invita a 5 amigos y gana 1 semana PREMIUM gratis!\n"
            f"📲 Usa /referir para obtener tu link\n\n"
            f"💬 Usa /upgrade para más info sobre PREMIUM"
        )
    
    # Mensaje para usuarios existentes
    if user.is_premium_active():
        premium_info = ""
        if user.premium_expires_at and not user.is_permanent_premium:
            from datetime import datetime, timezone
            expiry = datetime.fromisoformat(user.premium_expires_at)
            days_left = (expiry - datetime.now(timezone.utc)).days
            premium_info = f" (expira en {days_left} días)"
        
        return (
            f"👋 Bienvenido de vuelta, usuario PREMIUM{premium_info}!\n\n"
            f"💼 Bankroll: ${user.bankroll:.2f}\n"
            f"📬 Alertas hoy: {user.alerts_sent_today}/{user.get_max_alerts()}\n"
            f"👥 Referidos: {len(user.referred_users)}/5 para próxima semana\n\n"
            f"Comandos disponibles:\n"
            f"/stats - Ver tus estadísticas\n"
            f"/bankroll <monto> - Ajustar tu bankroll\n"
            f"/referir - Tu link de referido\n"
            f"/mis_referidos - Ver referidos\n"
            f"/reset - Resetear contador de alertas\n"
        )
    else:
        return (
            f"👋 ¡Bienvenido al Bot de Value Bets!\n\n"
            f"🆓 Cuenta GRATUITA activada\n"
            f"📬 Recibirás 1 alerta diaria\n\n"
            f"🌟 PREMIUM GRATIS:\n"
            f"👥 Invita a 5 amigos = 1 semana PREMIUM\n"
            f"📲 Usa /referir para tu link\n\n"
            f"🌟 UPGRADE A PREMIUM:\n"
            f"✨ Alertas ILIMITADAS\n"
            f"📊 Análisis completo\n"
            f"💰 Stake recomendado\n"
            f"📈 Gestión de bankroll\n"
            f"🎯 Tracking de ROI\n\n"
            f"💬 Usa /upgrade para más info"
        )


async def handle_stats_command(chat_id: str) -> str:
    """Comando /stats - Muestra estadísticas del usuario premium."""
    users_manager = get_users_manager()
    user = users_manager.get_user(chat_id)
    
    return format_stats_message(user)


async def handle_upgrade_command(chat_id: str) -> str:
    """Comando /upgrade - Información sobre cuenta premium."""
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🌟 UPGRADE A PREMIUM 💎\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "BENEFICIOS PREMIUM:\n\n"
        "✨ Alertas ILIMITADAS de valor\n"
        "📊 Análisis completo con estadísticas avanzadas\n"
        "💎 Probabilidades reales y valor esperado\n"
        "💰 Stake recomendado según tu bankroll\n"
        "📈 Gestión automática de bankroll\n"
        "🎯 Tracking completo: ROI, win rate, profit\n"
        "⚡ Detección de sharp money signals\n"
        "🔍 Análisis de consensus entre bookmakers\n"
        "📊 Monitoreo de movimientos de línea\n\n"
        "💶 *IMPORTANTE*\n"
        "El bot cobrará el 20% de las ganancias generadas cada semana (según tu bank dinámico).\n"
        "El cobro se realiza todos los lunes temprano, sobre las ganancias de la semana anterior.\n"
        "Para seguir en Premium, debes contactar con el administrador y realizar el pago correspondiente.\n"
        "Si no pagas, serás retirado del Premium.\n\n"
        "🔄 *REPARTO DEL 20% COBRADO*\n"
        "- El 50% se destina a arreglos y mejoras del bot.\n"
        "- El otro 50% se reparte entre los 3 usuarios que más referidos premium hayan traído esa semana:\n"
        "   • 1er lugar: 50% de ese fondo\n"
        "   • 2do lugar: 30%\n"
        "   • 3er lugar: 20%\n\n"
        "💬 Contacta para activar tu cuenta premium:\n"
        "[Contacto del administrador]"
    )


async def handle_bankroll_command(chat_id: str, args: str) -> str:
    """
    Comando /bankroll <monto> - Ajusta el bankroll (solo premium).
    
    Args:
        chat_id: ID del chat
        args: Argumentos del comando (monto)
    """
    users_manager = get_users_manager()
    user = users_manager.get_user(chat_id)
    
    if user.nivel != "premium":
        return "⚠️  Este comando solo está disponible para usuarios PREMIUM."
    
    try:
        new_bankroll = float(args.strip())
        
        if new_bankroll <= 0:
            return "❌ El bankroll debe ser mayor que 0."
        
        if new_bankroll < 100:
            return "⚠️  Bankroll muy bajo. Recomendamos al menos $100 para gestión adecuada."
        
        old_bankroll = user.bankroll
        user.bankroll = new_bankroll
        user.initial_bankroll = new_bankroll
        users_manager.save()
        
        return (
            f"✅ Bankroll actualizado!\n\n"
            f"💼 Anterior: ${old_bankroll:.2f}\n"
            f"💼 Nuevo: ${new_bankroll:.2f}\n\n"
            f"💡 Los stakes se calcularán con el nuevo bankroll."
        )
        
    except ValueError:
        return (
            f"❌ Formato incorrecto.\n\n"
            f"Uso: /bankroll <monto>\n"
            f"Ejemplo: /bankroll 1000"
        )


async def handle_reset_command(chat_id: str) -> str:
    """Comando /reset - Resetea el contador de alertas diarias manualmente."""
    users_manager = get_users_manager()
    user = users_manager.get_user(chat_id)
    
    old_count = user.alerts_sent_today
    user.alerts_sent_today = 0
    users_manager.save()
    
    return (
        f"✅ Contador de alertas reseteado!\n\n"
        f"📬 Alertas anteriores: {old_count}/{user.get_max_alerts()}\n"
        f"📬 Alertas disponibles: {user.get_max_alerts()}/{user.get_max_alerts()}\n\n"
        f"🎯 Volverás a recibir pronósticos."
    )


async def handle_referir_command(chat_id: str) -> str:
    """Comando /referir - Genera link de referido del usuario."""
    users_manager = get_users_manager()
    user = users_manager.get_user(chat_id)
    
    bot_username = "tu_bot"  # Reemplazar con el username real del bot
    referral_link = f"https://t.me/{bot_username}?start=ref_{user.referral_code}"
    
    referidos_actuales = len(user.referred_users)
    referidos_necesarios = 5 - (referidos_actuales % 5)
    
    return (
        f"🎯 TU LINK DE REFERIDO\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔗 {referral_link}\n\n"
        f"📊 ESTADO ACTUAL:\n"
        f"👥 Referidos totales: {referidos_actuales}\n"
        f"🏆 Semanas ganadas: {user.premium_weeks_earned}\n"
        f"⏳ Faltan {referidos_necesarios} referidos para próxima semana PREMIUM\n\n"
        f"💡 CÓMO FUNCIONA:\n"
        f"✅ Comparte tu link único\n"
        f"👤 Cada 5 personas que se registren\n"
        f"🎁 Ganas 1 semana de PREMIUM gratis\n"
        f"♾️  Sin límite de semanas\n\n"
        f"🌟 BENEFICIOS PREMIUM:\n"
        f"• Alertas ILIMITADAS (vs 1 gratis)\n"
        f"• Análisis completo de valor\n"
        f"• Stakes recomendados\n"
        f"• Gestión de bankroll\n"
        f"• Tracking de ROI\n\n"
        f"📱 ¡Comparte ahora y empieza a ganar!"
    )


async def handle_mis_referidos_command(chat_id: str) -> str:
    """Comando /mis_referidos - Muestra estadísticas de referidos."""
    users_manager = get_users_manager()
    user = users_manager.get_user(chat_id)
    stats = users_manager.get_referral_stats(chat_id)
    
    # Formatear tiempo restante
    tiempo_premium = "Sin premium activo"
    if stats['premium_activo']:
        if stats['premium_permanente']:
            tiempo_premium = "PREMIUM PERMANENTE 🌟"
        else:
            tiempo_premium = f"{stats['premium_dias_restantes']} días restantes"
    
    return (
        f"📊 TUS ESTADÍSTICAS DE REFERIDOS\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 Tu código: {stats['referral_code']}\n"
        f"👥 Total referidos: {stats['total_referidos']}\n"
        f"🏆 Semanas ganadas: {stats['semanas_ganadas']}\n"
        f"⏰ Premium: {tiempo_premium}\n\n"
        f"🎯 PROGRESO ACTUAL:\n"
        f"📈 Faltan {stats['referidos_para_proxima']} referidos para próxima semana\n"
        f"🎁 Cada 5 referidos = 1 semana PREMIUM\n\n"
        f"🔗 USA /referir para obtener tu link\n"
        f"📱 ¡Sigue invitando para más semanas gratis!"
    )


async def handle_mi_link_command(chat_id: str) -> str:
    """Comando /mi_link - Genera link de referido con USER_ID."""
    bot_username = "Valueapuestasbot"  # Cambiar por el username real del bot
    referral_link = f"https://t.me/{bot_username}?start={chat_id}"
    
    users_manager = get_users_manager()
    user = users_manager.get_user(chat_id)
    stats = user.get_commission_stats()
    
    return (
        f"💼 TU LINK DE COMISIONES\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔗 {referral_link}\n\n"
        f"💰 GANA DINERO REAL:\n"
        f"👥 Por cada referido que pague 15€\n"
        f"📈 Ganas ${5:.0f} USD de comisión (10%)\n\n"
        f"🎁 SEMANAS GRATIS:\n"
        f"🏆 Cada 3 referidos pagos = 1 semana premium gratis\n\n"
        f"📊 TU ESTADO ACTUAL:\n"
        f"💵 Saldo acumulado: ${stats['saldo_actual']:.2f} USD\n"
        f"👥 Referidos pagos: {stats['referidos_pagos']}\n"
        f"🎁 Semanas gratis ganadas: {stats['semanas_gratis']}\n"
        f"⏳ Faltan {stats['referidos_para_proxima_semana']} referidos para próxima semana gratis\n\n"
        f"💸 RETIRO DE DINERO:\n"
        f"📱 Escribe al soporte cuando quieras retirar\n"
        f"💬 Contacta al administrador del bot\n\n"
        f"🚀 ¡Comparte tu link y empieza a ganar!"
    )


async def handle_mis_comisiones_command(chat_id: str) -> str:
    """Comando /mis_comisiones - Muestra estadísticas de comisiones."""
    users_manager = get_users_manager()
    user = users_manager.get_user(chat_id)
    stats = user.get_commission_stats()
    
    # Formatear fecha de suscripción
    subscription_info = "No activa"
    if stats['subscription_active']:
        end_date = stats['subscription_end'][:10] if stats['subscription_end'] else "Error"
        subscription_info = f"Activa hasta {end_date}"
    
    return (
        f"📊 TUS COMISIONES Y REFERIDOS\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 SALDO DE COMISIONES:\n"
        f"💵 Saldo actual: ${stats['saldo_actual']:.2f} USD\n"
        f"📈 Total ganado: ${stats['total_ganado']:.2f} USD\n\n"
        f"👥 REFERIDOS:\n"
        f"💳 Referidos pagos: {stats['referidos_pagos']}\n"
        f"🎁 Semanas gratis ganadas: {stats['semanas_gratis']}\n"
        f"⏳ Faltan {stats['referidos_para_proxima_semana']} para próxima semana gratis\n\n"
        f"🌟 SUSCRIPCIÓN:\n"
        f"📅 Estado: {subscription_info}\n\n"
        f"💡 CÓMO GANAR MÁS:\n"
        f"🔗 Usa /mi_link para obtener tu enlace\n"
        f"👥 Cada referido que pague = ${5:.0f} USD\n"
        f"🎁 Cada 3 referidos pagos = 1 semana gratis\n\n"
        f"💸 RETIRO:\n"
        f"📱 Escribe al soporte para retirar tu saldo\n"
        f"💬 Contacta al administrador"
    )


async def handle_pagar_command(chat_id: str, args: str) -> str:
    """
    Comando /pagar <monto> - Simula un pago de suscripción premium.
    SOLO PARA TESTING - En producción esto sería manejado por el gateway de pagos.
    """
    try:
        amount = float(args.strip())
        
        if amount <= 0:
            return "❌ El monto debe ser mayor que 0."
        
        users_manager = get_users_manager()
        user = users_manager.get_user(chat_id)
        
        # Procesar el pago
        payment_info = user.process_premium_payment(amount)
        users_manager.save()
        
        # Si hay referidor, procesar comisión AUTOMÁTICAMENTE
        commission_earned = False
        logger = logging.getLogger(__name__)
        
        if payment_info['referrer_commission']:
            referrer_id = payment_info['referrer_commission']['referrer_id']
            referrer = users_manager.get_user(referrer_id)
            
            # Procesar en sistema de usuarios (legacy)
            commission_info = referrer.add_paid_referral(amount)
            users_manager.save()
            
            # NUEVO: Procesar en ReferralSystem automáticamente
            try:
                referral_system = ReferralSystem()
                referral_result = referral_system.process_premium_payment(
                    user_id=chat_id,
                    amount_usd=amount,
                    payment_method="user_payment"
                )
                if referral_result['success'] and referral_result['reward_granted']:
                    logger.info(f"✅ Comisión automática: {referral_result['commission']:.2f}€ para {referrer_id}")
                    commission_earned = True
            except Exception as e:
                logger.error(f"❌ Error procesando comisión automática: {e}")
            
            # Marcar para envío de notificaciones
            payment_info['_send_commission_notification'] = {
                'referrer_id': referrer_id,
                'commission_info': commission_info
            }
            commission_earned = True
        
        response = (
            f"✅ PAGO SIMULADO PROCESADO\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💳 Monto: ${amount:.2f} USD\n"
            f"⭐ PREMIUM activado por 1 semana\n"
            f"📅 Expira: {payment_info['subscription_end'][:10]}\n\n"
        )
        
        if commission_earned:
            response += (
                f"💰 Tu referidor ganó comisión automáticamente\n"
                f"📨 Se le enviará notificación\n\n"
            )
        
        response += (
            f"🌟 Disfruta de todos los beneficios premium!\n"
            f"💬 Usa /mi_link para ganar dinero refiriendo"
        )
        
        return response
        
    except ValueError:
        return (
            f"❌ Formato incorrecto.\n\n"
            f"Uso: /pagar <monto>\n"
            f"Ejemplo: /pagar 15"
        )


async def handle_result_command(chat_id: str, args: str) -> str:
    """
    Comando /result <won/lost> - Registra resultado de última apuesta (premium).
    
    Args:
        chat_id: ID del chat
        args: "won" o "lost"
    """
    users_manager = get_users_manager()
    user = users_manager.get_user(chat_id)
    
    if user.nivel != "premium":
        return "⚠️  Este comando solo está disponible para usuarios PREMIUM."
    
    # TODO: Implementar tracking de última apuesta enviada
    # Por ahora, mensaje informativo
    return (
        "ℹ️  Funcionalidad en desarrollo.\n\n"
        "Próximamente podrás registrar resultados de tus apuestas con:\n"
        "/result won - Apuesta ganada\n"
        "/result lost - Apuesta perdida\n\n"
        "El sistema actualizará automáticamente tu bankroll y estadísticas."
    )


async def handle_premium_command(chat_id: str) -> str:
    """Comando /premium - Muestra opciones de pago Premium"""
    try:
        users_manager = get_users_manager()
        user = users_manager.get_user(chat_id)
        
        # Verificar si ya tiene Premium activo
        if user.is_subscription_active():
            return (f"✅ **Ya tienes Premium activo**\n\n"
                   f"⏱️ **Expira:** {user.suscripcion_fin}\n\n"
                   f"🎯 **Comparte tu link y gana dinero:**\n"
                   f"Usa /mi_link para obtener tu enlace de referidos")
        
        # Mostrar mensaje promocional
        return format_free_vs_premium_message()
        
    except Exception as e:
        return f"❌ Error al mostrar opciones Premium: {str(e)}"


async def activar_premium(user_id: str, weeks: int = 1) -> str:
    """Activa Premium para un usuario (función para admin)"""
    try:
        users_manager = get_users_manager()
        user = users_manager.get_user(user_id)
        
        # Añadir semanas de Premium
        user.add_free_premium_week(weeks)
        
        # Guardar cambios
        users_manager.save()
        
        return f"✅ Premium activado para usuario {user_id} por {weeks} semana(s)"
        
    except Exception as e:
        return f"❌ Error al activar Premium: {str(e)}"


async def check_free_user_limit(user_id: str) -> bool:
    """Verifica si usuario gratuito ha alcanzado su límite diario"""
    try:
        users_manager = get_users_manager()
        user = users_manager.get_user(user_id)
        
        # Si tiene Premium activo, no hay límite
        if user.is_subscription_active():
            return False
        
        # Para usuarios gratuitos, verificar límite diario (1 alerta)
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date()
        
        # Verificar en historial si ya recibió alerta hoy
        # (Esta lógica se puede expandir según tu sistema de tracking)
        return hasattr(user, '_daily_alerts_sent') and user._daily_alerts_sent >= 1
        
    except Exception as e:
        print(f"Error verificando límite: {e}")
        return False


async def get_free_limit_message() -> str:
    """Obtiene mensaje de límite alcanzado para usuario gratuito"""
    return format_free_limit_message()


async def handle_mi_deuda_command(chat_id: str) -> str:
    """
    Comando /mi_deuda - Muestra el estado de pagos del usuario premium.
    """
    users_manager = get_users_manager()
    user = users_manager.get_user(chat_id)
    
    if not user:
        return "❌ Usuario no encontrado. Usa /start primero."
    
    if user.nivel != "premium":
        return "❌ Este comando es solo para usuarios Premium."
    
    payment_status = user.get_payment_status()
    
    # Construir mensaje
    message = "💳 *ESTADO DE PAGOS*\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Información de Premium
    if user.suscripcion_fin:
        from datetime import datetime
        try:
            expiry = datetime.fromisoformat(user.suscripcion_fin)
            message += f"📅 Premium vence: {expiry.strftime('%d/%m/%Y')}\n\n"
        except:
            pass
    
    # Pago base semanal (15€)
    base_status = "✅ Pagado" if payment_status['base_paid'] else "❌ Pendiente"
    message += f"*PAGO BASE SEMANAL*\n"
    message += f"Monto: {payment_status['base_fee']:.2f} €\n"
    message += f"Estado: {base_status}\n\n"
    
    # Comisión por ganancias (20%)
    message += f"*COMISIÓN POR GANANCIAS (20%)*\n"
    message += f"Bank inicio semana: {payment_status['week_start_bank']:.2f} €\n"
    message += f"Bank actual: {payment_status['dynamic_bank_current']:.2f} €\n"
    
    if payment_status['weekly_profit'] > 0:
        fee_status = "✅ Pagado" if payment_status['weekly_fee_paid'] else "❌ Pendiente"
        message += f"Ganancia semanal: +{payment_status['weekly_profit']:.2f} €\n"
        message += f"20% adeudado: {payment_status['weekly_fee_due']:.2f} €\n"
        message += f"Estado: {fee_status}\n"
    elif payment_status['weekly_profit'] < 0:
        message += f"Pérdida semanal: {payment_status['weekly_profit']:.2f} €\n"
        message += f"20% adeudado: 0.00 € (no se cobra en pérdidas)\n"
    else:
        message += f"Sin ganancias aún esta semana\n"
        message += f"20% adeudado: 0.00 €\n"
    
    # Total adeudado
    message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    message += f"💰 *TOTAL ADEUDADO: {payment_status['total_due']:.2f} €*\n\n"
    message += f"💬 Contacta al administrador para realizar el pago."
    
    return message


# Mapeo de comandos
COMMAND_HANDLERS = {
    "/start": handle_start_command,
    "/stats": handle_stats_command,
    "/upgrade": handle_upgrade_command,
    "/bankroll": handle_bankroll_command,
    "/reset": handle_reset_command,
    "/referir": handle_referir_command,
    "/mis_referidos": handle_mis_referidos_command,
    "/mi_link": handle_mi_link_command,
    "/mis_comisiones": handle_mis_comisiones_command,
    "/pagar": handle_pagar_command,
    "/premium": handle_premium_command,
    "/result": handle_result_command,
    "/mi_deuda": handle_mi_deuda_command,
}


async def process_command(chat_id: str, command: str, args: str = "") -> str:
    """
    Procesa un comando de Telegram.
    
    Args:
        chat_id: ID del chat
        command: Comando (ej: "/start")
        args: Argumentos del comando
    
    Returns:
        Mensaje de respuesta
    """
    handler = COMMAND_HANDLERS.get(command)
    
    if not handler:
        return f"❌ Comando desconocido: {command}"
    
    # Comandos con argumentos
    if command in ["/bankroll", "/result", "/start", "/pagar"]:
        return await handler(chat_id, args)
    else:
        return await handler(chat_id)
