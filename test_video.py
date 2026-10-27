# -*- coding: utf-8 -*-
"""视频转换器端到端验证。

- 流复制：多容器兼容矩阵 + 编码裸流逐字节一致性（证明确实零重编码）；
- FFV1：解码帧逐像素一致；
- 有损档：文件可生成可解码。
"""
import os, sys, subprocess, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converters.video_converter import VideoConverter
from core.plugin_base import ConvertError

tmp = tempfile.mkdtemp()
conv = VideoConverter()
results = []

# 1) 生成 1 秒 256x144 测试源
def make_src(name, venc_args, ext, extra=None):
    out = os.path.join(tmp, name + ext)
    cmd = ["ffmpeg","-y","-f","lavfi","-i",
           "testsrc2=size=256x144:rate=24:duration=1",
           "-f","lavfi","-i","sine=frequency=440:duration=1",
           *venc_args]
    if extra: cmd += extra
    cmd += [out]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print("SOURCE GEN FAIL", name, p.stderr.splitlines()[-1][:100])
    return out

h264 = make_src("h264", ["-c:v","libx264","-crf","23","-pix_fmt","yuv420p",
                         "-c:a","aac","-b:a","96k"], ".mp4")
vp9  = make_src("vp9", ["-c:v","libvpx-vp9","-crf","30","-b:v","0",
                        "-c:a","libopus","-b:a","64k"], ".webm")
h265 = make_src("h265", ["-c:v","libx265","-crf","25","-pix_fmt","yuv420p",
                         "-c:a","aac","-b:a","96k"], ".mkv")

def raw_video(path):
    """提取解码前的编码视频裸流（证明流复制零改动）。"""
    p = subprocess.run(["ffmpeg","-i",path,"-map","0:v:0","-c","copy",
                        "-f","data","-"], capture_output=True)
    return p.stdout

def frames(path):
    """解码为 RGB 帧数组。"""
    p = subprocess.run(["ffmpeg","-i",path,"-f","rawvideo","-pix_fmt","rgb24","-"],
                       capture_output=True)
    return np.frombuffer(p.stdout, dtype=np.uint8)

fmts = {f.key: f for f in conv.output_formats()}

# 2) 流复制兼容矩阵
matrix = [
    # (源, 目标key, 期望)
    (h264, "mkv-copy", "ok"),
    (h264, "mp4-copy", "ok"),
    (h264, "webm-copy", "reject"),
    (vp9,  "mkv-copy", "ok"),
    (vp9,  "webm-copy", "ok"),
    (vp9,  "mp4-copy", "reject"),
    (h265, "mkv-copy", "ok"),
    (h265, "mp4-copy", "ok"),   # h265 能进 mp4
    (h265, "webm-copy", "reject"),
]
for src, key, expect in matrix:
    dst = os.path.join(tmp, f"m_{os.path.basename(src)}_{key}{fmts[key].ext}")
    tag = f"{os.path.splitext(os.path.basename(src))[0]}→{key}"
    try:
        conv.convert(src, dst, fmts[key], lambda f: None, lambda: False)
        if expect == "reject":
            results.append((tag, "🔴", "应拒绝却通过")); continue
        # 裸流逐字节一致
        same = raw_video(src) == raw_video(dst)
        results.append((tag, "✅" if same else "🔴",
                        "流复制成功，编码裸流逐字节一致" if same
                        else "流复制后裸流发生变化！"))
    except ConvertError as e:
        results.append((tag, "✅" if expect=="reject" else "🔴",
                        f"容器正确拒绝: {str(e)[:50]}" if expect=="reject"
                        else f"意外拒绝: {str(e)[:60]}"))

# 3) FFV1 真无损重编码：解码帧逐像素一致
for sname, src in [("h264",h264),("vp9",vp9)]:
    dst = os.path.join(tmp, f"ffv1_{sname}.mkv")
    tag = f"{sname}→ffv1"
    try:
        conv.convert(src, dst, fmts["mkv-ffv1"], lambda f: None, lambda: False)
        f1, f2 = frames(src), frames(dst)
        eq = f1.shape == f2.shape and np.array_equal(f1, f2)
        results.append((tag, "✅" if eq else "🔴",
                        f"解码帧逐像素一致（{len(f1)}B）" if eq
                        else f"帧不一致 shapes {f1.shape}/{f2.shape}"))
    except ConvertError as e:
        results.append((tag, "🔴", f"意外失败: {e}"))

# 4) 有损重编码档
for sname, src, key in [("h264",h264,"mp4-h264"),("h264",h264,"mkv-h265"),
                        ("vp9",vp9,"webm-vp9")]:
    dst = os.path.join(tmp, f"lossy_{key}{fmts[key].ext}")
    tag = f"{sname}→{key}"
    try:
        conv.convert(src, dst, fmts[key], lambda f: None, lambda: False)
        fr = frames(dst)
        ok = os.path.exists(dst) and len(fr) > 0
        results.append((tag, "✅" if ok else "🔴",
                        f"有损文件可解码（{os.path.getsize(dst)//1024}KB）"))
    except ConvertError as e:
        results.append((tag, "🔴", f"失败: {e}"))

# 5) 取消（重编码途中取消）
dst = os.path.join(tmp,"cancel.mkv")
tag = "cancel-ffv1"
try:
    conv.convert(h264, dst, fmts["mkv-ffv1"], lambda f: None, lambda: True)
    results.append((tag,"🔴","应取消却完成"))
except ConvertError:
    results.append((tag,"✅","正确响应取消"))

print(f"{'场景':22s} 结果 说明")
print("-"*80)
fails=0
for tag,r,note in results:
    print(f"{tag:22s} {r} {note}")
    if r=="🔴": fails+=1
print("-"*80)
print(f"共 {len(results)} 项，{'全部通过 ✅' if fails==0 else str(fails)+' 项失败 🔴'}")
sys.exit(1 if fails else 0)
