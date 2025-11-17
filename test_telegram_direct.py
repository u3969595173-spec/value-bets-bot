import requests
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Test usando requests directo
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": "🎯 TEST ALERT\n\nSi recibes este mensaje, el bot funciona correctamente!",
    "parse_mode": "Markdown"
}

print(f"Enviando mensaje a CHAT_ID: {CHAT_ID}")
print(f"BOT_TOKEN: {BOT_TOKEN[:20]}...")

response = requests.post(url, json=payload)
print(f"\nRespuesta: {response.status_code}")
print(f"Contenido: {response.json()}")

if response.status_code == 200:
    print("\n✅ MENSAJE ENVIADO EXITOSAMENTE!")
else:
    print(f"\n❌ ERROR: {response.json().get('description')}")
