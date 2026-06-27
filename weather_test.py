from config import load_config
from weather import WeatherClient

cfg=load_config()
wc=WeatherClient(cfg)
print("Current:",wc.current())
print("Daily:",wc.daily())
print("Hourly:")
for h in wc.hourly()[:18]:
    print(h["datetime"],h["temperature"],h["precipitation"],h["humidity"])
