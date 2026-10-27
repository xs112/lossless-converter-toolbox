# -*- coding: utf-8 -*-
"""图片转换器插件。无损参数均经像素往返实测（见 probe_formats*.py）。"""
from __future__ import annotations
import os
import subprocess
import tempfile

from PIL import Image
import pillow_heif

from core.plugin_base import ConverterPlugin, OutputFormat, ConvertError
from core.runtime import find_tool

pillow_heif.register_heif_opener()


def _ffmpeg_available() -> bool:
    return find_tool("ffmpeg") is not None


class ImageConverter(ConverterPlugin):
    name = "图片转换"
    category = "图片"
    input_exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
                  ".jp2", ".j2k", ".heic", ".heif", ".avif", ".gif")

    def output_formats(self) -> list[OutputFormat]:
        fmts = [
            OutputFormat("png", "PNG（无损）", ".png", True),
            OutputFormat("tiff", "TIFF / LZW（无损）", ".tif", True),
            OutputFormat("webp", "WebP（无损，体积更小）", ".webp", True),
            OutputFormat("jp2", "JPEG2000（无损）", ".jp2", True),
            OutputFormat("bmp", "BMP（无损，不支持透明）", ".bmp", True,
                         "源图含透明通道时将拒绝转换"),
        ]
        if _ffmpeg_available():
            fmts.append(OutputFormat(
                "avif", "AVIF（无损，需 ffmpeg，不支持透明）", ".avif", True,
                "经 ffmpeg libaom-av1 crf0 编码；源图含透明通道时将拒绝转换"))
        fmts += [
            OutputFormat("jpg", "JPEG（质量 100，⚠️有损）", ".jpg", False,
                         "JPEG 无无损模式；透明通道将被丢弃"),
            OutputFormat("heic", "HEIC（最高质量，⚠️有损）", ".heic", False,
                         "当前编码后端无真正无损模式"),
        ]
        return fmts

    def convert(self, src, dst, fmt: OutputFormat, progress, is_cancelled):
        try:
            img = Image.open(src)
            img.load()
        except FileNotFoundError:
            raise ConvertError(f"文件不存在：{src}")
        except Exception as e:
            raise ConvertError(f"无法打开图片（可能已损坏）：{type(e).__name__}: {e}")

        has_alpha = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info)

        key = fmt.key
        if key in ("bmp", "avif") and has_alpha:
            raise ConvertError(
                f"{fmt.key.upper()} 不支持透明通道，转换会丢失透明度——已拒绝。"
                f"请改选 PNG / WebP / TIFF。")

        save_kwargs: dict = {}
        exif = img.info.get("exif")
        if exif:
            save_kwargs["exif"] = exif

        try:
            if key == "png":
                img.save(dst, format="PNG", compress_level=6, **save_kwargs)

            elif key == "tiff":
                img.save(dst, format="TIFF", compression="tiff_lzw", **save_kwargs)

            elif key == "webp":
                # 坑：带 alpha 时必须 exact=True，否则透明像素的 RGB 被清零
                out_img = img
                if out_img.mode not in ("RGB", "RGBA", "L", "LA"):
                    out_img = out_img.convert("RGBA" if has_alpha else "RGB")
                out_img.save(dst, format="WEBP", lossless=True, quality=100,
                             exact=True, method=6, **save_kwargs)

            elif key == "jp2":
                out_img = img
                if out_img.mode not in ("RGB", "RGBA", "L", "LA", "I"):
                    out_img = out_img.convert("RGBA" if has_alpha else "RGB")
                # Pillow 的保存键是 JPEG2000，不是 JP2
                out_img.save(dst, format="JPEG2000", lossless=True)

            elif key == "bmp":
                out_img = img if img.mode in ("RGB", "L", "1", "I;16") else img.convert("RGB")
                out_img.save(dst, format="BMP")

            elif key == "jpg":
                out_img = img
                if out_img.mode != "RGB":
                    bg = Image.new("RGB", out_img.size, (255, 255, 255))
                    if out_img.mode in ("RGBA", "LA", "P"):
                        rgba = out_img.convert("RGBA")
                        bg.paste(rgba, mask=rgba.split()[-1])
                        out_img = bg
                    else:
                        out_img = out_img.convert("RGB")
                out_img.save(dst, format="JPEG", quality=100, subsampling=0,
                             **save_kwargs)

            elif key == "heic":
                out_img = img if img.mode in ("RGB", "RGBA") else \
                    img.convert("RGBA" if has_alpha else "RGB")
                out_img.save(dst, format="HEIF", quality=100, chroma=444)

            elif key == "avif":
                self._convert_avif(img, dst)

            else:
                raise ConvertError(f"未知目标格式：{key}")
        except ConvertError:
            raise
        except Exception as e:
            raise ConvertError(f"保存失败：{type(e).__name__}: {e}")

        progress(1.0)

    @staticmethod
    def _convert_avif(img: Image.Image, dst: str):
        """经 ffmpeg libaom-av1 crf0 实现真正无损（pillow_heif 无损实测不生效）。"""
        out_img = img if img.mode in ("RGB", "L") else img.convert("RGB")
        with tempfile.TemporaryDirectory() as td:
            tmp_png = os.path.join(td, "_src.png")
            out_img.save(tmp_png, format="PNG")
            cmd = [find_tool("ffmpeg") or "ffmpeg", "-y", "-i", tmp_png,
                   "-c:v", "libaom-av1",
                   "-still-picture", "1", "-crf", "0", "-f", "avif", dst]
            p = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if p.returncode != 0 or not os.path.exists(dst):
                tail = (p.stderr or "").strip().splitlines()
                raise ConvertError(
                    "ffmpeg AVIF 编码失败：" + (tail[-1][:150] if tail else "未知错误"))
