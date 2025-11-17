import requests

sports = [
    'basketball_nba',
    'soccer_epl',
    'soccer_spain_la_liga',
    'soccer_germany_bundesliga',
    'soccer_italy_serie_a',
    'soccer_france_ligue_one',
    'tennis_atp',
    'tennis_wta'
]

print('Verificando eventos disponibles:\n')
total = 0

for sport in sports:
    url = f'https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey=93ca4bd31056e6b903cd7d4cec156de5&regions=us&markets=h2h'
    r = requests.get(url)
    
    if r.status_code == 200:
        events = r.json()
        count = len(events)
        total += count
        status = '✅' if count > 0 else '❌'
        print(f'{status} {sport}: {count} eventos')
    else:
        print(f'❌ {sport}: Error {r.status_code}')

print(f'\n📊 Total eventos: {total}')
print(f'🔄 Requests restantes: {r.headers.get("x-requests-remaining", "N/A")}')
