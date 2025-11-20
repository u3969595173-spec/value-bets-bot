"""
run_render.py - Bot + HTTP server con webhook para Render - v5
"""
import sys
import os
import asyncio
import json
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Variable global para la aplicación de Telegram
telegram_app = None

class WebhookHandler(BaseHTTPRequestHandler):
    """Handler HTTP para health checks y webhook de Telegram"""
    
    def do_GET(self):
        """Health check de Render"""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running')
    
    def do_POST(self):
        """Recibe updates del webhook de Telegram"""
        global telegram_app
        
        # Solo procesar el path del webhook
        if not self.path.startswith('/webhook/'):
            self.send_response(404)
            self.end_headers()
            return
        
        try:
            # Leer el body de la request
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            update_data = json.loads(body.decode('utf-8'))
            
            # Procesar el update de Telegram de forma sync (lo maneja el bot internamente)
            if telegram_app:
                from telegram import Update
                update = Update.de_json(update_data, telegram_app.bot)
                
                # Programar procesamiento async en el loop principal
                loop = asyncio.new_event_loop()
                loop.run_until_complete(telegram_app.process_update(update))
            
            self.send_response(200)
            self.end_headers()
            
        except Exception as e:
            print(f"[WEBHOOK] Error procesando update: {e}")
            self.send_response(500)
            self.end_headers()
    
    def do_HEAD(self):
        """Manejar HEAD requests de health checks"""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
    
    def log_message(self, format, *args):
        # Suprimir logs HTTP rutinarios
        if '200' in str(args):
            return
        # Solo loggear errores
        print(f"[HTTP] {format % args}")

def run_http_server():
    """Corre un servidor HTTP que maneja health checks y webhook"""
    port = int(os.getenv('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), WebhookHandler)
    print(f"[RUN_RENDER v5] HTTP server listening on port {port}")
    server.serve_forever()

async def run_both_bots():
    """Ejecuta solo el bot de predicciones (comandos deshabilitado temporalmente)"""
    import main
    
    print("[RUN_RENDER v5] ✅ Arrancando bot de PRONÓSTICOS (main.py)...")
    print("[RUN_RENDER v5] ⚠️ Bot de comandos deshabilitado temporalmente")
    
    # Solo ejecutar el bot de predicciones
    await main.main()

if __name__ == "__main__":
    print("[RUN_RENDER v5] Iniciando bot completo: Comandos (WEBHOOK) + Pronósticos con HTTP server...")
    print(f"[RUN_RENDER v5] Python: {sys.version}")
    print(f"[RUN_RENDER v5] Working dir: {os.getcwd()}")
    
    # Iniciar HTTP server en thread separado para Render
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    try:
        # Ejecutar ambos bots en paralelo
        asyncio.run(run_both_bots())
        
    except KeyboardInterrupt:
        print("[RUN_RENDER v5] Bot stopped by user")
    except Exception as e:
        print(f"[RUN_RENDER v5] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
