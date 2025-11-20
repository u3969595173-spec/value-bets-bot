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

if __name__ == "__main__":
    print("[RUN_RENDER v4] Iniciando bot completo: Comandos + Pronósticos con HTTP health server...")
    print(f"[RUN_RENDER v4] Python: {sys.version}")
    print(f"[RUN_RENDER v4] Working dir: {os.getcwd()}")
    
    # Iniciar HTTP server en thread separado para Render
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    try:
        # Importar ambos bots
        import bot_telegram
        import main
        
        print("[RUN_RENDER v4] ✅ Arrancando bot de COMANDOS (bot_telegram.py)...")
        print("[RUN_RENDER v4] ✅ Arrancando bot de PRONÓSTICOS (main.py)...")
        
        # Crear evento loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Función para correr bot_telegram en thread separado
        def run_bot_telegram():
            bot_telegram.main()
        
        # Arrancar bot de comandos en thread separado
        telegram_thread = Thread(target=run_bot_telegram, daemon=False)
        telegram_thread.start()
        
        # Arrancar bot de pronósticos en el main thread
        loop.run_until_complete(main.ValueBotMonitor().run())
        
    except Exception as e:
        print(f"[RUN_RENDER v4] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
