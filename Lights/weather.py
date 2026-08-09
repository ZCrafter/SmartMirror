import requests
from config import *

HEADERS={'Authorization':f'Bearer {HA_TOKEN}','Content-Type':'application/json'}

def get_state(entity):
    r=requests.get(f"{HA_URL}/api/states/{entity}",headers=HEADERS,timeout=10)
    r.raise_for_status()
    return r.json()

def get_weather():
    temp=float(get_state(ENTITY_TEMP)['state'])
    feels=float(get_state(ENTITY_FEELSLIKE)['state'])
    humidity=float(get_state(ENTITY_HUMIDITY)['state'])

    payload={
      "type":"daily"
    }
    r=requests.post(f"{HA_URL}/api/services/weather/get_forecasts",
                    headers=HEADERS,
                    json={"entity_id":ENTITY_FORECAST,"type":"daily"},
                    timeout=15)
    daily=r.json() if r.ok else {}

    return {"temp":temp,"feels":feels,"humidity":humidity,"daily":daily}
