import requests

class WeatherClient:
    def __init__(self,cfg):
        self.cfg=cfg
        self.headers={"Authorization":f"Bearer {cfg.HA_TOKEN}","Content-Type":"application/json"}

    def _state(self,e):
        r=requests.get(f"{self.cfg.HA_URL}/api/states/{e}",headers=self.headers,timeout=10)
        r.raise_for_status()
        return r.json()

    def current(self):
        return {
            "temp":float(self._state(self.cfg.ENTITY_TEMP)["state"]),
            "feels":float(self._state(self.cfg.ENTITY_FEELSLIKE)["state"]),
            "humidity":float(self._state(self.cfg.ENTITY_HUMIDITY)["state"])
        }

    def hourly(self):
        r=requests.post(
            f"{self.cfg.HA_URL}/api/services/weather/get_forecasts?return_response",
            headers=self.headers,
            json={"entity_id":self.cfg.ENTITY_FORECAST,"type":"hourly"},
            timeout=20)
        r.raise_for_status()
        return r.json()["service_response"][self.cfg.ENTITY_FORECAST]["forecast"]

    def daily(self):
        r=requests.post(
            f"{self.cfg.HA_URL}/api/services/weather/get_forecasts?return_response",
            headers=self.headers,
            json={"entity_id":self.cfg.ENTITY_FORECAST,"type":"daily"},
            timeout=20)
        r.raise_for_status()
        return r.json()["service_response"][self.cfg.ENTITY_FORECAST]["forecast"][0]
