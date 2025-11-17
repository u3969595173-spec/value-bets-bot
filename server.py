"""
Servidor web simple para mantener el bot activo en Render
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os
import sys
import asyncio

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running!')
    
    def log_message(self, format, *args):
        # Silenciar logs del servidor HTTP
        pass

def start_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Servidor HTTP iniciado en puerto {port}")
    server.serve_forever()

if __name__ == '__main__':
    # Iniciar servidor HTTP en thread separado
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Importar y ejecutar el bot principal
    print("Iniciando bot principal...")
    from main import main
    asyncio.run(main())
