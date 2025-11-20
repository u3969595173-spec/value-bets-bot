"""
Servidor web para webhooks de Telegram y health checks en Render
"""
import os
import sys
import asyncio
import logging
from aiohttp import web

# Importar el bot para acceder a telegram_app
import main as bot_main

logger = logging.getLogger(__name__)

async def health_check(request):
    """Health check endpoint para Render"""
    return web.Response(text='Bot is running!')

async def telegram_webhook(request):
    """Endpoint para recibir updates de Telegram via webhook"""
    try:
        update_data = await request.json()
        
        # Obtener la instancia del bot desde main
        if hasattr(bot_main, 'monitoring_system') and bot_main.monitoring_system:
            telegram_app = bot_main.monitoring_system.telegram_app
            
            # Procesar el update
            from telegram import Update
            update = Update.de_json(update_data, telegram_app.bot)
            await telegram_app.process_update(update)
            
            return web.Response(status=200)
        else:
            logger.error("Bot no inicializado aún")
            return web.Response(status=503, text="Bot not ready")
            
    except Exception as e:
        logger.error(f"Error procesando webhook: {e}")
        return web.Response(status=500, text=str(e))

async def start_server():
    """Inicia el servidor aiohttp"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_post('/telegram-webhook', telegram_webhook)
    
    port = int(os.environ.get('PORT', 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Servidor HTTP iniciado en puerto {port}")
    logger.info(f"Webhook endpoint: /telegram-webhook")
    
    # Mantener el servidor corriendo
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Iniciar servidor y bot juntos
    print("Iniciando bot principal...")
    asyncio.run(bot_main.main())
