# -*- coding: utf-8 -*-
"""
打包为单文件 exe。

用法：
    python build_exe.py            # 不含 ffmpeg，产物约 60MB，图片功能完整
    python build_exe.py --embed-ffmpeg   # 内置 ffmpeg，产物约 350MB，音视频开箱即用

关键：
- customtkinter 需要收集数据文件（themes/assets）；
- tkinterdnd2 需要收集 tkdnd 原生库，否则拖拽会崩；
- ffmpeg 默认不打包，运行时从 exe 同级 bin/ 或 PATH 查找。
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
import sysconfig

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "无损转换工具箱"


def pkg_path(pkg: str) -> str:
    import importlib.util
    spec = importlib.util.find_spec(pkg)
    if not spec or not spec.origin:
        raise SystemExit(f"找不到包：{pkg}")
    return os.path.dirname(spec.origin)


def main() -> int:
    embed = "--embed-ffmpeg" in sys.argv
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", NAME,
        # customtkinter 数据文件
        "--collect-data", "customtkinter",
        # pillow_heif 原生扩展
        "--collect-binaries", "pillow_heif",
        "--collect-submodules", "PIL",
        # tkinterdnd2 的 tkdnd 原生库 + python 文件
        "--collect-all", "tkinterdnd2",
        # 隐式导入
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "pillow_heif",
        "--exclude-module", "numpy.f2py",
        "--exclude-module", "matplotlib",
    ]

    if embed:
        ff = shutil.which("ffmpeg")
        fp = shutil.which("ffprobe")
        if not ff or not fp:
            raise SystemExit("未找到 ffmpeg/ffprobe，无法内置。")
        sep = ";" if os.name == "nt" else ":"
        args += ["--add-binary", f"{ff}{sep}."]
        args += ["--add-binary", f"{fp}{sep}."]
        print("内置 ffmpeg：", ff)

    icon = os.path.join(ROOT, "icon.ico")
    if os.path.exists(icon):
        args += ["--icon", icon]

    args.append(os.path.join(ROOT, "app.py"))
    print("执行：", " ".join(args[:8]), "...")
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode != 0:
        return r.returncode

    dist = os.path.join(ROOT, "dist", NAME + ".exe")
    print("\n产物：", dist)
    if os.path.exists(dist):
        print(f"体积：{os.path.getsize(dist)/1024/1024:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
