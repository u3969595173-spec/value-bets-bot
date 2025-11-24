"""
Bot Vida Nueva - Trabajo y Vivienda para inmigrantes
MVP - Versión inicial
"""
import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from web_server import run_in_background
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
    ConversationHandler
)
from database import (
    init_database, get_or_create_user, save_search, get_user_searches, 
    save_jobs, search_jobs_db, save_housing, search_housing_db, get_all_searches,
    activate_user, deactivate_user, get_all_users, get_user_stats,
    toggle_search_status, delete_user_searches
)
from scrapers.job_scraper import search_jobs
from scrapers.housing_scraper import search_housing
import json
from datetime import datetime, timedelta

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '5901833301'))  # Tu Telegram ID

# Estados para conversaciones
(TRABAJO_CIUDAD, TRABAJO_SALARIO, TRABAJO_CONTRATO, TRABAJO_EXPERIENCIA,
 VIVIENDA_CIUDAD, VIVIENDA_PRECIO, VIVIENDA_HABITACIONES, VIVIENDA_M2) = range(8)


class VidaNuevaBot:
    def __init__(self):
        self.app = None
        self.last_alert_check = {}  # {search_id: last_check_time}
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        user = update.effective_user
        
        # Registrar usuario en base de datos
        get_or_create_user(user.id, user.username, user.first_name)
        
        # Teclado personalizado
        keyboard = [
            [KeyboardButton("💼 Buscar Trabajo"), KeyboardButton("🏠 Buscar Vivienda")],
            [KeyboardButton("⚙️ Mis Búsquedas"), KeyboardButton("💳 Pago")],
            [KeyboardButton("ℹ️ Ayuda")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        welcome_msg = (
            f"¡Hola {user.first_name}! 👋\n\n"
            "Soy el Bot **Vida Nueva** 🚀\n\n"
            "Te ayudo a encontrar:\n"
            "💼 **Trabajo** - 18 portales de empleo\n"
            "🏠 **Vivienda** - 15 portales inmobiliarios\n\n"
            "Todo en tiempo real.\n\n"
            "💎 **UN SOLO PAGO: 10€/mes**\n"
            "Acceso completo a trabajo Y vivienda\n\n"
            "⚠️ **IMPORTANTE:**\n"
            "Debes PAGAR antes de ser activado.\n"
            "Sin pago no podrás usar el bot.\n\n"
            "📞 **Escribe al WhatsApp para PAGAR:**\n"
            "+34 936 07 56 41\n\n"
            f"🆔 Tu ID: `{user.id}`\n"
            "Proporciona este ID al escribir.\n\n"
            "Selecciona una opción:"
        )
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def buscar_trabajo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Iniciar búsqueda de trabajo - paso a paso"""
        user_id = update.effective_user.id
        
        # Verificar si el usuario es premium
        user_data = get_or_create_user(user_id, update.effective_user.username, update.effective_user.first_name)
        
        if not user_data.get('is_premium', False):
            await update.message.reply_text(
                "🔒 **PAGO REQUERIDO**\n\n"
                "⚠️ Debes PAGAR primero para usar el bot.\n\n"
                "💎 **UN SOLO PAGO: 10€/mes**\n"
                "Acceso completo a trabajo Y vivienda\n\n"
                "📞 **Escribe al WhatsApp para PAGAR:**\n"
                "+34 936 07 56 41\n\n"
                f"🆔 **Tu ID:** `{user_id}`\n"
                "Envía este ID cuando escribas.\n\n"
                "✅ Serás activado manualmente tras verificar tu pago.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Iniciar conversación
        context.user_data['search_type'] = 'trabajo'
        context.user_data['search_data'] = {}
        
        msg = (
            "💼 **BÚSQUEDA DE TRABAJO**\n\n"
            "Voy a hacerte unas preguntas para buscar el trabajo perfecto.\n\n"
            "**Pregunta 1 de 4:**\n"
            "¿Qué puesto de trabajo buscas?\n\n"
            "Ejemplos: camarero, limpieza, construcción, cocinero, etc."
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        return TRABAJO_CIUDAD
    
    async def trabajo_ciudad(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Guardar puesto y preguntar ciudad"""
        context.user_data['search_data']['puesto'] = update.message.text
        
        msg = (
            "📍 **Pregunta 2 de 4:**\n"
            "¿En qué ciudad?\n\n"
            "Ejemplos: Madrid, Barcelona, Valencia, o escribe 'España' para buscar en todo el país."
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        return TRABAJO_SALARIO
    
    async def trabajo_salario(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Guardar ciudad y preguntar salario"""
        context.user_data['search_data']['ciudad'] = update.message.text
        
        msg = (
            "💰 **Pregunta 3 de 4:**\n"
            "¿Salario mínimo que aceptas? (en €/mes)\n\n"
            "Escribe solo el número o 'cualquiera' si no importa.\n"
            "Ejemplos: 1200, 1500, cualquiera"
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        return TRABAJO_CONTRATO
    
    async def trabajo_contrato(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Guardar salario y preguntar tipo de contrato"""
        salario_text = update.message.text.lower()
        if salario_text != 'cualquiera':
            try:
                context.user_data['search_data']['salario'] = int(salario_text)
            except:
                pass
        
        msg = (
            "📋 **Pregunta 4 de 4:**\n"
            "¿Qué tipo de contrato prefieres?\n\n"
            "Escribe 'cualquiera' si no importa.\n"
            "Ejemplos: indefinido, temporal, media jornada, cualquiera"
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        return TRABAJO_EXPERIENCIA
    
    async def trabajo_experiencia(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Guardar contrato y realizar búsqueda"""
        contrato_text = update.message.text.lower()
        if contrato_text != 'cualquiera':
            context.user_data['search_data']['contrato'] = contrato_text
        
        # Construir query
        search_data = context.user_data['search_data']
        query = f"trabajo: {search_data['puesto']}, {search_data['ciudad']}"
        
        if 'salario' in search_data:
            query += f", salario: {search_data['salario']}"
        if 'contrato' in search_data:
            query += f", contrato: {search_data['contrato']}"
        
        # Realizar búsqueda
        await self.process_job_search(update, context, query)
        
        return ConversationHandler.END
    
    async def buscar_vivienda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Iniciar búsqueda de vivienda - paso a paso"""
        user_id = update.effective_user.id
        
        # Verificar si el usuario es premium
        user_data = get_or_create_user(user_id, update.effective_user.username, update.effective_user.first_name)
        
        if not user_data.get('is_premium', False):
            await update.message.reply_text(
                "🔒 **PAGO REQUERIDO**\n\n"
                "⚠️ Debes PAGAR primero para usar el bot.\n\n"
                "💎 **Precio: 10€/mes**\n\n"
                "📞 **Escribe al WhatsApp para PAGAR:**\n"
                "+34 936 07 56 41\n\n"
                f"🆔 **Tu ID:** `{user_id}`\n"
                "Envía este ID cuando escribas.\n\n"
                "✅ Serás activado inmediatamente tras confirmar el pago.",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Iniciar conversación
        context.user_data['search_type'] = 'vivienda'
        context.user_data['search_data'] = {}
        
        msg = (
            "🏠 **BÚSQUEDA DE VIVIENDA**\n\n"
            "Voy a hacerte unas preguntas para encontrar tu vivienda ideal.\n\n"
            "**Pregunta 1 de 4:**\n"
            "¿Qué tipo de vivienda buscas?\n\n"
            "Ejemplos: habitacion, piso, estudio, apartamento, etc."
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        return VIVIENDA_CIUDAD
    
    async def vivienda_ciudad(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Guardar tipo y preguntar ciudad"""
        context.user_data['search_data']['tipo'] = update.message.text
        
        msg = (
            "📍 **Pregunta 2 de 4:**\n"
            "¿En qué ciudad?\n\n"
            "Ejemplos: Madrid, Barcelona, Valencia, Sevilla, etc."
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        return VIVIENDA_PRECIO
    
    async def vivienda_precio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Guardar ciudad y preguntar precio"""
        context.user_data['search_data']['ciudad'] = update.message.text
        
        msg = (
            "💰 **Pregunta 3 de 4:**\n"
            "¿Cuánto puedes pagar al mes? (en €)\n\n"
            "Puedes escribir:\n"
            "• Un rango: 300-500\n"
            "• Un máximo: 600\n"
            "• 'cualquiera' si no importa"
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        return VIVIENDA_HABITACIONES
    
    async def vivienda_habitaciones(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Guardar precio y preguntar habitaciones"""
        precio_text = update.message.text.lower()
        if precio_text != 'cualquiera':
            if '-' in precio_text:
                try:
                    precios = precio_text.split('-')
                    context.user_data['search_data']['precio_min'] = int(precios[0])
                    context.user_data['search_data']['precio_max'] = int(precios[1])
                except:
                    pass
            else:
                try:
                    context.user_data['search_data']['precio_max'] = int(precio_text)
                except:
                    pass
        
        msg = (
            "🛏️ **Pregunta 4 de 4:**\n"
            "¿Cuántas habitaciones necesitas?\n\n"
            "Escribe el número o 'cualquiera' si no importa.\n"
            "Ejemplos: 1, 2, 3, cualquiera"
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
        return VIVIENDA_M2
    
    async def vivienda_m2(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Guardar habitaciones y realizar búsqueda"""
        habitaciones_text = update.message.text.lower()
        if habitaciones_text != 'cualquiera':
            try:
                context.user_data['search_data']['habitaciones'] = int(habitaciones_text)
            except:
                pass
        
        # Construir query
        search_data = context.user_data['search_data']
        query = f"vivienda: {search_data['tipo']}, {search_data['ciudad']}"
        
        if 'precio_min' in search_data and 'precio_max' in search_data:
            query += f", precio: {search_data['precio_min']}-{search_data['precio_max']}"
        elif 'precio_max' in search_data:
            query += f", precio: 0-{search_data['precio_max']}"
        
        if 'habitaciones' in search_data:
            query += f", habitaciones: {search_data['habitaciones']}"
        
        # Realizar búsqueda
        await self.process_housing_search(update, context, query)
        
        return ConversationHandler.END
    
    async def cancelar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancelar conversación"""
        await update.message.reply_text(
            "❌ Búsqueda cancelada.\n\n"
            "Usa los botones del menú para empezar de nuevo."
        )
        return ConversationHandler.END
    
    async def mis_busquedas(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando para ver búsquedas guardadas con botones para gestionar alertas"""
        user_id = update.effective_user.id
        
        # Obtener búsquedas de la base de datos
        searches = get_user_searches(user_id)
        
        if searches:
            msg = "⚙️ **TUS BÚSQUEDAS:**\n\n"
            
            keyboard = []
            for i, search in enumerate(searches, 1):
                tipo = "💼 Trabajo" if search['search_type'] == 'trabajo' else "🏠 Vivienda"
                status = "🔔 ON" if search['is_active'] else "🔕 OFF"
                msg += f"{i}. {tipo}: {search['keywords']}\n"
                if search['location']:
                    msg += f"   📍 {search['location']}\n"
                msg += f"   Alertas: {status}\n\n"
                
                # Botones para cada búsqueda
                if search['is_active']:
                    keyboard.append([InlineKeyboardButton(
                        f"🔕 Desactivar #{i}",
                        callback_data=f"toggle_search_{search['id']}_off"
                    )])
                else:
                    keyboard.append([InlineKeyboardButton(
                        f"🔔 Activar #{i}",
                        callback_data=f"toggle_search_{search['id']}_on"
                    )])
            
            # Botón para eliminar todas
            keyboard.append([InlineKeyboardButton(
                "🗑️ Eliminar todas",
                callback_data="delete_all_searches"
            )])
            
            msg += f"\n📊 Total: {len(searches)} búsquedas\n"
            msg += "\n💡 **Alertas automáticas:**\n"
            msg += "🔔 ON = Revisa cada hora y te avisa\n"
            msg += "🔕 OFF = No busca automáticamente"
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            msg = (
                "⚙️ **MIS BÚSQUEDAS**\n\n"
                "Aún no tienes búsquedas guardadas.\n\n"
                "📋 **Para empezar:**\n"
                "1. Usa '💼 Buscar Trabajo' o '🏠 Buscar Vivienda'\n"
                "2. Guarda tus búsquedas\n"
                "3. Activa alertas automáticas (cada hora)\n\n"
                "💎 **UN SOLO PAGO: 10€/mes**\n"
                "Acceso a trabajo Y vivienda\n\n"
                "📞 **Escribe al WhatsApp:** +34 936 07 56 41\n\n"
                "💡 Usa '💳 Pago' para más información."
            )
            await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def pago(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /pago - Información de pago"""
        user_id = update.effective_user.id
        
        msg = (
            "💳 **INFORMACIÓN DE PAGO**\n\n"
            "⚠️ **IMPORTANTE:**\n"
            "Debes PAGAR antes de usar el bot.\n"
            "Sin pago confirmado, no podrás buscar.\n\n"
            "💎 **Precio: 10€/mes**\n\n"
            "📞 **Escribe al WhatsApp para PAGAR:**\n"
            "+34 936 07 56 41\n\n"
            f"🆔 **Tu ID:** `{user_id}`\n"
            "⚠️ Proporciona este ID al escribir\n\n"
            "📋 **Proceso:**\n"
            "1. Escribe al WhatsApp\n"
            "2. Envía tu ID de usuario\n"
            "3. Te diremos cómo pagar\n"
            "4. Confirmas el pago\n"
            "5. Eres activado inmediatamente\n\n"
            "🔄 **Renovación:**\n"
            "Mensual - Te avisaremos por WhatsApp."
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        msg = (
            "ℹ️ **CÓMO FUNCIONA**\n\n"
            "⚠️ **PASO 1: PAGAR**\n"
            "Escribe al WhatsApp: +34 936 07 56 41\n"
            "Paga 10€/mes - UN SOLO PAGO para TODO\n\n"
            "✅ **PASO 2: ACTIVACIÓN MANUAL**\n"
            "Verificamos tu pago y te activamos\n\n"
            "🔍 **PASO 3: USAR EL BOT**\n"
            "1️⃣ Busca trabajo o vivienda (sin límite)\n"
            "2️⃣ Responde las preguntas\n"
            "3️⃣ Recibe TODAS las ofertas encontradas\n"
            "4️⃣ Activa alertas automáticas (cada hora)\n\n"
            "💎 **UN SOLO PAGO: 10€/mes**\n"
            "• Trabajo: 18 portales\n"
            "• Vivienda: 15 portales\n"
            "• Alertas automáticas\n"
            "• Búsquedas ilimitadas\n\n"
            "📞 **WhatsApp para PAGAR:**\n"
            "+34 936 07 56 41\n\n"
            "**Comandos:**\n"
            "/start - Menú principal\n"
            "/help - Esta ayuda\n"
            "/pago - Info de pago"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def pago(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /pago - Información de pago"""
        user_id = update.effective_user.id
        
        msg = (
            "💳 **INFORMACIÓN DE PAGO**\n\n"
            "⚠️ **IMPORTANTE:**\n"
            "Debes PAGAR antes de usar el bot.\n"
            "Sin pago confirmado, no podrás buscar.\n\n"
            "💎 **Precio: 10€/mes**\n\n"
            "📞 **Escribe al WhatsApp para PAGAR:**\n"
            "+34 936 07 56 41\n\n"
            f"🆔 **Tu ID:** `{user_id}`\n"
            "⚠️ Proporciona este ID al escribir\n\n"
            "📋 **Proceso:**\n"
            "1. Escribe al WhatsApp\n"
            "2. Envía tu ID de usuario\n"
            "3. Te diremos cómo pagar\n"
            "4. Confirmas el pago\n"
            "5. Eres activado inmediatamente\n\n"
            "🔄 **Renovación:**\n"
            "Mensual - Te avisaremos por WhatsApp."
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Procesar mensajes de texto"""
        text = update.message.text.lower()
        user_id = update.effective_user.id
        
        if "💼" in text or "trabajo" in text:
            await self.buscar_trabajo(update, context)
        elif "🏠" in text or "vivienda" in text:
            await self.buscar_vivienda(update, context)
        elif "⚙️" in text or "búsquedas" in text:
            await self.mis_busquedas(update, context)
        elif "💳" in text or "pago" in text:
            await self.pago(update, context)
        elif "ℹ️" in text or "ayuda" in text:
            await self.ayuda(update, context)
        else:
            # Procesar búsqueda de trabajo
            if text.startswith("trabajo:"):
                await self.process_job_search(update, context, text)
            elif text.startswith("vivienda:"):
                await self.process_housing_search(update, context, text)
            else:
                await update.message.reply_text(
                    "No entiendo ese comando. Usa /help para ver los comandos disponibles."
                )
    
    async def admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Panel de administración (solo para admin)"""
        user_id = update.effective_user.id
        
        if ADMIN_ID == 0 or user_id != ADMIN_ID:
            await update.message.reply_text("❌ No tienes permisos de administrador.")
            return
        
        # Obtener estadísticas
        stats = get_user_stats()
        
        msg = (
            "🔐 **PANEL DE ADMINISTRACIÓN**\n\n"
            f"👥 Total usuarios: {stats.get('total_users', 0)}\n"
            f"💎 Premium: {stats.get('premium_users', 0)}\n"
            f"🆓 Gratis: {stats.get('free_users', 0)}\n\n"
            "**Comandos disponibles:**\n"
            "/usuarios - Ver lista de usuarios\n"
            "/activar [user_id] - Activar usuario\n"
            "/desactivar [user_id] - Desactivar usuario\n"
            "/stats - Estadísticas detalladas"
        )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def usuarios(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ver lista de usuarios con botones para activar/desactivar"""
        user_id = update.effective_user.id
        
        if ADMIN_ID == 0 or user_id != ADMIN_ID:
            await update.message.reply_text("❌ No tienes permisos de administrador.")
            return
        
        users = get_all_users()
        
        if not users:
            await update.message.reply_text("No hay usuarios registrados.")
            return
        
        # Enviar usuarios en grupos de 5
        for i in range(0, len(users), 5):
            batch = users[i:i+5]
            
            for user in batch:
                status = "✅ Premium" if user['is_premium'] else "❌ Inactivo"
                username = f"@{user['username']}" if user['username'] else "Sin username"
                
                msg = (
                    f"**{user['first_name']}** {status}\n"
                    f"ID: `{user['user_id']}`\n"
                    f"Usuario: {username}\n"
                    f"Registro: {user['created_at'].strftime('%d/%m/%Y')}"
                )
                
                # Botones para activar/desactivar
                keyboard = []
                if user['is_premium']:
                    keyboard.append([InlineKeyboardButton("❌ Desactivar", callback_data=f"deactivate_{user['user_id']}")])
                else:
                    keyboard.append([InlineKeyboardButton("✅ Activar Premium", callback_data=f"activate_{user['user_id']}")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejar botones de activar/desactivar usuarios y búsquedas"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        # Manejar activar/desactivar búsquedas (cualquier usuario)
        if data.startswith("toggle_search_"):
            parts = data.split("_")
            search_id = int(parts[2])
            action = parts[3]  # 'on' o 'off'
            
            if action == "on":
                if toggle_search_status(search_id, True):
                    await query.answer("✅ Alertas activadas")
                    # Refrescar la vista
                    searches = get_user_searches(user_id)
                    
                    if searches:
                        msg = "⚙️ **TUS BÚSQUEDAS:**\n\n"
                        keyboard = []
                        
                        for i, search in enumerate(searches, 1):
                            tipo = "💼 Trabajo" if search['search_type'] == 'trabajo' else "🏠 Vivienda"
                            status = "🔔 ON" if search['is_active'] else "🔕 OFF"
                            msg += f"{i}. {tipo}: {search['keywords']}\n"
                            if search['location']:
                                msg += f"   📍 {search['location']}\n"
                            msg += f"   Alertas: {status}\n\n"
                            
                            if search['is_active']:
                                keyboard.append([InlineKeyboardButton(
                                    f"🔕 Desactivar #{i}",
                                    callback_data=f"toggle_search_{search['id']}_off"
                                )])
                            else:
                                keyboard.append([InlineKeyboardButton(
                                    f"🔔 Activar #{i}",
                                    callback_data=f"toggle_search_{search['id']}_on"
                                )])
                        
                        keyboard.append([InlineKeyboardButton(
                            "🗑️ Eliminar todas",
                            callback_data="delete_all_searches"
                        )])
                        
                        msg += f"\n📊 Total: {len(searches)} búsquedas\n"
                        msg += "\n💡 **Alertas automáticas:**\n"
                        msg += "🔔 ON = Revisa cada hora y te avisa\n"
                        msg += "🔕 OFF = No busca automáticamente"
                        
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
                else:
                    await query.answer("❌ Error al activar", show_alert=True)
            else:
                if toggle_search_status(search_id, False):
                    await query.answer("🔕 Alertas desactivadas")
                    # Refrescar la vista
                    searches = get_user_searches(user_id)
                    
                    if searches:
                        msg = "⚙️ **TUS BÚSQUEDAS:**\n\n"
                        keyboard = []
                        
                        for i, search in enumerate(searches, 1):
                            tipo = "💼 Trabajo" if search['search_type'] == 'trabajo' else "🏠 Vivienda"
                            status = "🔔 ON" if search['is_active'] else "🔕 OFF"
                            msg += f"{i}. {tipo}: {search['keywords']}\n"
                            if search['location']:
                                msg += f"   📍 {search['location']}\n"
                            msg += f"   Alertas: {status}\n\n"
                            
                            if search['is_active']:
                                keyboard.append([InlineKeyboardButton(
                                    f"🔕 Desactivar #{i}",
                                    callback_data=f"toggle_search_{search['id']}_off"
                                )])
                            else:
                                keyboard.append([InlineKeyboardButton(
                                    f"🔔 Activar #{i}",
                                    callback_data=f"toggle_search_{search['id']}_on"
                                )])
                        
                        keyboard.append([InlineKeyboardButton(
                            "🗑️ Eliminar todas",
                            callback_data="delete_all_searches"
                        )])
                        
                        msg += f"\n📊 Total: {len(searches)} búsquedas\n"
                        msg += "\n💡 **Alertas automáticas:**\n"
                        msg += "🔔 ON = Revisa cada hora y te avisa\n"
                        msg += "🔕 OFF = No busca automáticamente"
                        
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
                else:
                    await query.answer("❌ Error al desactivar", show_alert=True)
            return
        
        # Eliminar todas las búsquedas
        if data == "delete_all_searches":
            if delete_user_searches(user_id):
                await query.edit_message_text(
                    "🗑️ **Todas las búsquedas eliminadas**\n\n"
                    "Usa los botones del menú para crear nuevas búsquedas."
                )
            else:
                await query.answer("❌ Error al eliminar", show_alert=True)
            return
        
        # COMANDOS DE ADMIN
        if ADMIN_ID == 0 or user_id != ADMIN_ID:
            await query.edit_message_text("❌ No tienes permisos de administrador.")
            return
        
        if data.startswith("activate_"):
            target_user_id = int(data.split("_")[1])
            
            if activate_user(target_user_id):
                # Notificar al usuario
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=(
                            "🎉 **¡CUENTA ACTIVADA!**\n\n"
                            "Tu suscripción Premium ha sido activada.\n"
                            "Ya puedes usar todas las funciones del bot.\n\n"
                            "💼 Busca trabajos en 18 portales\n"
                            "🏠 Busca viviendas en 15 portales\n"
                            "🔔 Alertas automáticas cada hora\n\n"
                            "¡Disfruta del servicio!"
                        ),
                        parse_mode='Markdown'
                    )
                except:
                    pass
                
                await query.edit_message_text(
                    f"{query.message.text}\n\n✅ **Usuario activado correctamente**"
                )
            else:
                await query.edit_message_text(
                    f"{query.message.text}\n\n❌ **Error al activar usuario**"
                )
        
        elif data.startswith("deactivate_"):
            target_user_id = int(data.split("_")[1])
            
            if deactivate_user(target_user_id):
                # Notificar al usuario
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=(
                            "⚠️ **SUSCRIPCIÓN CANCELADA**\n\n"
                            "Tu suscripción Premium ha sido desactivada.\n\n"
                            "Para reactivarla, contacta:\n"
                            "📞 +34 936 07 56 41 (WhatsApp)"
                        ),
                        parse_mode='Markdown'
                    )
                except:
                    pass
                
                await query.edit_message_text(
                    f"{query.message.text}\n\n✅ **Usuario desactivado correctamente**"
                )
            else:
                await query.edit_message_text(
                    f"{query.message.text}\n\n❌ **Error al desactivar usuario**"
                )
    
    async def process_job_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """Procesar búsqueda de trabajo"""
        user_id = update.effective_user.id
        
        # Verificar si el usuario es premium
        user_data = get_or_create_user(user_id, update.effective_user.username, update.effective_user.first_name)
        
        if not user_data.get('is_premium', False):
            await update.message.reply_text(
                "🔒 **PAGO REQUERIDO**\n\n"
                "⚠️ Debes PAGAR primero para usar el bot.\n\n"
                "💎 **Precio: 10€/mes**\n\n"
                "📞 **Escribe al WhatsApp para PAGAR:**\n"
                "+34 936 07 56 41\n\n"
                f"🆔 **Tu ID:** `{user_id}`\n"
                "Envía este ID cuando escribas.\n\n"
                "✅ Serás activado inmediatamente tras confirmar el pago.",
                parse_mode='Markdown'
            )
            return
        
        try:
            # Parsear query: "trabajo: camarero, Madrid, salario: 1200, contrato: indefinido, experiencia: 2"
            query_clean = query.replace("trabajo:", "").strip()
            
            # Separar por comas
            parts = [p.strip() for p in query_clean.split(",")]
            
            if len(parts) < 1:
                await update.message.reply_text("❌ Formato incorrecto. Ejemplo: `trabajo: camarero, Madrid`", parse_mode='Markdown')
                return
            
            # Extraer parámetros
            keywords = parts[0]
            location = "España"
            min_salary = None
            contract_type = None
            experience = None
            
            for part in parts[1:]:
                part_lower = part.lower()
                if "salario:" in part_lower:
                    try:
                        min_salary = int(part_lower.split("salario:")[1].strip())
                    except:
                        pass
                elif "contrato:" in part_lower:
                    contract_type = part_lower.split("contrato:")[1].strip()
                elif "experiencia:" in part_lower:
                    try:
                        experience = int(part_lower.split("experiencia:")[1].strip())
                    except:
                        pass
                elif not any(x in part_lower for x in ["salario:", "contrato:", "experiencia:"]):
                    # Si no tiene palabra clave, es la ubicación
                    location = part
            
            # Construir mensaje de búsqueda
            search_details = f"💼 Puesto: {keywords}\n📍 Ubicación: {location}"
            if min_salary:
                search_details += f"\n💰 Salario mínimo: {min_salary}€/mes"
            if contract_type:
                search_details += f"\n📋 Contrato: {contract_type}"
            if experience is not None:
                if experience == 0:
                    search_details += f"\n🎓 Sin experiencia requerida"
                else:
                    search_details += f"\n📊 Experiencia: {experience} años"
            
            # Mensaje de inicio
            status_msg = await update.message.reply_text(
                f"🔍 **BUSCANDO TRABAJO**\n\n"
                f"{search_details}\n\n"
                f"⏳ Escaneando 18 portales de empleo...",
                parse_mode='Markdown'
            )
            
            # Ejecutar scraping
            logger.info(f"Buscando trabajos: {keywords} en {location}")
            result = search_jobs(keywords, location, max_results=50)
            
            # El scraper ahora devuelve un dict con exact_matches y location_only
            exact_jobs = result.get('exact_matches', []) if isinstance(result, dict) else result
            location_jobs = result.get('location_only', []) if isinstance(result, dict) else []
            
            # Aplicar filtros adicionales si hay (salario, contrato, experiencia) solo a exact_jobs
            if (min_salary or contract_type or experience is not None) and exact_jobs:
                filtered_jobs = []
                for job in exact_jobs:
                    # Filtrar por salario
                    if min_salary and job.get('salary'):
                        try:
                            # Extraer número del salario (ej: "1.500€" -> 1500)
                            salary_str = job['salary'].replace('€', '').replace('.', '').replace(',', '').strip()
                            salary_num = int(''.join(filter(str.isdigit, salary_str)))
                            if salary_num < min_salary:
                                continue
                        except:
                            pass
                    
                    # Filtrar por tipo de contrato
                    if contract_type:
                        job_text = (job.get('title', '') + ' ' + job.get('description', '')).lower()
                        if contract_type not in job_text:
                            continue
                    
                    # Filtrar por experiencia
                    if experience is not None:
                        job_text = (job.get('title', '') + ' ' + job.get('description', '')).lower()
                        if experience == 0:
                            # Buscar trabajos sin experiencia
                            if not any(word in job_text for word in ['sin experiencia', 'no experiencia', 'primer empleo']):
                                if any(word in job_text for word in ['experiencia requerida', 'años de experiencia']):
                                    continue
                    
                    filtered_jobs.append(job)
                
                exact_jobs = filtered_jobs
                logger.info(f"Después de filtrar: {len(exact_jobs)} trabajos exactos")
            
            # Guardar en base de datos
            all_jobs_to_save = exact_jobs + location_jobs
            if all_jobs_to_save:
                saved_count = save_jobs(all_jobs_to_save)
                logger.info(f"Guardados {saved_count} trabajos nuevos")
            
            # Guardar búsqueda
            try:
                search_id = save_search(user_id, 'trabajo', keywords, location, None)
                logger.info(f"Búsqueda guardada con ID: {search_id}")
            except Exception as e:
                logger.error(f"Error guardando búsqueda: {e}")
            
            # Actualizar mensaje con resultados
            if not exact_jobs and not location_jobs:
                await status_msg.edit_text(
                    f"❌ **NO SE ENCONTRARON RESULTADOS**\n\n"
                    f"💼 Puesto: {keywords}\n"
                    f"📍 Ubicación: {location}\n\n"
                    f"💡 **Sugerencias:**\n"
                    f"• Prueba con sinónimos (ej: 'mesero' en vez de 'camarero')\n"
                    f"• Amplía la ubicación (ej: 'España' en vez de ciudad)\n"
                    f"• Reduce los filtros\n\n"
                    f"✅ Búsqueda guardada.\n"
                    f"🔔 Usa '⚙️ Mis Búsquedas' para activar alertas automáticas.",
                    parse_mode='Markdown'
                )
                return
            
            # Si hay trabajos exactos, mostrarlos primero
            if exact_jobs:
                result_msg = (
                    f"✅ **ENCONTRADOS {len(exact_jobs)} TRABAJOS DE {keywords.upper()}**\n\n"
                    f"💼 {keywords}\n"
                    f"📍 {location}\n\n"
                    f"📋 Enviando todos los resultados:\n"
                )
                await status_msg.edit_text(result_msg, parse_mode='Markdown')
                
                # Enviar cada trabajo como mensaje separado
                for i, job in enumerate(exact_jobs, 1):
                    job_msg = (
                        f"**{i}. {job['title']}**\n"
                        f"🏢 {job['company']}\n"
                        f"📍 {job['location']}\n"
                    )
                    
                    if job.get('salary'):
                        job_msg += f"💰 {job['salary']}\n"
                    
                    if job.get('special_tags'):
                        tags_emoji = {
                            'sin_papeles': '🔓',
                            'sin_experiencia': '🎓',
                            'urgente': '⚡',
                            'hosteleria': '🍽️'
                        }
                        tags_str = ' '.join([f"{tags_emoji.get(t, '🏷️')} {t.replace('_', ' ').title()}" for t in job['special_tags']])
                        job_msg += f"{tags_str}\n"
                    
                    job_msg += f"\n🔗 [Ver oferta]({job['url']})\n"
                    job_msg += f"📡 Fuente: {job['source']}"
                    
                    await update.message.reply_text(job_msg, parse_mode='Markdown', disable_web_page_preview=True)
                
                # Mensaje final
                await update.message.reply_text(
                    f"📊 **TOTAL: {len(exact_jobs)} ofertas de {keywords} enviadas**\n\n"
                    f"✅ Búsqueda guardada correctamente.\n\n"
                    f"🔔 **ACTIVAR ALERTAS:**\n"
                    f"Usa '⚙️ Mis Búsquedas' para activar las alertas automáticas.\n"
                    f"Te avisaré cada hora si encuentro nuevas ofertas.\n\n"
                    f"💡 Tip: Las alertas están desactivadas por defecto para que tú decidas cuándo activarlas.",
                    parse_mode='Markdown'
                )
            
            # Si NO hay trabajos exactos PERO SÍ hay en la ubicación, mostrar mensaje alternativo
            elif not exact_jobs and location_jobs:
                no_exact_msg = (
                    f"❌ **NO ENCONTRÉ TRABAJOS DE {keywords.upper()} EN {location.upper()}**\n\n"
                    f"Pero encontré **{len(location_jobs)} trabajos disponibles en {location}**:\n"
                )
                await status_msg.edit_text(no_exact_msg, parse_mode='Markdown')
                
                # Enviar trabajos alternativos
                for i, job in enumerate(location_jobs, 1):
                    job_msg = (
                        f"**{i}. {job['title']}**\n"
                        f"🏢 {job['company']}\n"
                        f"📍 {job['location']}\n"
                    )
                    
                    if job.get('salary'):
                        job_msg += f"💰 {job['salary']}\n"
                    
                    if job.get('special_tags'):
                        tags_emoji = {
                            'sin_papeles': '🔓',
                            'sin_experiencia': '🎓',
                            'urgente': '⚡',
                            'hosteleria': '🍽️'
                        }
                        tags_str = ' '.join([f"{tags_emoji.get(t, '🏷️')} {t.replace('_', ' ').title()}" for t in job['special_tags']])
                        job_msg += f"{tags_str}\n"
                    
                    job_msg += f"\n🔗 [Ver oferta]({job['url']})\n"
                    job_msg += f"📡 Fuente: {job['source']}"
                    
                    await update.message.reply_text(job_msg, parse_mode='Markdown', disable_web_page_preview=True)
                
                # Mensaje final explicativo
                await update.message.reply_text(
                    f"📊 **{len(location_jobs)} trabajos alternativos en {location}**\n\n"
                    f"💡 No encontré trabajos específicos de **{keywords}**, pero estos están en tu ubicación y podrían interesarte.\n\n"
                    f"✅ Búsqueda guardada.\n"
                    f"🔔 Usa '⚙️ Mis Búsquedas' para activar alertas.",
                    parse_mode='Markdown'
                )
            
        except Exception as e:
            logger.error(f"Error procesando búsqueda: {e}")
            await update.message.reply_text(
                f"❌ Error al buscar trabajos: {str(e)}\n\n"
                f"Intenta de nuevo o contacta con soporte."
            )
    
    async def process_housing_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """Procesar búsqueda de vivienda"""
        user_id = update.effective_user.id
        
        # Verificar si el usuario es premium
        user_data = get_or_create_user(user_id, update.effective_user.username, update.effective_user.first_name)
        
        if not user_data.get('is_premium', False):
            await update.message.reply_text(
                "🔒 **PAGO REQUERIDO**\n\n"
                "⚠️ Debes PAGAR primero para usar el bot.\n\n"
                "💎 **Precio: 10€/mes**\n\n"
                "📞 **Escribe al WhatsApp para PAGAR:**\n"
                "+34 936 07 56 41\n\n"
                f"🆔 **Tu ID:** `{user_id}`\n"
                "Envía este ID cuando escribas.\n\n"
                "✅ Serás activado inmediatamente tras confirmar el pago.",
                parse_mode='Markdown'
            )
            return
        
        try:
            # Parsear query: "vivienda: habitacion, Madrid, precio: 300-500, habitaciones: 1, m2: 20"
            query_clean = query.replace("vivienda:", "").strip()
            
            # Separar por comas
            parts = [p.strip() for p in query_clean.split(",")]
            
            if len(parts) < 1:
                await update.message.reply_text("❌ Formato incorrecto. Ejemplo: `vivienda: habitacion, Madrid`", parse_mode='Markdown')
                return
            
            # Extraer parámetros
            keywords = parts[0]
            location = "madrid"
            min_price = None
            max_price = None
            bedrooms = None
            min_m2 = None
            bathrooms = None
            
            for part in parts[1:]:
                part_lower = part.lower()
                if "precio:" in part_lower:
                    try:
                        price_range = part_lower.split("precio:")[1].strip()
                        if "-" in price_range:
                            prices = price_range.split("-")
                            min_price = int(prices[0].strip())
                            max_price = int(prices[1].strip())
                        else:
                            max_price = int(price_range)
                    except:
                        pass
                elif "habitaciones:" in part_lower or "habitacion:" in part_lower:
                    try:
                        bedrooms = int(part_lower.split(":")[1].strip())
                    except:
                        pass
                elif "m2:" in part_lower:
                    try:
                        min_m2 = int(part_lower.split("m2:")[1].strip())
                    except:
                        pass
                elif "baños:" in part_lower or "baño:" in part_lower:
                    try:
                        bathrooms = int(part_lower.split(":")[1].strip())
                    except:
                        pass
                elif not any(x in part_lower for x in ["precio:", "habitaciones:", "habitacion:", "m2:", "baños:", "baño:"]):
                    # Si no tiene palabra clave, es la ubicación
                    location = part
            
            # Construir mensaje de búsqueda
            search_details = f"🏘️ Tipo: {keywords}\n📍 Ubicación: {location}"
            if min_price and max_price:
                search_details += f"\n💰 Precio: {min_price}-{max_price}€/mes"
            elif max_price:
                search_details += f"\n💰 Precio máximo: {max_price}€/mes"
            if bedrooms:
                search_details += f"\n🛏️ Habitaciones: {bedrooms}"
            if min_m2:
                search_details += f"\n📏 Mínimo: {min_m2}m²"
            if bathrooms:
                search_details += f"\n🚿 Baños: {bathrooms}"
            
            # Mensaje de inicio
            status_msg = await update.message.reply_text(
                f"🏠 **BUSCANDO VIVIENDA**\n\n"
                f"{search_details}\n\n"
                f"⏳ Escaneando 15 portales de vivienda...",
                parse_mode='Markdown'
            )
            
            # Ejecutar scraping
            logger.info(f"Buscando viviendas: {keywords} en {location}")
            result = search_housing(keywords, location, None, max_results=40)
            
            # El scraper ahora devuelve un dict con exact_matches y location_only
            exact_listings = result.get('exact_matches', []) if isinstance(result, dict) else result
            location_listings = result.get('location_only', []) if isinstance(result, dict) else []
            
            # Aplicar filtros adicionales si hay (precio, habitaciones, etc.) solo a exact_listings
            if (min_price or max_price or bedrooms or min_m2 or bathrooms) and exact_listings:
                filtered_listings = []
                for listing in exact_listings:
                    # Filtrar por precio
                    if listing.get('price'):
                        try:
                            price = float(listing['price'])
                            if min_price and price < min_price:
                                continue
                            if max_price and price > max_price:
                                continue
                        except:
                            pass
                    
                    # Filtrar por habitaciones
                    if bedrooms and listing.get('bedrooms'):
                        try:
                            if int(listing['bedrooms']) < bedrooms:
                                continue
                        except:
                            pass
                    
                    # Filtrar por m2
                    if min_m2 and listing.get('size_m2'):
                        try:
                            if int(listing['size_m2']) < min_m2:
                                continue
                        except:
                            pass
                    
                    # Filtrar por baños
                    if bathrooms and listing.get('bathrooms'):
                        try:
                            if int(listing['bathrooms']) < bathrooms:
                                continue
                        except:
                            pass
                    
                    filtered_listings.append(listing)
                
                exact_listings = filtered_listings
                logger.info(f"Después de filtrar: {len(exact_listings)} viviendas exactas")
            
            # Guardar en base de datos
            all_listings_to_save = exact_listings + location_listings
            if all_listings_to_save:
                saved_count = save_housing(all_listings_to_save)
                logger.info(f"Guardadas {saved_count} viviendas nuevas")
            
            # Guardar búsqueda
            try:
                search_id = save_search(user_id, 'vivienda', keywords, location, None)
                logger.info(f"Búsqueda vivienda guardada con ID: {search_id}")
            except Exception as e:
                logger.error(f"Error guardando búsqueda vivienda: {e}")
            
            # Actualizar mensaje con resultados
            if not exact_listings and not location_listings:
                await status_msg.edit_text(
                    f"❌ **NO SE ENCONTRARON RESULTADOS**\n\n"
                    f"🏘️ Tipo: {keywords}\n"
                    f"📍 {location}\n\n"
                    f"💡 **Sugerencias:**\n"
                    f"• Prueba con otra ciudad\n"
                    f"• Cambia el tipo (ej: 'habitacion' en vez de 'piso')\n"
                    f"• Amplía la zona de búsqueda\n\n"
                    f"✅ Búsqueda guardada.\n"
                    f"🔔 Usa '⚙️ Mis Búsquedas' para activar alertas automáticas.",
                    parse_mode='Markdown'
                return
            
            # Si hay viviendas exactas, mostrarlas primero
            if exact_listings:
                result_msg = (
                    f"✅ **ENCONTRADAS {len(exact_listings)} VIVIENDAS DE {keywords.upper()}**\n\n"
                    f"🏘️ {keywords}\n"
                    f"📍 {location}\n\n"
                    f"📋 Enviando todos los resultados:\n"
                )
                await status_msg.edit_text(result_msg, parse_mode='Markdown')
                
                # Enviar cada vivienda como mensaje separado
                for i, listing in enumerate(exact_listings, 1):
                    housing_msg = (
                        f"**{i}. {listing['title']}**\n"
                        f"📍 {listing['location']}\n"
                    )
                    
                    if listing.get('price'):
                        housing_msg += f"💰 {listing['price']}€/mes\n"
                    
                    if listing.get('bedrooms'):
                        housing_msg += f"🛏️ {listing['bedrooms']} hab.\n"
                    
                    if listing.get('special_tags'):
                        tags_emoji = {
                            'sin_fianza': '💳',
                            'sin_nomina': '📄',
                            'acepta_extranjeros': '🌍',
                            'compartido': '👥'
                        }
                        tags_str = ' '.join([f"{tags_emoji.get(t, '🏷️')} {t.replace('_', ' ').title()}" for t in listing['special_tags']])
                        housing_msg += f"{tags_str}\n"
                    
                    housing_msg += f"\n🔗 [Ver anuncio]({listing['url']})\n"
                    housing_msg += f"📡 Fuente: {listing['source']}"
                    
                    await update.message.reply_text(housing_msg, parse_mode='Markdown', disable_web_page_preview=True)
                
                # Mensaje final
                await update.message.reply_text(
                    f"📊 **TOTAL: {len(exact_listings)} viviendas de {keywords} enviadas**\n\n"
                    f"✅ Búsqueda guardada correctamente.\n\n"
                    f"🔔 **ACTIVAR ALERTAS:**\n"
                    f"Usa '⚙️ Mis Búsquedas' para activar las alertas automáticas.\n"
                    f"Te avisaré cada hora si encuentro nuevas ofertas.\n\n"
                    f"💡 Tip: Las alertas están desactivadas por defecto para que tú decidas cuándo activarlas.",
                    parse_mode='Markdown'
                )
            
            # Si NO hay viviendas exactas PERO SÍ hay en la ubicación, mostrar mensaje alternativo
            elif not exact_listings and location_listings:
                no_exact_msg = (
                    f"❌ **NO ENCONTRÉ {keywords.upper()} EN {location.upper()}**\n\n"
                    f"Pero encontré **{len(location_listings)} viviendas disponibles en {location}**:\n"
                )
                await status_msg.edit_text(no_exact_msg, parse_mode='Markdown')
                
                # Enviar viviendas alternativas
                for i, listing in enumerate(location_listings, 1):
                    housing_msg = (
                        f"**{i}. {listing['title']}**\n"
                        f"📍 {listing['location']}\n"
                    )
                    
                    if listing.get('price'):
                        housing_msg += f"💰 {listing['price']}€/mes\n"
                    
                    if listing.get('bedrooms'):
                        housing_msg += f"🛏️ {listing['bedrooms']} hab.\n"
                    
                    if listing.get('special_tags'):
                        tags_emoji = {
                            'sin_fianza': '💳',
                            'sin_nomina': '📄',
                            'acepta_extranjeros': '🌍',
                            'compartido': '👥'
                        }
                        tags_str = ' '.join([f"{tags_emoji.get(t, '🏷️')} {t.replace('_', ' ').title()}" for t in listing['special_tags']])
                        housing_msg += f"{tags_str}\n"
                    
                    housing_msg += f"\n🔗 [Ver anuncio]({listing['url']})\n"
                    housing_msg += f"📡 Fuente: {listing['source']}"
                    
                    await update.message.reply_text(housing_msg, parse_mode='Markdown', disable_web_page_preview=True)
                
                # Mensaje final explicativo
                await update.message.reply_text(
                    f"📊 **{len(location_listings)} viviendas alternativas en {location}**\n\n"
                    f"💡 No encontré **{keywords}** específicamente, pero estas están en tu ubicación y podrían interesarte.\n\n"
                    f"✅ Búsqueda guardada.\n"
                    f"🔔 Usa '⚙️ Mis Búsquedas' para activar alertas.",
                    parse_mode='Markdown'
                )
            
        except Exception as e:
            logger.error(f"Error procesando búsqueda vivienda: {e}")
            await update.message.reply_text(
                f"❌ Error al buscar viviendas: {str(e)}\n\n"
                f"Intenta de nuevo o contacta con soporte."
            )
    
    async def check_alerts(self, context: ContextTypes.DEFAULT_TYPE):
        """Verificar búsquedas guardadas y enviar alertas de nuevos resultados"""
        try:
            logger.info("🔔 Ejecutando verificación de alertas automáticas...")
            
            # Obtener solo las búsquedas con alertas ACTIVADAS
            searches = get_all_searches()
            active_searches = [s for s in searches if s.get('is_active', False)]
            
            if not active_searches:
                logger.info("No hay búsquedas con alertas activadas")
                return
            
            logger.info(f"Verificando {len(active_searches)} búsquedas con alertas activadas...")
            
            for search in active_searches:
                search_id = search['id']
                user_id = search['user_id']
                search_type = search['search_type']
                keywords = search['keywords']
                location = search['location']
                
                try:
                    # Verificar si ya se revisó recientemente (última hora)
                    if search_id in self.last_alert_check:
                        time_diff = datetime.now() - self.last_alert_check[search_id]
                        if time_diff < timedelta(hours=1):
                            continue
                    
                    logger.info(f"Verificando búsqueda #{search_id}: {search_type} - {keywords} en {location}")
                    
                    if search_type == 'trabajo':
                        # Buscar trabajos
                        result = search_jobs(keywords, location, max_results=10)
                        
                        # Manejar nuevo formato con exact_matches y location_only
                        exact_jobs = result.get('exact_matches', []) if isinstance(result, dict) else result
                        location_jobs = result.get('location_only', []) if isinstance(result, dict) else []
                        
                        # Priorizar trabajos exactos
                        new_jobs = exact_jobs if exact_jobs else location_jobs[:5]  # Solo 5 alternativos
                        
                        if new_jobs:
                            # Guardar en BD
                            saved = save_jobs(new_jobs)
                            
                            if saved > 0:
                                # Mensaje diferente según tipo de resultados
                                if exact_jobs:
                                    alert_msg = (
                                        f"🔔 **NUEVA ALERTA DE TRABAJO**\n\n"
                                        f"💼 {keywords}\n"
                                        f"📍 {location}\n\n"
                                        f"✅ Se encontraron **{saved} nuevas ofertas**\n\n"
                                        f"Mostrando las primeras:"
                                    )
                                else:
                                    alert_msg = (
                                        f"🔔 **ALERTA: Trabajos en {location}**\n\n"
                                        f"No encontré trabajos de **{keywords}**, pero hay {len(new_jobs)} ofertas en tu ubicación:\n"
                                    )
                                
                                await context.bot.send_message(
                                    chat_id=user_id,
                                    text=alert_msg,
                                    parse_mode='Markdown'
                                )
                                
                                # Enviar todos los trabajos
                                for i, job in enumerate(new_jobs, 1):
                                    job_msg = (
                                        f"**{i}. {job['title']}**\n"
                                        f"🏢 {job['company']}\n"
                                        f"📍 {job['location']}\n"
                                    )
                                    
                                    if job.get('salary'):
                                        job_msg += f"💰 {job['salary']}\n"
                                    
                                    job_msg += f"\n🔗 [Ver oferta]({job['url']})\n"
                                    job_msg += f"📡 {job['source']}"
                                    
                                    await context.bot.send_message(
                                        chat_id=user_id,
                                        text=job_msg,
                                        parse_mode='Markdown',
                                        disable_web_page_preview=True
                                    )
                                
                                logger.info(f"✅ Alerta enviada a usuario {user_id}: {saved} trabajos")
                    
                    elif search_type == 'vivienda':
                        # Buscar viviendas
                        result = search_housing(keywords, location, None, max_results=10)
                        
                        # Manejar nuevo formato con exact_matches y location_only
                        exact_listings = result.get('exact_matches', []) if isinstance(result, dict) else result
                        location_listings = result.get('location_only', []) if isinstance(result, dict) else []
                        
                        # Priorizar viviendas exactas
                        new_listings = exact_listings if exact_listings else location_listings[:5]  # Solo 5 alternativas
                        
                        if new_listings:
                            # Guardar en BD
                            saved = save_housing(new_listings)
                            
                            if saved > 0:
                                # Mensaje diferente según tipo de resultados
                                if exact_listings:
                                    alert_msg = (
                                        f"🔔 **NUEVA ALERTA DE VIVIENDA**\n\n"
                                        f"🏠 {keywords}\n"
                                        f"📍 {location}\n\n"
                                        f"✅ Se encontraron **{saved} nuevas viviendas**\n\n"
                                        f"Mostrando las primeras:"
                                    )
                                else:
                                    alert_msg = (
                                        f"🔔 **ALERTA: Viviendas en {location}**\n\n"
                                        f"No encontré **{keywords}**, pero hay {len(new_listings)} viviendas en tu ubicación:\n"
                                    )
                                
                                await context.bot.send_message(
                                    chat_id=user_id,
                                    text=alert_msg,
                                    parse_mode='Markdown'
                                )
                                
                                # Enviar todas las viviendas
                                for i, listing in enumerate(new_listings, 1):
                                    housing_msg = (
                                        f"**{i}. {listing['title']}**\n"
                                        f"📍 {listing['location']}\n"
                                    )
                                    
                                    if listing.get('price'):
                                        housing_msg += f"💰 {listing['price']}€/mes\n"
                                    
                                    if listing.get('bedrooms'):
                                        housing_msg += f"🛏️ {listing['bedrooms']} hab.\n"
                                    
                                    housing_msg += f"\n🔗 [Ver anuncio]({listing['url']})\n"
                                    housing_msg += f"📡 {listing['source']}"
                                    
                                    await context.bot.send_message(
                                        chat_id=user_id,
                                        text=housing_msg,
                                        parse_mode='Markdown',
                                        disable_web_page_preview=True
                                    )
                                
                                logger.info(f"✅ Alerta enviada a usuario {user_id}: {saved} viviendas")
                    
                    # Actualizar timestamp de última verificación
                    self.last_alert_check[search_id] = datetime.now()
                    
                except Exception as e:
                    logger.error(f"Error verificando búsqueda #{search_id}: {e}")
                    continue
            
            logger.info("✅ Verificación de alertas completada")
            
        except Exception as e:
            logger.error(f"Error en check_alerts: {e}")
    
    def run(self):
        """Iniciar el bot"""
        self.app = Application.builder().token(BOT_TOKEN).build()
        
        # Conversation handler para búsqueda de trabajo
        trabajo_conv = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex(r'💼|[Tt]rabajo|TRABAJO'), self.buscar_trabajo)
            ],
            states={
                TRABAJO_CIUDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.trabajo_ciudad)],
                TRABAJO_SALARIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.trabajo_salario)],
                TRABAJO_CONTRATO: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.trabajo_contrato)],
                TRABAJO_EXPERIENCIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.trabajo_experiencia)],
            },
            fallbacks=[CommandHandler("cancelar", self.cancelar)]
        )
        
        # Conversation handler para búsqueda de vivienda
        vivienda_conv = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex(r'🏠|[Vv]ivienda|VIVIENDA'), self.buscar_vivienda)
            ],
            states={
                VIVIENDA_CIUDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.vivienda_ciudad)],
                VIVIENDA_PRECIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.vivienda_precio)],
                VIVIENDA_HABITACIONES: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.vivienda_habitaciones)],
                VIVIENDA_M2: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.vivienda_m2)],
            },
            fallbacks=[CommandHandler("cancelar", self.cancelar)]
        )
        
        # Handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.ayuda))
        self.app.add_handler(CommandHandler("pago", self.pago))
        self.app.add_handler(CommandHandler("admin", self.admin))
        self.app.add_handler(CommandHandler("usuarios", self.usuarios))
        self.app.add_handler(CallbackQueryHandler(self.handle_admin_callback))
        self.app.add_handler(trabajo_conv)
        self.app.add_handler(vivienda_conv)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Sistema de alertas automáticas (solo para búsquedas activas)
        job_queue = self.app.job_queue
        job_queue.run_repeating(
            self.check_alerts,
            interval=3600,  # 1 hora en segundos
            first=60,  # Primera ejecución después de 1 minuto
            name='alert_checker'
        )
        logger.info("🔔 Sistema de alertas automáticas activado (cada 1 hora - solo búsquedas activas)")
        
        # Iniciar
        logger.info("Bot iniciado correctamente ✅")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == '__main__':
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN no configurado en .env")
        exit(1)
    
    # Inicializar base de datos
    try:
        logger.info("🔄 Inicializando base de datos...")
        init_database()
        logger.info("✅ Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"❌ Error inicializando base de datos: {e}")
        exit(1)
    
    # Iniciar servidor HTTP para Render (en background)
    if os.getenv('RENDER_SERVICE_NAME'):
        run_in_background()
        
        # Esperar 90 segundos para que instancia anterior termine
        import time
        logger.info("⏳ RENDER: Esperando 90s para que instancia anterior termine...")
        time.sleep(90)
    
    bot = VidaNuevaBot()
    bot.run()
