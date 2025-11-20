"""
run_render.py - Bot + HTTP server mínimo para Render - v4
"""
import sys
import os
import asyncio
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Handler HTTP simple para health checks de Render"""
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running')
    
    def log_message(self, format, *args):
        # Suprimir logs HTTP para no saturar
        pass

def run_http_server():
    """Corre un servidor HTTP mínimo en el puerto que Render espera"""
    port = int(os.getenv('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"[RUN_RENDER v4] HTTP health server listening on port {port}")
    server.serve_forever()

async def run_both_bots():
    """Ejecuta ambos bots en paralelo usando asyncio.gather()"""
    import bot_telegram
    import main
    
    # Crear tareas para ambos bots
    async def run_telegram_bot():
        """Wrapper para ejecutar bot_telegram.main() de forma async"""
        loop = asyncio.get_event_loop()
        # bot_telegram.main() es sync, lo ejecutamos en executor
        await loop.run_in_executor(None, bot_telegram.main)
    
    async def run_prediction_bot():
        """Ejecuta el bot de predicciones"""
        # main.main() ya es async y llama a ValueBotMonitor().run_continuous_monitoring()
        await main.main()
    
    print("[RUN_RENDER v4] ✅ Arrancando bot de COMANDOS (bot_telegram.py)...")
    print("[RUN_RENDER v4] ✅ Arrancando bot de PRONÓSTICOS (main.py)...")
    
    # Ejecutar ambos bots en paralelo
    await asyncio.gather(
        run_telegram_bot(),
        run_prediction_bot()
    )

if __name__ == "__main__":
    print("[RUN_RENDER v4] Iniciando bot completo: Comandos + Pronósticos con HTTP health server...")
    print(f"[RUN_RENDER v4] Python: {sys.version}")
    print(f"[RUN_RENDER v4] Working dir: {os.getcwd()}")
    
    # Iniciar HTTP server en thread separado para Render
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    try:
        # Ejecutar ambos bots en paralelo
        asyncio.run(run_both_bots())
        
    except KeyboardInterrupt:
        print("[RUN_RENDER v4] Bot stopped by user")
    except Exception as e:
        print(f"[RUN_RENDER v4] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
