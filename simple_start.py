"""
Simple bot startup - diagnóstico para Render
"""
import sys
import os
from datetime import datetime

print("=" * 60)
print("🚀 VALUE BET BOT - STARTUP")
print("=" * 60)
print(f"📅 {datetime.now()}")
print(f"🐍 Python: {sys.version}")
print(f"📂 Working dir: {os.getcwd()}")
print()

# Check env vars
print("🔍 Checking environment variables...")
api_key = os.getenv("API_KEY", "")
bot_token = os.getenv("BOT_TOKEN", "")
sports = os.getenv("SPORTS", "")

print(f"   API_KEY: {'✅ SET' if api_key else '❌ MISSING'}")
print(f"   BOT_TOKEN: {'✅ SET' if bot_token else '❌ MISSING'}")
print(f"   SPORTS: {sports if sports else '❌ MISSING'}")
print()

# Start web server for Render
print("🌐 Starting web server on port 10000...")
from http.server import HTTPServer, BaseHTTPRequestHandler

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
        <p>API_KEY: {'SET' if api_key else 'MISSING'}</p>
        <p>Sports: {sports}</p>
        </body>
        </html>
        """
        self.wfile.write(msg.encode())
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

port = int(os.getenv("PORT", "10000"))
server = HTTPServer(('0.0.0.0', port), HealthHandler)

print(f"✅ Server listening on http://0.0.0.0:{port}")
print("=" * 60)
print()

# Now try to import bot
try:
    print("📦 Importing bot modules...")
    sys.path.insert(0, os.getcwd())
    
    from data.odds_api import OddsFetcher
    print("   ✅ OddsFetcher")
    
    from scanner.scanner import ValueScanner
    print("   ✅ ValueScanner")
    
    print()
    print("✅ ALL IMPORTS SUCCESSFUL")
    print("🔄 Bot ready to scan...")
    print()
    
except Exception as e:
    print(f"❌ ERROR IMPORTING: {e}")
    import traceback
    traceback.print_exc()

# Keep server running
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\n👋 Shutting down...")
    server.shutdown()
