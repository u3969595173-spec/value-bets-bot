"""Mostrar todos los deportes disponibles organizados"""
import aiohttp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def show_all_sports():
    api_key = os.getenv('API_KEY')
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={api_key}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                sports = await resp.json()
                
                # Organizar por categoría
                categories = {
                    'FUTBOL': [],
                    'BALONCESTO': [],
                    'FUTBOL AMERICANO': [],
                    'HOCKEY': [],
                    'COMBATE': [],
                    'CRICKET': [],
                    'RUGBY': [],
                    'OTROS': []
                }
                
                for sport in sports:
                    key = sport['key']
                    title = sport['title']
                    
                    if 'soccer' in key:
                        categories['FUTBOL'].append(f"{key} - {title}")
                    elif 'basketball' in key:
                        categories['BALONCESTO'].append(f"{key} - {title}")
                    elif 'americanfootball' in key:
                        categories['FUTBOL AMERICANO'].append(f"{key} - {title}")
                    elif 'icehockey' in key:
                        categories['HOCKEY'].append(f"{key} - {title}")
                    elif 'boxing' in key or 'mma' in key:
                        categories['COMBATE'].append(f"{key} - {title}")
                    elif 'cricket' in key:
                        categories['CRICKET'].append(f"{key} - {title}")
                    elif 'rugby' in key:
                        categories['RUGBY'].append(f"{key} - {title}")
                    else:
                        categories['OTROS'].append(f"{key} - {title}")
                
                print(f"\n{'='*80}")
                print(f"DEPORTES DISPONIBLES EN THE ODDS API ({len(sports)} TOTAL)")
                print(f"{'='*80}\n")
                
                for category, items in categories.items():
                    if items:
                        print(f"\n{category} ({len(items)}):")
                        print("-" * 80)
                        for item in sorted(items):
                            print(f"  • {item}")

asyncio.run(show_all_sports())
