from dotenv import load_dotenv
import os
load_dotenv()

HA_URL=os.getenv("HA_URL")
HA_TOKEN=os.getenv("HA_TOKEN")
ENTITY_TEMP=os.getenv("ENTITY_TEMP")
ENTITY_FEELSLIKE=os.getenv("ENTITY_FEELSLIKE")
ENTITY_HUMIDITY=os.getenv("ENTITY_HUMIDITY")
ENTITY_FORECAST=os.getenv("ENTITY_FORECAST")

TOTAL_LEDS=int(os.getenv("TOTAL_LEDS",554))
LEFT_LEDS=int(os.getenv("LEFT_LEDS",217))
TOP_LEDS=int(os.getenv("TOP_LEDS",120))
RIGHT_LEDS=int(os.getenv("RIGHT_LEDS",217))
FPS=int(os.getenv("FPS",20))
