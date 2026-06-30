import requests
from config.settings import GOOGLE_API_KEY

print('Chave:', GOOGLE_API_KEY[:15], '...')

resp = requests.get('https://maps.googleapis.com/maps/api/geocode/json', params={
    'address': 'Rua Alfredo Lopes 1028, Sao Carlos, SP, Brasil',
    'key': GOOGLE_API_KEY,
    'region': 'br',
    'language': 'pt-BR'
}, timeout=10)

data = resp.json()
print('Status HTTP:', resp.status_code)
print('Status API:', data.get('status'))
print('Error message:', data.get('error_message', 'nenhum'))
if data.get('results'):
    loc = data['results'][0]['geometry']['location']
    print('Coordenada:', loc)
else:
    print('Sem resultados')