"""Odds fetcher: tries TheOddsAPI if API key provided, otherwise loads sample JSON

Returns a standardized list of events with bookmakers and markets.
"""
import os
import aiohttp
import json
from pathlib import Path
from typing import List

class OddsFetcher:
    def __init__(self, api_key: str = None, sample_path: str = "data/sample_odds.json"):
        # Preferir API key pasada, si no usar la variable de entorno API_KEY (o THEODDS_API_KEY)
        self.api_key = api_key or os.getenv('API_KEY') or os.getenv('THEODDS_API_KEY')
        self.sample_path = sample_path

    async def fetch_odds(self, sports: List[str]):
        if self.api_key:
            return await self._fetch_from_theodds(sports)
        else:
            return self._load_sample()

    async def _fetch_from_theodds(self, sports: List[str]):
        # Construir URL completa con apiKey en query string
        base_url = "https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        query_params = "?apiKey={apiKey}&regions=eu,us,au&markets=h2h,spreads,totals&oddsFormat=decimal"
        
        headers = {
            'User-Agent': 'ValueBetsBot/1.0',
            'Accept': 'application/json'
        }
        
        results = []
        async with aiohttp.ClientSession(headers=headers) as session:
            for sport in sports:
                # URL completa con todos los parámetros
                url = base_url.format(sport=sport) + query_params.format(apiKey=self.api_key)
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for ev in data:
                                ev['_sport_key'] = sport
                                results.append(ev)
                        else:
                            text = await resp.text()
                            print(f"Warning: TheOddsAPI {sport} returned {resp.status}: {text[:100]}")
                except Exception as e:
                    print(f"Error fetching {sport}: {e}")
        return results

    def _load_sample(self):
        p = Path(self.sample_path)
        if not p.exists():
            print(f"Sample odds file not found at {self.sample_path}")
            return []
        with p.open(encoding='utf-8') as f:
            data = json.load(f)
        # support two shapes: {\"events\": [...]} or list
        if isinstance(data, dict) and 'events' in data:
            return data['events']
        return data
