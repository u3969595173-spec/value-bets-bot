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
    CallbackQueryHandler
)
from database import (
    init_database, get_or_create_user, save_search, get_user_searches, 
    save_jobs, search_jobs_db, save_housing, search_housing_db, get_all_searches,
    activate_user, deactivate_user, get_all_users, get_user_stats
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
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))  # Tu Telegram ID


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
            [KeyboardButton("⚙️ Mis Búsquedas"), KeyboardButton("ℹ️ Ayuda")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        welcome_msg = (
            f"¡Hola {user.first_name}! 👋\n\n"
            "Soy el Bot **Vida Nueva** 🚀\n\n"
            "Te ayudo a encontrar:\n"
            "💼 **Trabajo** - 11 portales de empleo\n"
            "🏠 **Vivienda** - 6 portales inmobiliarios\n\n"
            "Todo en tiempo real.\n\n"
            "💎 **Suscripción: 10€/mes**\n\n"
            "📞 **Soporte/Pagos:** +34 936 07 56 41 (WhatsApp)\n\n"
            "Selecciona una opción:"
        )
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def buscar_trabajo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para buscar trabajo"""
        msg = (
            "💼 **BÚSQUEDA DE TRABAJO**\n\n"
            "Escribe tu búsqueda con los detalles que quieras:\n\n"
            "**Formato básico:**\n"
            "`trabajo: [puesto], [ciudad]`\n\n"
            "**Formato completo (opcional):**\n"
            "`trabajo: [puesto], [ciudad], salario: [mínimo], contrato: [tipo], experiencia: [años]`\n\n"
            "**Ejemplos:**\n"
            "• `trabajo: camarero, Madrid`\n"
            "• `trabajo: limpieza, Barcelona, salario: 1200`\n"
            "• `trabajo: construcción, Valencia, salario: 1500, contrato: indefinido`\n"
            "• `trabajo: cocinero, Madrid, experiencia: 0, salario: 1300`\n\n"
            "**Opciones disponibles:**\n"
            "• `salario: [cantidad]` - Salario mínimo en €/mes\n"
            "• `contrato: [tipo]` - indefinido, temporal, media jornada\n"
            "• `experiencia: [años]` - Años de experiencia (0 = sin experiencia)\n\n"
            "Buscaré en Indeed, Infojobs, Jooble y más..."
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def buscar_vivienda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para buscar vivienda"""
        msg = (
            "🏠 **BÚSQUEDA DE VIVIENDA**\n\n"
            "Escribe tu búsqueda con los detalles que quieras:\n\n"
            "**Formato básico:**\n"
            "`vivienda: [tipo], [ciudad]`\n\n"
            "**Formato completo (opcional):**\n"
            "`vivienda: [tipo], [ciudad], precio: [min-max], habitaciones: [num], m2: [tamaño]`\n\n"
            "**Ejemplos:**\n"
            "• `vivienda: habitacion, Madrid`\n"
            "• `vivienda: piso, Barcelona, precio: 500-800`\n"
            "• `vivienda: estudio, Valencia, precio: 400-600, m2: 30`\n"
            "• `vivienda: habitacion, Madrid, precio: 300-500, habitaciones: 1`\n\n"
            "**Opciones disponibles:**\n"
            "• `precio: [min-max]` - Rango de precio en €/mes\n"
            "• `habitaciones: [número]` - Número de habitaciones\n"
            "• `m2: [tamaño]` - Metros cuadrados mínimos\n"
            "• `baños: [número]` - Número de baños\n\n"
            "Buscaré en Idealista, Fotocasa, Badi y más..."
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def mis_busquedas(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando para ver búsquedas guardadas"""
        user_id = update.effective_user.id
        
        # Obtener búsquedas de la base de datos
        searches = get_user_searches(user_id)
        
        if searches:
            msg = "⚙️ **TUS BÚSQUEDAS ACTIVAS:**\n\n"
            for i, search in enumerate(searches, 1):
                tipo = "💼 Trabajo" if search['search_type'] == 'trabajo' else "🏠 Vivienda"
                msg += f"{i}. {tipo}: {search['keywords']}\n"
                if search['location']:
                    msg += f"   📍 {search['location']}\n"
                msg += "\n"
            
            msg += f"\n📊 Total: {len(searches)} búsquedas\n"
            msg += "\n💡 Recibirás alertas cuando encuentre nuevas ofertas."
        else:
            msg = (
                "⚙️ **MIS BÚSQUEDAS**\n\n"
                "Aún no tienes búsquedas guardadas.\n\n"
                "Cuando crees una búsqueda, te enviaré alertas automáticas "
                "cada vez que aparezca una nueva oferta.\n\n"
                "💎 **Suscripción:** 10€/mes - Búsquedas ilimitadas"
            )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        msg = (
            "ℹ️ **CÓMO FUNCIONA**\n\n"
            "1️⃣ Selecciona qué buscas (trabajo o vivienda)\n"
            "2️⃣ Escribe tu búsqueda: `trabajo: camarero, Madrid`\n"
            "3️⃣ Yo escaneo múltiples plataformas en tiempo real\n"
            "4️⃣ Te muestro los mejores resultados al instante\n\n"
            "**Fuentes de datos:**\n"
            "💼 Trabajo: 11 sitios (Indeed, InfoJobs, Milanuncios...)\n"
            "🏠 Vivienda: 6 sitios (Idealista, Fotocasa, Badi...)\n\n"
            "**Precio:**\n"
            "💎 **10€/mes** - Acceso completo sin límites\n\n"
            "**Comandos:**\n"
            "/start - Menú principal\n"
            "/help - Esta ayuda\n\n"
            "📞 **Soporte/Pagos:** +34 936 07 56 41 (WhatsApp)"
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
        """Manejar botones de activar/desactivar usuarios"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        if ADMIN_ID == 0 or user_id != ADMIN_ID:
            await query.edit_message_text("❌ No tienes permisos de administrador.")
            return
        
        data = query.data
        
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
                            "💼 Busca trabajos en 11 portales\n"
                            "🏠 Busca viviendas en 6 portales\n"
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
                "🔒 **SUSCRIPCIÓN REQUERIDA**\n\n"
                "Para usar el bot necesitas activar tu suscripción Premium.\n\n"
                "💎 **10€/mes** - Acceso completo\n"
                "• 11 portales de trabajo\n"
                "• 6 portales de vivienda\n"
                "• Alertas automáticas cada hora\n"
                "• Búsquedas ilimitadas\n\n"
                "📞 **Contacta para activar:**\n"
                "+34 936 07 56 41 (WhatsApp)\n\n"
                f"🆔 Tu ID: `{user_id}`\n"
                "Proporciona este ID al hacer el pago.",
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
                f"⏳ Escaneando 11 portales de empleo...",
                parse_mode='Markdown'
            )
            
            # Ejecutar scraping
            logger.info(f"Buscando trabajos: {keywords} en {location}")
            jobs = search_jobs(keywords, location, max_results=50)
            
            # Filtrar por criterios adicionales
            if min_salary or contract_type or experience is not None:
                filtered_jobs = []
                for job in jobs:
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
                
                jobs = filtered_jobs
                logger.info(f"Después de filtrar: {len(jobs)} trabajos")
            
            # Guardar en base de datos
            if jobs:
                saved_count = save_jobs(jobs)
                logger.info(f"Guardados {saved_count} trabajos nuevos")
            
            # Guardar búsqueda
            try:
                search_id = save_search(user_id, 'trabajo', keywords, location, None)
                logger.info(f"Búsqueda guardada con ID: {search_id}")
            except Exception as e:
                logger.error(f"Error guardando búsqueda: {e}")
            
            # Actualizar mensaje con resultados
            if not jobs:
                await status_msg.edit_text(
                    f"❌ **NO SE ENCONTRARON RESULTADOS**\n\n"
                    f"💼 Puesto: {keywords}\n"
                    f"📍 Ubicación: {location}\n\n"
                    f"💡 **Sugerencias:**\n"
                    f"• Prueba con sinónimos (ej: 'mesero' en vez de 'camarero')\n"
                    f"• Amplía la ubicación (ej: 'España' en vez de ciudad)\n"
                    f"• Reduce los filtros\n\n"
                    f"✅ Tu búsqueda está guardada. Te avisaré cuando encuentre ofertas.",
                    parse_mode='Markdown'
                )
                return
            
            # Enviar resultados
            result_msg = (
                f"✅ **ENCONTRADOS {len(jobs)} TRABAJOS**\n\n"
                f"💼 {keywords}\n"
                f"📍 {location}\n\n"
                f"📋 Mostrando los primeros 5 resultados:\n"
            )
            await status_msg.edit_text(result_msg, parse_mode='Markdown')
            
            # Enviar cada trabajo como mensaje separado
            for i, job in enumerate(jobs[:5], 1):
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
            if len(jobs) > 5:
                await update.message.reply_text(
                    f"📊 Se encontraron **{len(jobs)} ofertas** en total.\n\n"
                    f"✅ Tu búsqueda está guardada.\n"
                    f"🔔 Te avisaré cuando aparezcan nuevas ofertas.\n\n"
                    f"💡 Usa '⚙️ Mis Búsquedas' para ver todas tus búsquedas activas.",
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
                "🔒 **SUSCRIPCIÓN REQUERIDA**\n\n"
                "Para usar el bot necesitas activar tu suscripción Premium.\n\n"
                "💎 **10€/mes** - Acceso completo\n"
                "• 11 portales de trabajo\n"
                "• 6 portales de vivienda\n"
                "• Alertas automáticas cada hora\n"
                "• Búsquedas ilimitadas\n\n"
                "📞 **Contacta para activar:**\n"
                "+34 936 07 56 41 (WhatsApp)\n\n"
                f"🆔 Tu ID: `{user_id}`\n"
                "Proporciona este ID al hacer el pago.",
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
                f"⏳ Escaneando 6 portales de vivienda...",
                parse_mode='Markdown'
            )
            
            # Ejecutar scraping
            logger.info(f"Buscando viviendas: {keywords} en {location}")
            listings = search_housing(keywords, location, None, max_results=40)
            
            # Filtrar por criterios adicionales
            if min_price or max_price or bedrooms or min_m2 or bathrooms:
                filtered_listings = []
                for listing in listings:
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
                
                listings = filtered_listings
                logger.info(f"Después de filtrar: {len(listings)} viviendas")
            
            # Guardar en base de datos
            if listings:
                saved_count = save_housing(listings)
                logger.info(f"Guardadas {saved_count} viviendas nuevas")
            
            # Guardar búsqueda
            try:
                search_id = save_search(user_id, 'vivienda', keywords, location, None)
                logger.info(f"Búsqueda vivienda guardada con ID: {search_id}")
            except Exception as e:
                logger.error(f"Error guardando búsqueda vivienda: {e}")
            
            # Actualizar mensaje con resultados
            if not listings:
                await status_msg.edit_text(
                    f"❌ **NO SE ENCONTRARON RESULTADOS**\n\n"
                    f"🏘️ Tipo: {keywords}\n"
                    f"📍 {location}\n\n"
                    f"💡 **Sugerencias:**\n"
                    f"• Prueba con otra ciudad\n"
                    f"• Cambia el tipo (ej: 'habitacion' en vez de 'piso')\n"
                    f"• Amplía la zona de búsqueda\n\n"
                    f"✅ Tu búsqueda está guardada. Te avisaré cuando encuentre ofertas.",
                    parse_mode='Markdown'
                )
                return
            
            # Enviar resultados
            result_msg = (
                f"✅ **ENCONTRADAS {len(listings)} VIVIENDAS**\n\n"
                f"🏘️ {keywords}\n"
                f"📍 {location}\n\n"
                f"📋 Mostrando los primeros 5 resultados:\n"
            )
            await status_msg.edit_text(result_msg, parse_mode='Markdown')
            
            # Enviar cada vivienda como mensaje separado
            for i, listing in enumerate(listings[:5], 1):
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
            if len(listings) > 5:
                await update.message.reply_text(
                    f"📊 Se encontraron **{len(listings)} viviendas** en total.\n\n"
                    f"✅ Tu búsqueda está guardada.\n"
                    f"🔔 Te avisaré cuando aparezcan nuevas ofertas.\n\n"
                    f"💡 Usa '⚙️ Mis Búsquedas' para ver todas tus búsquedas activas.",
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
            
            # Obtener todas las búsquedas activas
            searches = get_all_searches()
            
            if not searches:
                logger.info("No hay búsquedas activas para verificar")
                return
            
            logger.info(f"Verificando {len(searches)} búsquedas activas...")
            
            for search in searches:
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
                        new_jobs = search_jobs(keywords, location, max_results=10)
                        
                        if new_jobs:
                            # Guardar en BD
                            saved = save_jobs(new_jobs)
                            
                            if saved > 0:
                                # Enviar alerta al usuario
                                alert_msg = (
                                    f"🔔 **NUEVA ALERTA DE TRABAJO**\n\n"
                                    f"💼 {keywords}\n"
                                    f"📍 {location}\n\n"
                                    f"✅ Se encontraron **{saved} nuevas ofertas**\n\n"
                                    f"Mostrando las primeras:"
                                )
                                
                                await context.bot.send_message(
                                    chat_id=user_id,
                                    text=alert_msg,
                                    parse_mode='Markdown'
                                )
                                
                                # Enviar primeros 3 trabajos
                                for i, job in enumerate(new_jobs[:3], 1):
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
                        new_listings = search_housing(keywords, location, None, max_results=10)
                        
                        if new_listings:
                            # Guardar en BD
                            saved = save_housing(new_listings)
                            
                            if saved > 0:
                                # Enviar alerta al usuario
                                alert_msg = (
                                    f"🔔 **NUEVA ALERTA DE VIVIENDA**\n\n"
                                    f"🏠 {keywords}\n"
                                    f"📍 {location}\n\n"
                                    f"✅ Se encontraron **{saved} nuevas viviendas**\n\n"
                                    f"Mostrando las primeras:"
                                )
                                
                                await context.bot.send_message(
                                    chat_id=user_id,
                                    text=alert_msg,
                                    parse_mode='Markdown'
                                )
                                
                                # Enviar primeras 3 viviendas
                                for i, listing in enumerate(new_listings[:3], 1):
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
        
        # Handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.ayuda))
        self.app.add_handler(CommandHandler("admin", self.admin))
        self.app.add_handler(CommandHandler("usuarios", self.usuarios))
        self.app.add_handler(CallbackQueryHandler(self.handle_admin_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Programar alertas automáticas cada hora
        job_queue = self.app.job_queue
        job_queue.run_repeating(
            self.check_alerts,
            interval=3600,  # 1 hora en segundos
            first=60,  # Primera ejecución después de 1 minuto
            name='alert_checker'
        )
        logger.info("🔔 Sistema de alertas automáticas activado (cada 1 hora)")
        
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
