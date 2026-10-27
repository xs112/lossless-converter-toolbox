# -*- coding: utf-8 -*-
"""针对打包环境的自检入口：验证 exe 内的资源、依赖与真实转换能力。

以同样 PyInstaller 方式打包成 exe 运行，确保测的是打包后的真实环境。
输出写入同目录 selftest_report.txt 并退出码标识结果。
"""
from __future__ import annotations
import os
import sys
import traceback

HERE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LOG = os.path.join(os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
                   else HERE, "selftest_report.txt")
lines: list[str] = []
fails = 0


def log(msg=""):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(str(msg).encode("gbk", "replace").decode("gbk"))
    lines.append(str(msg))


def check(name, fn):
    global fails
    try:
        detail = fn()
        log(f"[PASS] {name}" + (f" —— {detail}" if detail else ""))
    except Exception as e:
        fails += 1
        log(f"[FAIL] {name} —— {type(e).__name__}: {e}")
        lines.append(traceback.format_exc())


# 1. 是否为打包环境
def t_frozen():
    import core.runtime as rt
    assert rt.is_frozen(), "当前不是打包环境，测试无效"
    return f"app_dir={rt.app_dir()}"
check("打包环境识别", t_frozen)

# 2. customtkinter 数据文件
def t_ctk():
    import customtkinter as ctk
    roots = []
    p = os.path.dirname(ctk.__file__)
    for sub in ("assets/themes", "assets/fonts"):
        fp = os.path.join(p, sub)
        if os.path.isdir(fp):
            roots.append(f"{sub}:{len(os.listdir(fp))}项")
    assert roots, f"customtkinter 资源目录缺失: {p}"
    return ", ".join(roots)
check("customtkinter 数据文件", t_ctk)

# 3. tkinterdnd2 原生库（拖拽功能依赖）
def t_tkdnd():
    import tkinterdnd2
    base = os.path.dirname(tkinterdnd2.__file__)
    tkdnd = os.path.join(base, "tkdnd")
    assert os.path.isdir(tkdnd), f"tkdnd 目录缺失: {tkdnd}"
    variants = [d for d in os.listdir(tkdnd)
                if d.startswith(("win-x64", "win-x86"))]
    assert variants, f"缺少 Windows tkdnd 库，只有: {os.listdir(tkdnd)}"
    # 确认实际 dll 存在
    dlls = []
    for v in variants:
        vp = os.path.join(tkdnd, v)
        for f in os.listdir(vp):
            if f.endswith(".dll"):
                dlls.append(f)
    assert dlls, "tkdnd 目录内无 dll"
    return f"{variants} -> {dlls[:3]}"
check("tkdnd 原生库", t_tkdnd)

# 4. 真正创建带拖拽的窗口（会加载 tkdnd，最容易崩的一步）
def t_gui_build():
    import app as appmod
    a = appmod.App()
    for _ in range(4):
        a.update_idletasks(); a.update()
    n_fmt = len(a.formats)
    cats = [p.category for p in a.plugins]
    w, h = a.winfo_width(), a.winfo_height()
    a.destroy()
    assert n_fmt >= 7, f"格式数异常 {n_fmt}"
    assert len(cats) == 3, f"类别异常 {cats}"
    return f"窗口 {w}x{h}，类别 {cats}，当前类别 {n_fmt} 个格式"
check("GUI 构建 + 拖拽库加载", t_gui_build)

# 5. Pillow / pillow_heif 原生扩展
def t_pillow():
    from PIL import Image
    import pillow_heif
    pillow_heif.register_heif_opener()
    import numpy as np
    im = Image.fromarray(np.zeros((16, 16, 3), dtype=np.uint8), "RGB")
    return f"Pillow {Image.__version__}，pillow_heif {pillow_heif.__version__}"
check("图像库原生扩展", t_pillow)

# 6. ffmpeg 检测（打包版默认不带）
def t_ffmpeg():
    import core.runtime as rt
    f, p = rt.find_tool("ffmpeg"), rt.find_tool("ffprobe")
    if f and p:
        return f"已找到 ffmpeg={f} ffprobe={p}"
    return "未内置（图片来源可用，音视频需 bin/ 或 PATH）"
check("ffmpeg 定位", lambda: t_ffmpeg())

# 7. 真实图片转换（无损往返像素比对）
def t_image_convert():
    import tempfile
    import numpy as np
    from PIL import Image
    from converters.image_converter import ImageConverter
    tmp = tempfile.mkdtemp()
    arr = np.random.default_rng(0).integers(0, 255, (64, 64, 4), dtype=np.uint8)
    src = os.path.join(tmp, "a.png")
    Image.fromarray(arr, "RGBA").save(src)
    conv = ImageConverter()
    done = []
    for f in conv.output_formats():
        if f.key not in ("png", "webp", "tiff", "jp2", "bmp"):
            continue
        dst = os.path.join(tmp, f"o_{f.key}{f.ext}")
        try:
            conv.convert(src, dst, f, lambda x: None, lambda: False)
            a1 = np.asarray(Image.open(src))
            a2 = np.asarray(Image.open(dst).convert("RGBA"))
            assert a1.shape == a2.shape and np.array_equal(a1, a2), f"{f.key} 像素不一致"
            done.append(f.key)
        except Exception as e:
            if f.key == "bmp":   # BMP 不支持 alpha，应拒绝
                done.append("bmp(拒绝✔)")
            else:
                raise
    return "无损通过: " + ",".join(done)
check("图片无损转换", t_image_convert)

# 8. 真实音频转换（若 ffmpeg 可用）
def t_audio():
    import core.runtime as rt
    if not rt.have_ffmpeg():
        return "跳过（无 ffmpeg）"
    import tempfile, subprocess
    import numpy as np
    from converters.audio_converter import AudioConverter
    tmp = tempfile.mkdtemp()
    SR = 8000
    sig = (np.sin(2*np.pi*440*np.linspace(0, 1, SR, endpoint=False)) * 20000
           ).astype("<i2")
    src = os.path.join(tmp, "a.wav")
    subprocess.run([rt.find_tool("ffmpeg"), "-y", "-f", "s16le", "-ar", str(SR),
                    "-ac", "1", "-i", "-", "-c:a", "pcm_s16le", src],
                   input=sig.tobytes(), capture_output=True)
    conv = AudioConverter()
    out = os.path.join(tmp, "a.flac")
    conv.convert(src, out, {f.key: f for f in conv.output_formats()}["flac"],
                 lambda x: None, lambda: False)
    dec = subprocess.run([rt.find_tool("ffmpeg"), "-i", out, "-f", "s16le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    same = np.array_equal(np.frombuffer(dec.stdout, "<i2"), sig)
    assert same, "FLAC 逐样本不一致"
    return "WAV→FLAC 逐样本一致"
check("音频无损转换", t_audio)

# 9. 真实视频流复制（若 ffmpeg 可用）
def t_video():
    import core.runtime as rt
    if not rt.have_ffmpeg():
        return "跳过（无 ffmpeg）"
    import tempfile, subprocess
    from converters.video_converter import VideoConverter
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "v.mp4")
    subprocess.run([rt.find_tool("ffmpeg"), "-y", "-f", "lavfi", "-i",
                    "testsrc=size=128x96:rate=10:duration=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", src],
                   capture_output=True)
    conv = VideoConverter()
    out = os.path.join(tmp, "v.mkv")
    conv.convert(src, out, {f.key: f for f in conv.output_formats()}["mkv-copy"],
                 lambda x: None, lambda: False)
    def raw(p):
        return subprocess.run([rt.find_tool("ffmpeg"), "-i", p, "-map", "0:v:0",
                               "-c", "copy", "-f", "data", "-"],
                              capture_output=True).stdout
    assert raw(src) == raw(out), "流复制后编码裸流不一致"
    return "MP4→MKV 流复制裸流逐字节一致"
check("视频无损流复制", t_video)

log()
log("=" * 60)
log(f"结果：{'全部通过 ✅' if fails == 0 else str(fails) + ' 项失败 🔴'}")
with open(LOG, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
sys.exit(0 if fails == 0 else 1)
