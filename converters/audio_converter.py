# -*- coding: utf-8 -*-
"""音频转换器插件。无损结论经整数域逐样本实测（probe_audio2.py）。

关键坑：
1. ffmpeg 转 WAV/AIFF 默认降到 16bit —— 必须按源位深显式选 pcm_s16/24/32；
2. FLAC / ALAC 最高仅 24bit，32bit 源会被截断 —— 对 32bit 源拒绝；
3. 浮点源只有 WAV(pcm_f32le) 能无损保留。
"""
from __future__ import annotations
import os

from core.plugin_base import ConverterPlugin, OutputFormat, ConvertError
from core.ffmpeg_utils import ffprobe, get_streams, media_duration, run_ffmpeg


class AudioConverter(ConverterPlugin):
    name = "音频转换"
    category = "音频"
    input_exts = (".flac", ".wav", ".m4a", ".mp3", ".aac", ".ogg", ".opus",
                  ".aiff", ".aif", ".ape", ".wv", ".wma", ".3gp", ".amr")

    def output_formats(self) -> list[OutputFormat]:
        return [
            OutputFormat("flac", "FLAC（无损，≤24bit）", ".flac", True,
                         "FLAC 最高支持 24bit；32bit 整数/浮点源将拒绝转换"),
            OutputFormat("wav", "WAV（无损，保留源位深）", ".wav", True,
                         "按源位深编码，16/24/32bit 及浮点均可无损保留"),
            OutputFormat("alac", "ALAC / m4a（无损，≤24bit）", ".m4a", True,
                         "ALAC 最高支持 24bit；32bit 整数/浮点源将拒绝转换"),
            OutputFormat("aiff", "AIFF（无损，保留源位深）", ".aiff", True,
                         "按源位深编码；浮点源将拒绝转换"),
            OutputFormat("mp3", "MP3（320kbps，⚠️有损）", ".mp3", False,
                         "MP3 为有损格式，320kbps 已是最高码率"),
            OutputFormat("aac", "AAC / m4a（320kbps，⚠️有损）", ".m4a", False),
            OutputFormat("ogg", "OGG Vorbis（q10，⚠️有损）", ".ogg", False),
            OutputFormat("opus", "Opus（256kbps，⚠️有损）", ".opus", False,
                         "Opus 为有损格式；256kbps 接近其透明音质上限"),
        ]

    # -- 源格式分析 --
    @staticmethod
    def _source_kind(path: str) -> tuple[str, int | None]:
        """返回 ('int', bits) / ('float', None)。"""
        info = ffprobe(path)
        streams = get_streams(info, "audio")
        if not streams:
            raise ConvertError("文件中没有音频流。")
        s = streams[0]
        sfmt = (s.get("sample_fmt") or "").lower()
        if sfmt.startswith(("flt", "dbl")):
            return "float", None
        # 位深：优先 raw bits，其次 sample_fmt 推断
        raw = s.get("bits_per_raw_sample")
        try:
            if raw and raw != "0":
                return "int", int(raw)
        except ValueError:
            pass
        bps = s.get("bits_per_sample")
        try:
            if bps:
                return "int", int(bps)
        except (TypeError, ValueError):
            pass
        table = {"s16": 16, "s24": 24, "s32": 32, "s8": 8}
        for k, v in table.items():
            if sfmt.startswith(k):
                return "int", v
        return "int", 16   # 未知按 16 处理（最保守）

    def convert(self, src, dst, fmt: OutputFormat, progress, is_cancelled):
        if not os.path.exists(src):
            raise ConvertError(f"文件不存在：{src}")
        info = ffprobe(src)
        duration = media_duration(info)
        kind, bits = self._source_kind(src)
        key = fmt.key

        # -- 无损目标的合法性检查 --
        if key in ("flac", "alac"):
            if kind == "float":
                raise ConvertError(
                    f"{key.upper()} 不支持浮点音频，转换会量化为整数——已拒绝。"
                    f"请改选 WAV（pcm_f32le）。")
            if bits and bits > 24:
                raise ConvertError(
                    f"源为 {bits}bit，{key.upper()} 最高仅支持 24bit，转换会丢失精度"
                    f"——已拒绝。请改选 WAV / AIFF。")
        if key == "aiff" and kind == "float":
            raise ConvertError(
                "AIFF 无可靠的浮点 PCM 支持，转换会损失信息——已拒绝。请改选 WAV。")

        # -- 组装编码参数 --
        args: list[str]
        if key == "flac":
            args = ["-c:a", "flac"]
        elif key == "wav":
            if kind == "float":
                args = ["-c:a", "pcm_f32le"]
            else:
                args = ["-c:a", {16: "pcm_s16le", 24: "pcm_s24le",
                                  32: "pcm_s32le", 8: "pcm_s8"}.get(bits, "pcm_s16le")]
        elif key == "alac":
            args = ["-c:a", "alac"]
        elif key == "aiff":
            args = ["-c:a", {16: "pcm_s16be", 24: "pcm_s24be",
                              32: "pcm_s32be", 8: "pcm_s8"}.get(bits, "pcm_s16be")]
        elif key == "mp3":
            args = ["-c:a", "libmp3lame", "-q:a", "0", "-b:a", "320k"]
        elif key == "aac":
            args = ["-c:a", "aac", "-b:a", "320k"]
        elif key == "ogg":
            args = ["-c:a", "libvorbis", "-q:a", "10"]
        elif key == "opus":
            args = ["-c:a", "libopus", "-b:a", "256k", "-vbr", "on"]
        else:
            raise ConvertError(f"未知目标格式：{key}")

        cmd = ["ffmpeg", "-y", "-i", src, *args, dst]
        run_ffmpeg(cmd, duration, progress, is_cancelled)
        if not os.path.exists(dst):
            raise ConvertError("转换结束但未生成文件。")
        progress(1.0)
