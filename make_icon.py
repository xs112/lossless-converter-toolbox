# -*- coding: utf-8 -*-
"""生成应用图标 icon.ico：紫蓝圆角底 + 白色双向转换箭头。"""
import os
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角渐变底
grad = Image.new("RGB", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / S
    r = int(0x55 + (0x7b - 0x55) * t)
    g = int(0x66 + (0x8b - 0x66) * t)
    b = int(0xe8 + (0xff - 0xe8) * t)
    gd.line([(0, y), (S, y)], fill=(r, g, b))

mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([8, 8, S-8, S-8], radius=56, fill=255)
img.paste(grad, (0, 0), mask)

d = ImageDraw.Draw(img)
W = (255, 255, 255, 255)

# 上箭头（向右）
d.line([(70, 100), (176, 100)], fill=W, width=18)
d.polygon([(176, 78), (206, 100), (176, 122)], fill=W)
# 下箭头（向左）
d.line([(80, 156), (186, 156)], fill=W, width=18)
d.polygon([(80, 134), (50, 156), (80, 178)], fill=W)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
img.save(out, sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print("icon saved:", out, os.path.getsize(out), "bytes")
