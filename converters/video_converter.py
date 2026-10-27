# -*- coding: utf-8 -*-
"""视频转换器插件。

无损分两层：
1. 换封装 / 流复制（-c copy）：不动一帧，真正无损。但目标容器必须支持源编码，
   兼容性在运行时实测（muxer 拒绝即判定不兼容），不维护易过期的静态表；
2. 真无损重编码：FFV1（逐像素保留解码后的源画面）+ FLAC 音频。
另提供 H.264/H.265/VP9 高质量 CRF 档，明确标注有损。
"""
from __future__ import annotations
import os
import tempfile
import subprocess

from core.plugin_base import ConverterPlugin, OutputFormat, ConvertError
from core.ffmpeg_utils import ffprobe, get_streams, media_duration, run_ffmpeg
from core.runtime import find_tool


# 目标容器 -> (扩展名, ffmpeg muxer 格式名, 支持的大致编码，仅用于友好报错)
_CONTAINERS = {
    "mkv": (".mkv", "matroska",
            {"video": {"h264", "hevc", "vp8", "vp9", "av1", "mpeg4",
                       "mpeg2video", "ffv1", "prores"},
             "audio": {"aac", "mp3", "ac3", "eac3", "flac", "pcm_s16le",
                       "opus", "vorbis", "alac", "dts"}}),
    "mp4": (".mp4", "mp4",
            {"video": {"h264", "hevc", "mpeg4", "av1"},
             "audio": {"aac", "mp3", "ac3", "alac"}}),
    "webm": (".webm", "webm",
             {"video": {"vp8", "vp9", "av1"},
              "audio": {"vorbis", "opus"}}),
}


class VideoConverter(ConverterPlugin):
    name = "视频转换"
    category = "视频"
    input_exts = (".mkv", ".mp4", ".mov", ".webm", ".avi", ".flv", ".ts",
                  ".m4v", ".wmv", ".mpg", ".mpeg", ".3gp", ".m2ts")

    def output_formats(self) -> list[OutputFormat]:
        return [
            OutputFormat("mkv-copy", "MKV 换封装（流复制·无损）", ".mkv", True,
                         "不重编码；源编码几乎都能进 MKV"),
            OutputFormat("mp4-copy", "MP4 换封装（流复制·无损）", ".mp4", True,
                         "不重编码；要求 H.264/H.265/AV1 + AAC/MP3 等，不兼容将拒绝"),
            OutputFormat("webm-copy", "WebM 换封装（流复制·无损）", ".webm", True,
                         "不重编码；要求 VP8/VP9/AV1 + Opus/Vorbis，不兼容将拒绝"),
            OutputFormat("mkv-ffv1", "MKV / FFV1（重编码·真无损）", ".mkv", True,
                         "逐像素保留源画面；体积可能很大，音频转 FLAC（不额外损失）"),
            OutputFormat("mp4-h264", "MP4 / H.264 CRF18（重编码·⚠️高质量有损）",
                         ".mp4", False, "CRF18 接近视觉无损但非像素无损，音频 AAC 256k"),
            OutputFormat("mkv-h265", "MKV / H.265 CRF20（重编码·⚠️高质量有损）",
                         ".mkv", False, "同画质体积更小，音频 AAC 256k"),
            OutputFormat("webm-vp9", "WebM / VP9 CRF24（重编码·⚠️高质量有损）",
                         ".webm", False, "音频 Opus 192k"),
        ]

    # ---------------- 流复制 ----------------
    def _remux(self, src, dst, container_key, info, duration, progress, is_cancelled):
        ext, muxer, support = _CONTAINERS[container_key]
        vstreams = get_streams(info, "video")
        astreams = get_streams(info, "audio")
        sstreams = get_streams(info, "subtitle")

        # 友好的预检查（最终以 muxer 实测为准）
        bad = []
        for s in vstreams:
            if s.get("codec_name") not in support["video"]:
                bad.append(f"视频编码 {s.get('codec_name')}")
        for s in astreams:
            if s.get("codec_name") not in support["audio"]:
                bad.append(f"音频编码 {s.get('codec_name')}")
        if bad and container_key != "mkv":
            raise ConvertError(
                f"目标容器不兼容源编码（{', '.join(bad)}），流复制无法无损完成——已拒绝。"
                f"请选择对应的重编码格式。")

        # MKV 保留字幕；其他容器字幕支持差，直接不映射
        maps = ["-map", "0:v?", "-map", "0:a?"]
        if container_key == "mkv":
            maps += ["-map", "0:s?"]

        # 运行时实测：先尝试复制到临时文件，成功再落到 dst
        with tempfile.TemporaryDirectory() as td:
            tmp_out = os.path.join(td, "remux" + ext)
            cmd = [find_tool("ffmpeg") or "ffmpeg", "-y", "-i", src, *maps, "-c", "copy",
                   "-f", muxer, tmp_out]
            p = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if p.returncode != 0 or not os.path.exists(tmp_out):
                tail = (p.stderr or "").strip().splitlines()
                detail = tail[-1][:130] if tail else "未知原因"
                raise ConvertError(
                    f"流复制被 {container_key.upper()} 容器拒绝（{detail}）。"
                    f"请改用重编码格式。")
            # 成功：移动到目标位置（shutil.move 支持跨盘）
            import shutil
            shutil.move(tmp_out, dst)
        progress(1.0)

    # ---------------- 重编码 ----------------
    def _transcode(self, src, dst, key, duration, progress, is_cancelled):
        if key == "mkv-ffv1":
            args = ["-c:v", "ffv1", "-level", "3", "-c:a", "flac"]
        elif key == "mp4-h264":
            args = ["-c:v", "libx264", "-crf", "18", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k"]
        elif key == "mkv-h265":
            args = ["-c:v", "libx265", "-crf", "20", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k"]
        elif key == "webm-vp9":
            args = ["-c:v", "libvpx-vp9", "-crf", "24", "-b:v", "0",
                    "-row-mt", "1", "-c:a", "libopus", "-b:a", "192k"]
        else:
            raise ConvertError(f"未知目标格式：{key}")

        cmd = ["ffmpeg", "-y", "-i", src, "-map", "0:v?", "-map", "0:a?",
               *args, dst]
        run_ffmpeg(cmd, duration, progress, is_cancelled)
        if not os.path.exists(dst):
            raise ConvertError("转码结束但未生成文件。")
        progress(1.0)

    def convert(self, src, dst, fmt: OutputFormat, progress, is_cancelled):
        if not os.path.exists(src):
            raise ConvertError(f"文件不存在：{src}")
        info = ffprobe(src)
        if not get_streams(info, "video"):
            raise ConvertError("文件中没有视频流。")
        duration = media_duration(info)

        if fmt.key.endswith("-copy"):
            container = fmt.key.split("-")[0]
            self._remux(src, dst, container, info, duration, progress, is_cancelled)
        else:
            self._transcode(src, dst, fmt.key, duration, progress, is_cancelled)
