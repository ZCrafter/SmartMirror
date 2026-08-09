from config import load_config
from wled import WLED

cfg=load_config()
w=WLED(cfg.WLED_IP,cfg.WLED_PORT)
pixels=[(0,0,0)]*cfg.TOTAL_LEDS
for i in range(cfg.LEFT_START,cfg.LEFT_END+1):
    pixels[i]=cfg.LAYOUT_LEFT_COLOR
for i in range(cfg.TOP_START,cfg.TOP_END+1):
    pixels[i]=cfg.LAYOUT_TOP_COLOR
for i in range(cfg.RIGHT_START,cfg.RIGHT_END+1):
    pixels[i]=cfg.LAYOUT_RIGHT_COLOR
print("Left",cfg.LEFT_START,cfg.LEFT_END)
print("Top",cfg.TOP_START,cfg.TOP_END)
print("Right",cfg.RIGHT_START,cfg.RIGHT_END)
w.send(pixels)
print("Frame sent.")
