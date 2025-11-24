"""Script temporal para verificar si badminton está disponible"""
import aiohttp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def check_sports():
    api_key = os.getenv('API_KEY')
    if not api_key:
        print("❌ API_KEY no encontrada en .env")
        return
    
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={api_key}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                sports = await resp.json()
                
                # Buscar badminton
                badminton = [s for s in sports if 'badminton' in s['key'].lower() or 'badminton' in s['title'].lower()]
                
                if badminton:
                    print("✅ BADMINTON DISPONIBLE:")
                    for sport in badminton:
                        print(f"   {sport['key']} - {sport['title']}")
                else:
                    print("❌ BADMINTON NO DISPONIBLE EN LA API")
                
                print(f"\n📊 Total deportes disponibles: {len(sports)}")
                print("\n🎯 TODOS LOS DEPORTES DISPONIBLES:")
                for sport in sorted(sports, key=lambda x: x['key']):
                    print(f"   {sport['key']:50} - {sport['title']}")
            else:
                print(f"❌ Error: {resp.status}")

asyncio.run(check_sports())
