# -*- coding: utf-8 -*-
"""新版 GUI 冒烟测试：构建、三类切换、chips、卡片刷新、输入拦截、主题切换。"""
import os, sys, tempfile, subprocess
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod

a = appmod.App()
a.update_idletasks(); a.update()

assert len(a.plugins) == 3, f"插件数: {len(a.plugins)}"
cats = [p.category for p in a.plugins]
print("类别:", cats)
assert cats == ["图片", "音频", "视频"]

assert len(a.formats) == 8
print("图片 chips:", list(a._chip_buttons))

a._select_category(a.plugins[1]); a.update()
assert a.plugin.category == "音频"
assert len(a.formats) == 8
print("音频 chips:", list(a._chip_buttons))

a._select_category(a.plugins[2]); a.update()
assert a.plugin.category == "视频"
assert len(a.formats) == 7
print("视频 chips:", list(a._chip_buttons))

tmp = tempfile.mkdtemp()
p = os.path.join(tmp, "clip.mkv")
subprocess.run(["ffmpeg","-y","-f","lavfi","-i",
    "testsrc=size=64x48:rate=10:duration=1","-c:v","libx264",p],
    capture_output=True)
a._ingest([p]); a.update()
assert len(a.tasks) == 1
card_frames = [w for w in a.cards_frame.winfo_children()]
assert len(card_frames) >= 1

bad = os.path.join(tmp, "x.txt")
open(bad,"w").write("x")
a._ingest([bad]); a.update()
assert len(a.tasks) == 1
assert "不匹配" in a.status_label.cget("text")

a.tasks.clear(); a._refresh_cards()
a._start(); a.update()
assert "请先添加文件" in a.status_label.cget("text")

a._ingest([p])
a.out_mode.set("custom"); a._toggle_outdir()
a.outdir_entry.delete(0,"end"); a.outdir_entry.insert(0,"Z:/nope_xyz")
a._start(); a.update()
assert "输出文件夹无效" in a.status_label.cget("text")

a._pick_format(a.formats[2]); a.update()
assert a.current_fmt.key == a.formats[2].key

a._toggle_theme(); a.update()
a._toggle_theme(); a.update()

a.update_idletasks()
print("窗口:", a.winfo_width(), "x", a.winfo_height())
print("GUI 冒烟测试通过 ✅")
a.destroy()
