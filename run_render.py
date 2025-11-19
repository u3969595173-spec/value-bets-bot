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
    print("[RUN_RENDER v4] Iniciando bot de Telegram con HTTP health server...")
    print(f"[RUN_RENDER v4] Python: {sys.version}")
    print(f"[RUN_RENDER v4] Working dir: {os.getcwd()}")
    
    # Iniciar HTTP server en thread separado para Render
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    try:
        import bot_telegram
        bot_telegram.main()
    except Exception as e:
        print(f"[RUN_RENDER v4] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
