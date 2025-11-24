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
from database import init_database, get_or_create_user, save_search, get_user_searches

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
        
        if "💼" in text or "trabajo" in text:
            await self.buscar_trabajo(update, context)
        elif "🏠" in text or "vivienda" in text:
            await self.buscar_vivienda(update, context)
        elif "⚙️" in text or "búsquedas" in text:
            await self.mis_busquedas(update, context)
        elif "ℹ️" in text or "ayuda" in text:
            await self.ayuda(update, context)
        else:
            # Procesar búsqueda
            if text.startswith("trabajo:"):
                await update.message.reply_text("🔍 Buscando trabajo... (funcionalidad en desarrollo)")
            elif text.startswith("vivienda:"):
                await update.message.reply_text("🔍 Buscando vivienda... (funcionalidad en desarrollo)")
            else:
                await update.message.reply_text(
                    "No entiendo ese comando. Usa /help para ver los comandos disponibles."
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
