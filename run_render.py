"""
run_render.py - Unifica scanner (webserver) y bot Telegram para Render
"""
import os
import sys
import asyncio
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# --- Webserver para healthcheck (como simple_start.py) ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        msg = f"""
        <html>
        <body>
        <h1>✅ Value Bet Bot is RUNNING</h1>
        <p>Time: {datetime.now()}</p>
        <p>Python: {sys.version}</p>
        </body>
        </html>
        """
        self.wfile.write(msg.encode())
    def log_message(self, format, *args):
        pass

def start_webserver():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🌐 Webserver listening on http://0.0.0.0:{port}")
    server.serve_forever()

# --- Bot Telegram (como bot_telegram.py) ---
async def start_telegram_bot():
    import bot_telegram
    bot_telegram.main()

if __name__ == "__main__":
    print("[RUN_RENDER] Iniciando webserver en thread...")
    t = Thread(target=start_webserver, daemon=True)
    t.start()
    print("[RUN_RENDER] Webserver iniciado. Iniciando bot de Telegram...")
    try:
        asyncio.run(start_telegram_bot())
        print("[RUN_RENDER] Bot de Telegram finalizó (esto NO debería ocurrir)")
    except Exception as e:
        print(f"[RUN_RENDER] ERROR al iniciar bot de Telegram: {e}")
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
