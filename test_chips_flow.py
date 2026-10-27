# -*- coding: utf-8 -*-
"""确定性验证：chips 流式换行后，逐行实际宽度均 ≤ 容器宽度，无溢出。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod

a = appmod.App()
# 给 UI 几轮布局，拿到真实宽度
for _ in range(5):
    a.update_idletasks(); a.update()

def verify_category(plugin):
    a._select_category(plugin)
    for _ in range(6):
        a.update_idletasks(); a.update()
    frame_w = a.chips_frame.winfo_width()
    a._flow_chips()
    a.update_idletasks()

    # 按行收集按钮，行宽 = reqwidth 之和 + 间距
    rows: dict[int, list] = {}
    for b in a._chip_list:
        info = b.grid_info()
        r = int(info["row"])
        rows.setdefault(r, []).append(b.winfo_reqwidth())
    ok = True
    print(f"\n[{plugin.category}] 容器宽 {frame_w}px，共 {len(a._chip_list)} 个按钮，"
          f"排成 {len(rows)} 行")
    for r in sorted(rows):
        ws = rows[r]
        line_w = sum(ws) + 10 * (len(ws) - 1)   # padx 5*2 间隔
        fit = line_w <= frame_w
        ok = ok and fit
        print(f"  行{r}: {len(ws)} 个按钮，实际宽 {line_w}px "
              f"{'≤' if fit else '>'} {frame_w}  {'✅' if fit else '🔴溢出'}")
    return ok

all_ok = True
for p in a.plugins:
    all_ok = verify_category(p) and all_ok

# 缩小窗口到最小尺寸再验一次（最严苛）
a.geometry("920x600")
for _ in range(6):
    a.update_idletasks(); a.update()
frame_w = a.chips_frame.winfo_width()
a._flow_chips(); a.update_idletasks()
rows={}
for b in a._chip_list:
    rows.setdefault(int(b.grid_info()["row"]),[]).append(b.winfo_reqwidth())
min_ok=True
for r,ws in rows.items():
    lw=sum(ws)+10*(len(ws)-1)
    if lw>frame_w: min_ok=False
print(f"\n最小窗口宽 920：当前类别 chips 容器 {frame_w}px，"
      f"{'各行均不溢出 ✅' if min_ok else '存在溢出 🔴'}")

print("\n" + ("流式换行布局验证通过 ✅" if all_ok and min_ok else "存在溢出 🔴"))
a.destroy()
sys.exit(0 if (all_ok and min_ok) else 1)
