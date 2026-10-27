# -*- coding: utf-8 -*-
"""ffmpeg / ffprobe 公共助手：探测流信息、带进度解析的转码。"""
from __future__ import annotations
import json
import re
import subprocess
from typing import Callable

from core.plugin_base import ConvertError
from core.runtime import find_tool

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


def _tool(name: str) -> str:
    path = find_tool(name)
    if not path:
        missing = []
        if not find_tool("ffmpeg"):
            missing.append("ffmpeg.exe")
        if not find_tool("ffprobe"):
            missing.append("ffprobe.exe")
        miss = "、".join(missing) if missing else name
        raise ConvertError(
            f"缺少 {miss}。音频/视频转换需要 ffmpeg 与 ffprobe 两个程序，"
            f"请把二者一起放到本程序同目录的 bin 文件夹，或加入系统 PATH。")
    return path


def ffprobe(path: str) -> dict:
    """返回容器/流信息。失败抛 ConvertError。"""
    p = subprocess.run(
        [_tool("ffprobe"), "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", path],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if p.returncode != 0:
        raise ConvertError(f"ffprobe 无法识别文件（可能损坏或缺少解码器）：{path}")
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        raise ConvertError("ffprobe 输出解析失败。")


def media_duration(info: dict) -> float:
    dur = info.get("format", {}).get("duration")
    try:
        return max(float(dur), 0.001)
    except (TypeError, ValueError):
        for s in info.get("streams", []):
            try:
                return max(float(s.get("duration", 0)), 0.001)
            except (TypeError, ValueError):
                continue
    return 0.0


def get_streams(info: dict, codec_type: str) -> list[dict]:
    return [s for s in info.get("streams", []) if s.get("codec_type") == codec_type]


def run_ffmpeg(cmd: list[str], duration: float | None,
               progress: Callable[[float], None] | None,
               is_cancelled: Callable[[], bool] | None) -> None:
    """运行 ffmpeg，解析 stderr 的 time= 转进度。失败抛 ConvertError。"""
    proc = subprocess.Popen([_tool("ffmpeg"), *cmd[1:]], stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    last = 0.0
    try:
        assert proc.stderr is not None
        for line in proc.stderr:
            if is_cancelled and is_cancelled():
                proc.kill()
                raise ConvertError("已取消。")
            if progress and duration:
                m = _TIME_RE.search(line)
                if m:
                    t = (int(m.group(1)) * 3600 + int(m.group(2)) * 60
                         + float(m.group(3)))
                    f = t / duration
                    if f >= last:
                        last = min(max(f, 0.0), 1.0)
                        progress(last)
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    if proc.returncode != 0:
        raise ConvertError("ffmpeg 执行失败（返回码 %d）。" % proc.returncode)
