# -*- coding: utf-8 -*-
"""运行时环境适配：区分源码运行与 PyInstaller 打包运行，定位 ffmpeg 与资源。"""
from __future__ import annotations
import os
import shutil
import sys


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_dir() -> str:
    """exe 所在目录（打包后）或项目根目录（源码运行时）。"""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(rel: str) -> str:
    """读取只读资源（打包后位于 _MEIPASS 临时解压目录）。"""
    base = getattr(sys, "_MEIPASS", app_dir())
    return os.path.join(base, rel)


# ffmpeg 查找顺序：同级 bin/ → 同级根目录 → _MEIPASS → PATH
_FFMPEG_CACHE: dict[str, str | None] = {}


def find_tool(name: str) -> str | None:
    """定位 ffmpeg / ffprobe 可执行文件，找不到返回 None。"""
    if name in _FFMPEG_CACHE:
        return _FFMPEG_CACHE[name]
    exe = name + (".exe" if os.name == "nt" else "")

    candidates = [
        os.path.join(app_dir(), "bin", exe),
        os.path.join(app_dir(), exe),
        os.path.join(app_dir(), "ffmpeg", "bin", exe),
    ]
    if is_frozen():
        candidates.append(os.path.join(getattr(sys, "_MEIPASS", ""), exe))
        candidates.append(os.path.join(getattr(sys, "_MEIPASS", ""), "bin", exe))

    found = None
    for c in candidates:
        if c and os.path.isfile(c):
            found = c
            break
    if not found:
        found = shutil.which(name) or shutil.which(exe)
    _FFMPEG_CACHE[name] = found
    return found


def have_ffmpeg() -> bool:
    return find_tool("ffmpeg") is not None and find_tool("ffprobe") is not None


def ffmpeg_hint() -> str:
    """缺少 ffmpeg 时给用户的指引。"""
    return ("未找到 ffmpeg。图片转换功能可正常使用；音频/视频转换及 AVIF 无损输出需要 "
            "ffmpeg。请把 ffmpeg.exe 和 ffprobe.exe 放到本程序同目录的 bin 文件夹下，"
            "或将 ffmpeg 安装并加入系统 PATH。")
