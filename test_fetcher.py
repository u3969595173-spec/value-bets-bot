import asyncio
from data.odds_api import OddsFetcher

async def test():
    fetcher = OddsFetcher(api_key='6602a394f8334728af282aee71d7849c')
    print(f'API Key set: {fetcher.api_key[:10]}...')
    events = await fetcher.fetch_odds(['basketball_nba'])
    print(f'Fetched: {len(events)} events')

asyncio.run(test())
