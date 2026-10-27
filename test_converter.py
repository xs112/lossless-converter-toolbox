# -*- coding: utf-8 -*-
"""端到端验证：对 ImageConverter 每个目标格式做真实转换并像素校验。"""
import os, sys, tempfile
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converters.image_converter import ImageConverter
from core.plugin_base import ConvertError

tmp = tempfile.mkdtemp()

# 1) RGB 源（随机噪声，最难压缩）
rgb = Image.fromarray(np.random.default_rng(0).integers(0, 255, (128, 128, 3), dtype=np.uint8), "RGB")
rgb_path = os.path.join(tmp, "rgb.png"); rgb.save(rgb_path)

# 2) RGBA 源（含半透明）
a = np.random.default_rng(1).integers(0, 255, (128, 128, 4), dtype=np.uint8)
rgba = Image.fromarray(a, "RGBA")
rgba_path = os.path.join(tmp, "rgba.png"); rgba.save(rgba_path)

conv = ImageConverter()
results = []

def pixel_equal(p1, p2):
    i1, i2 = Image.open(p1), Image.open(p2); i1.load(); i2.load()
    return i1.mode, i2.mode, np.array_equal(np.asarray(i1), np.asarray(i2))

for fmt in conv.output_formats():
    # RGB 源
    dst = os.path.join(tmp, f"out_rgb.{fmt.key}")
    if os.path.exists(dst): os.remove(dst)
    try:
        conv.convert(rgb_path, dst, fmt, lambda f: None, lambda: False)
        m1, m2, eq = pixel_equal(rgb_path, dst)
        ok = eq if fmt.lossless else os.path.exists(dst)
        tag = "像素完全一致" if eq else f"有损输出({m1}->{m2})"
        results.append((fmt.key, "RGB", "✅" if ok else "🔴", tag))
    except ConvertError as e:
        results.append((fmt.key, "RGB", "🔴", f"意外拒绝: {e}"))

    # RGBA 源
    dst2 = os.path.join(tmp, f"out_rgba.{fmt.key}")
    if os.path.exists(dst2): os.remove(dst2)
    try:
        conv.convert(rgba_path, dst2, fmt, lambda f: None, lambda: False)
        if fmt.key in ("bmp", "avif"):
            results.append((fmt.key, "RGBA", "🔴", "应拒绝透明源却通过了"))
        else:
            m1, m2, eq = pixel_equal(rgba_path, dst2)
            if fmt.lossless:
                results.append((fmt.key, "RGBA", "✅" if eq else "🔴",
                                "像素一致" if eq else f"无损但像素不一致 {m1}->{m2}"))
            else:
                results.append((fmt.key, "RGBA", "✅", f"有损输出 {m1}->{m2}"))
    except ConvertError as e:
        if fmt.key in ("bmp", "avif"):
            results.append((fmt.key, "RGBA", "✅", f"正确拒绝: {str(e)[:40]}…"))
        else:
            results.append((fmt.key, "RGBA", "🔴", f"意外拒绝: {e}"))

# 取消功能
dst3 = os.path.join(tmp, "cancel.webp")
conv.convert(rgb_path, dst3, conv.output_formats()[2], lambda f: None, lambda: True)
results.append(("cancel", "-", "ℹ️", "转换器不主动检查取消（单文件瞬时完成），取消在任务级生效"))

# 损坏文件
bad = os.path.join(tmp, "bad.png")
with open(bad, "wb") as f: f.write(b"not an image")
try:
    conv.convert(bad, os.path.join(tmp, "x.png"), conv.output_formats()[0],
                 lambda f: None, lambda: False)
    results.append(("corrupt", "-", "🔴", "损坏文件未报错"))
except ConvertError:
    results.append(("corrupt", "-", "✅", "正确报告无法打开"))

print(f"{'格式':7s} {'源':4s} 结果  说明")
print("-" * 70)
fails = 0
for k, src, r, note in results:
    print(f"{k:7s} {src:4s} {r}  {note}")
    if r == "🔴": fails += 1
print("-" * 70)
print(f"共 {len(results)} 项，{'全部通过 ✅' if fails==0 else f'{fails} 项失败 🔴'}")
sys.exit(1 if fails else 0)
