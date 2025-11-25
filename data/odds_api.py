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
        """
        Fetch odds from The Odds API.
        Strategy: Fetch basic markets first, then optionally fetch expanded markets per event.
        """
        base_sport_url = "https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        base_event_url = "https://api.the-odds-api.com/v4/sports/{sport}/events/{event_id}/odds/"
        
        # Mercados básicos (soportados por sport endpoint)
        basic_markets = "h2h,spreads,totals"
        basic_query = f"?apiKey={{apiKey}}&regions=eu,us,au&markets={basic_markets}&oddsFormat=decimal"
        
        # Mercados expandidos (requieren event endpoint)
        expanded_markets = "h2h_q1,h2h_q2,h2h_q3,h2h_q4,spreads_q1,spreads_q2,spreads_q3,spreads_q4,totals_q1,totals_q2,totals_q3,totals_q4,player_points,player_assists,player_rebounds"
        expanded_query = f"?apiKey={{apiKey}}&regions=eu,us,au&markets={expanded_markets}&oddsFormat=decimal"
        
        headers = {
            'User-Agent': 'ValueBetsBot/1.0',
            'Accept': 'application/json'
        }
        
        results = []
        async with aiohttp.ClientSession(headers=headers) as session:
            for sport in sports:
                # 1. Fetch basic markets for all events
                url = base_sport_url.format(sport=sport) + basic_query.format(apiKey=self.api_key)
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            events = await resp.json()
                            
                            # 2. For each event, fetch expanded markets
                            for event in events:
                                event['_sport_key'] = sport
                                event_id = event.get('id')
                                
                                # Fetch expanded markets for this specific event
                                if event_id:
                                    expanded_url = base_event_url.format(sport=sport, event_id=event_id) + expanded_query.format(apiKey=self.api_key)
                                    try:
                                        async with session.get(expanded_url, timeout=aiohttp.ClientTimeout(total=10)) as exp_resp:
                                            if exp_resp.status == 200:
                                                expanded_data = await exp_resp.json()
                                                # Merge expanded markets into the event's bookmakers
                                                if expanded_data and 'bookmakers' in expanded_data:
                                                    # Merge bookmaker markets
                                                    existing_bookmakers = {bm.get('key'): bm for bm in event.get('bookmakers', [])}
                                                    for exp_bm in expanded_data.get('bookmakers', []):
                                                        bm_key = exp_bm.get('key')
                                                        if bm_key in existing_bookmakers:
                                                            # Add expanded markets to existing bookmaker
                                                            existing_bookmakers[bm_key].setdefault('markets', []).extend(exp_bm.get('markets', []))
                                                        else:
                                                            # Add new bookmaker with expanded markets
                                                            event.setdefault('bookmakers', []).append(exp_bm)
                                    except Exception as e:
                                        print(f"Warning: Could not fetch expanded markets for event {event_id}: {e}")
                                
                                results.append(event)
                        else:
                            text = await resp.text()
                            print(f"Warning: TheOddsAPI {sport} returned {resp.status}: {text[:200]}")
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
