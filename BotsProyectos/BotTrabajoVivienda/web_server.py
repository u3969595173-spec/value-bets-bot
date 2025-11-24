"""
Servidor HTTP simple para mantener el servicio activo en Render
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os

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
    """Inicia servidor HTTP en puerto para Render"""
    port = int(os.getenv('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"Servidor HTTP iniciado en puerto {port}")
    server.serve_forever()

def run_in_background():
    """Ejecuta el servidor en un thread separado"""
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()
