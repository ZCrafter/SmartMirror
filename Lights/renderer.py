def blank(count):
    return [(0,0,0) for _ in range(count)]

def temp_to_led(temp,left_leds=217):
    temp=max(0,min(100,temp))
    return int((temp/100.0)*(left_leds-1))
