"""
Bot Vida Nueva - Trabajo y Vivienda para inmigrantes
MVP - Versión inicial
"""
import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from web_server import run_in_background
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from database import init_database, get_or_create_user, save_search, get_user_searches, save_jobs, search_jobs_db
from scrapers.job_scraper import search_jobs
import json

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


class VidaNuevaBot:
    def __init__(self):
        self.app = None
    
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
            "💼 **Trabajo** - Con filtros especiales\n"
            "🏠 **Vivienda** - Sin requisitos imposibles\n\n"
            "**Ventajas:**\n"
            "✅ Alertas en 30 segundos\n"
            "✅ Filtros únicos (sin papeles, sin nómina)\n"
            "✅ Scraping de 35 plataformas\n\n"
            "Selecciona una opción:"
        )
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def buscar_trabajo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para buscar trabajo"""
        msg = (
            "💼 **BÚSQUEDA DE TRABAJO**\n\n"
            "Escribe tu búsqueda en este formato:\n\n"
            "`trabajo: [puesto], [ciudad], [filtros]`\n\n"
            "**Ejemplos:**\n"
            "• `trabajo: camarero, Madrid, sin papeles`\n"
            "• `trabajo: limpieza, Barcelona`\n"
            "• `trabajo: construcción, Valencia, con contrato`\n\n"
            "**Filtros disponibles:**\n"
            "🔸 `sin papeles` - Trabajos que contratan sin NIE\n"
            "🔸 `con contrato` - Para arraigo social\n"
            "🔸 `urgente` - Incorporación inmediata\n\n"
            "Buscaré en Indeed, Infojobs, Jooble y más..."
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def buscar_vivienda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para buscar vivienda"""
        msg = (
            "🏠 **BÚSQUEDA DE VIVIENDA**\n\n"
            "Escribe tu búsqueda en este formato:\n\n"
            "`vivienda: [tipo], [ciudad], [precio], [filtros]`\n\n"
            "**Ejemplos:**\n"
            "• `vivienda: habitación, Madrid, 500`\n"
            "• `vivienda: piso, Barcelona, 800, sin fianza`\n"
            "• `vivienda: estudio, Valencia, 600, sin nómina`\n\n"
            "**Filtros disponibles:**\n"
            "🔸 `sin nómina` - No piden contrato laboral\n"
            "🔸 `sin fianza` - Sin depósito inicial\n"
            "🔸 `acepta extranjeros` - Sin discriminación\n\n"
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
                "💡 **Plan Gratis:** 3 búsquedas activas\n"
                "💎 **Plan Premium:** 20 búsquedas activas + alertas instantáneas"
            )
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /help"""
        msg = (
            "ℹ️ **CÓMO FUNCIONA**\n\n"
            "1️⃣ Selecciona qué buscas (trabajo o vivienda)\n"
            "2️⃣ Escribe tu búsqueda con filtros\n"
            "3️⃣ Yo escaneo 35 plataformas cada 30 minutos\n"
            "4️⃣ Te aviso INSTANTÁNEAMENTE cuando hay algo nuevo\n\n"
            "**Comandos:**\n"
            "/start - Menú principal\n"
            "/help - Esta ayuda\n\n"
            "**Planes:**\n"
            "🆓 Gratis: 3 búsquedas, alertas cada hora\n"
            "💎 Premium 15€/mes: 20 búsquedas, alertas instantáneas\n\n"
            "**Soporte:** @tu_usuario"
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
                await update.message.reply_text("🏠 Búsqueda de vivienda en desarrollo...")
            else:
                await update.message.reply_text(
                    "No entiendo ese comando. Usa /help para ver los comandos disponibles."
                )
    
    async def process_job_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """Procesar búsqueda de trabajo"""
        user_id = update.effective_user.id
        
        try:
            # Parsear query: "trabajo: camarero, Madrid, sin papeles"
            query_clean = query.replace("trabajo:", "").strip()
            parts = [p.strip() for p in query_clean.split(",")]
            
            if len(parts) < 1:
                await update.message.reply_text("❌ Formato incorrecto. Ejemplo: `trabajo: camarero, Madrid`")
                return
            
            keywords = parts[0]
            location = parts[1] if len(parts) > 1 else "España"
            filters = parts[2:] if len(parts) > 2 else []
            
            # Mensaje de inicio
            status_msg = await update.message.reply_text(
                f"🔍 **BUSCANDO TRABAJO**\n\n"
                f"💼 Puesto: {keywords}\n"
                f"📍 Ubicación: {location}\n"
                f"🔧 Filtros: {', '.join(filters) if filters else 'ninguno'}\n\n"
                f"⏳ Escaneando 11 portales de empleo...",
                parse_mode='Markdown'
            )
            
            # Ejecutar scraping
            logger.info(f"Buscando trabajos: {keywords} en {location}")
            jobs = search_jobs(keywords, location, max_results=50)
            
            # Guardar en base de datos
            if jobs:
                saved_count = save_jobs(jobs)
                logger.info(f"Guardados {saved_count} trabajos nuevos")
            
            # Aplicar filtros especiales
            if filters:
                filtered_jobs = []
                for job in jobs:
                    tags_lower = [t.lower() for t in (job.get('special_tags') or [])]
                    desc_lower = (job.get('description') or '').lower()
                    title_lower = job['title'].lower()
                    
                    match = True
                    for f in filters:
                        f_lower = f.lower()
                        if 'sin papeles' in f_lower or 'sin nie' in f_lower:
                            if 'sin_papeles' not in tags_lower and 'sin papeles' not in desc_lower and 'sin nie' not in desc_lower:
                                match = False
                        elif 'urgente' in f_lower:
                            if 'urgente' not in tags_lower and 'urgente' not in desc_lower and 'urgente' not in title_lower:
                                match = False
                        elif 'sin experiencia' in f_lower:
                            if 'sin_experiencia' not in tags_lower and 'sin experiencia' not in desc_lower:
                                match = False
                    
                    if match:
                        filtered_jobs.append(job)
                
                jobs = filtered_jobs
            
            # Guardar búsqueda
            try:
                filters_json = json.dumps(filters) if filters else None
                search_id = save_search(user_id, 'trabajo', keywords, location, filters_json)
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
    
    def run(self):
        """Iniciar el bot"""
        self.app = Application.builder().token(BOT_TOKEN).job_queue(None).build()
        
        # Handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.ayuda))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
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
