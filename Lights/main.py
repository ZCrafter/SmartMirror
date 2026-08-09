import time
from config import *
from weather import get_weather
from renderer import blank,temp_to_led

print('Starting smart mirror...')

while True:
    try:
        w=get_weather()
        print('='*50)
        print('Temp',w['temp'])
        print('Feels',w['feels'])
        print('Humidity',w['humidity'])
        print('Daily',w['daily'])
        print('Temp LED',temp_to_led(w['temp']))
        print('Feels LED',temp_to_led(w['feels']))
        print('='*50)
    except Exception as e:
        print('ERROR',e)

    time.sleep(300)
