# -*- coding: utf-8 -*-
"""
Ejemplo de cómo integrar auto_fill.py en main.py de CitasBot

INSTRUCCIONES:
1. Importar el módulo auto_fill al inicio de main.py
2. Modificar la función cita_disponible_handler para usar auto-llenado
3. Si auto-llenado falla, enviar notificación manual como respaldo
"""

# ============================================================================
# PASO 1: AGREGAR IMPORT AL INICIO DE main.py (después de otros imports)
# ============================================================================

from auto_fill import auto_fill_appointment

# ============================================================================
# PASO 2: MODIFICAR cita_disponible_handler EN main.py
# ============================================================================

# ENCONTRAR la función cita_disponible_handler actual (aprox línea 200-250)
# REEMPLAZAR con esta versión mejorada:

async def cita_disponible_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cuando se detecta una cita disponible"""
    try:
        # Extraer fechas del mensaje
        query = update.callback_query
        dates_str = query.data.replace('cita_disponible_', '')
        
        # Obtener datos del usuario de la base de datos
        user_id = query.from_user.id
        user_data = db.get_user_data(user_id)
        
        if not user_data:
            await query.answer()
            await query.edit_message_text(
                "❌ No se encontraron tus datos. Usa /registrar primero."
            )
            return
        
        # Preparar datos para auto-llenado
        fill_data = {
            'name': user_data['name'],
            'document': user_data['document'],
            'email': user_data['email'],
            'phone': user_data['phone']
        }
        
        # Extraer primera fecha disponible
        dates_list = dates_str.split(',')
        first_date = dates_list[0].strip() if dates_list else dates_str
        
        await query.answer()
        
        # Notificar que se está intentando reserva automática
        processing_msg = await query.edit_message_text(
            f"🤖 *¡CITA DISPONIBLE!*\n\n"
            f"📅 Fecha: {first_date}\n\n"
            f"⚙️ *Intentando reserva automática...*\n"
            f"Por favor espera...",
            parse_mode='Markdown'
        )
        
        logger.info(f"🤖 Iniciando auto-llenado para usuario {user_id} - Fecha: {first_date}")
        
        # ============================================
        # INTENTO 1: AUTO-LLENADO AUTOMÁTICO
        # ============================================
        try:
            result = await auto_fill_appointment(fill_data, first_date)
            
            if result['success']:
                # ✅ ÉXITO - Reserva completada automáticamente
                confirmation = result.get('confirmation', 'COMPLETADO')
                
                success_message = (
                    f"✅ *¡RESERVA COMPLETADA AUTOMÁTICAMENTE!*\n\n"
                    f"📅 Fecha: {first_date}\n"
                    f"🎫 Confirmación: {confirmation}\n\n"
                    f"📋 *Tus datos:*\n"
                    f"• Nombre: {fill_data['name']}\n"
                    f"• Documento: {fill_data['document']}\n"
                    f"• Email: {fill_data['email']}\n"
                    f"• Teléfono: {fill_data['phone']}\n\n"
                    f"📧 Revisa tu email para más detalles.\n"
                    f"🔗 Puedes verificar en: https://citaprevia.ciencia.gob.es/qmaticwebbooking/#/"
                )
                
                await processing_msg.edit_text(success_message, parse_mode='Markdown')
                
                # Notificar al admin
                admin_message = (
                    f"✅ *AUTO-RESERVA EXITOSA*\n\n"
                    f"👤 Usuario: {fill_data['name']} (ID: {user_id})\n"
                    f"📅 Fecha: {first_date}\n"
                    f"🎫 Confirmación: {confirmation}"
                )
                await context.bot.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=admin_message,
                    parse_mode='Markdown'
                )
                
                logger.info(f"✅ Reserva automática completada para usuario {user_id}")
                return
                
            else:
                # ⚠️ Auto-llenado falló, pasar a método manual
                error_msg = result.get('message', 'Error desconocido')
                logger.warning(f"⚠️ Auto-llenado falló: {error_msg}")
                
                # Continuar con notificación manual (siguiente bloque)
                
        except Exception as e:
            logger.error(f"❌ Error durante auto-llenado: {e}", exc_info=True)
            # Continuar con notificación manual
        
        # ============================================
        # INTENTO 2: NOTIFICACIÓN MANUAL (RESPALDO)
        # ============================================
        logger.info(f"📱 Enviando notificación manual de respaldo para usuario {user_id}")
        
        # Extraer fechas del dict si es necesario
        if isinstance(dates_list, list) and len(dates_list) > 0:
            if isinstance(dates_list[0], dict):
                date_strings = [d.get('date', str(d)) for d in dates_list]
            else:
                date_strings = [str(d) for d in dates_list]
        else:
            date_strings = [dates_str]
        
        manual_message = (
            f"🎯 *¡CITA DISPONIBLE!*\n\n"
            f"⚠️ *El auto-llenado no pudo completarse*\n"
            f"Por favor, reserva manualmente:\n\n"
            f"📅 Fechas: {', '.join(date_strings)}\n\n"
            f"📋 *Tus datos registrados:*\n"
            f"• Nombre: {fill_data['name']}\n"
            f"• Documento: {fill_data['document']}\n"
            f"• Email: {fill_data['email']}\n"
            f"• Teléfono: {fill_data['phone']}\n\n"
            f"⚡ *ACTÚA RÁPIDO - Las citas se agotan en segundos*\n\n"
            f"🔗 Link: https://citaprevia.ciencia.gob.es/qmaticwebbooking/#/"
        )
        
        keyboard = [[InlineKeyboardButton("🔗 IR AL SITIO WEB", url="https://citaprevia.ciencia.gob.es/qmaticwebbooking/#/")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(
            manual_message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        # Notificar al admin sobre notificación manual
        admin_notification = (
            f"📱 *NOTIFICACIÓN MANUAL ENVIADA*\n\n"
            f"👤 Usuario: {fill_data['name']} (ID: {user_id})\n"
            f"📅 Fechas: {', '.join(date_strings)}\n"
            f"⚠️ Auto-llenado no disponible"
        )
        await context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=admin_notification,
            parse_mode='Markdown'
        )
        
        logger.info(f"📱 Notificación manual enviada a usuario {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error crítico en cita_disponible_handler: {e}", exc_info=True)
        try:
            await query.answer()
            await query.edit_message_text(
                f"❌ Error procesando la cita: {str(e)}\n"
                f"Por favor contacta al administrador."
            )
        except:
            pass


# ============================================================================
# NOTAS IMPORTANTES:
# ============================================================================

"""
1. El sistema intenta PRIMERO el auto-llenado automático
2. Si falla, envía notificación manual como RESPALDO
3. Siempre notifica al admin sobre el resultado
4. Captura screenshots del proceso (guardados localmente)
5. Funciona en modo headless (sin ventana de navegador visible)

VENTAJAS:
✅ Funciona 24/7 incluso cuando duermes
✅ Respuesta inmediata (segundos)
✅ No pierdes citas disponibles
✅ Respaldo manual si algo falla
✅ Screenshots como evidencia
✅ Notificaciones a admin

DESPLIEGUE EN RENDER:
- Render soporta navegadores headless
- Las dependencias se instalan automáticamente
- No requiere configuración adicional
"""
