# -*- coding: utf-8 -*-
"""转换引擎：批量任务、后台线程、取消、输出路径去重。"""
from __future__ import annotations
import os
import threading
from dataclasses import dataclass, field
from typing import Callable

from .plugin_base import ConverterPlugin, OutputFormat, ConvertError

# 任务状态
WAITING = "等待"
RUNNING = "转换中"
DONE = "完成"
FAILED = "失败"
SKIPPED = "跳过"


@dataclass
class Task:
    src: str
    status: str = WAITING
    message: str = ""
    dst: str = ""


@dataclass
class EngineCallbacks:
    on_task_status: Callable[[int, str, str], None] = lambda i, s, m: None
    on_progress: Callable[[float], None] = lambda f: None   # 整体进度 0~1
    on_finish: Callable[[int, int], None] = lambda ok, fail: None


def unique_dst(directory: str, stem: str, ext: str) -> str:
    """目录内重名自动加 _1/_2，绝不覆盖已有文件。"""
    base = os.path.join(directory, stem + ext)
    if not os.path.exists(base):
        return base
    i = 1
    while True:
        p = os.path.join(directory, f"{stem}_{i}{ext}")
        if not os.path.exists(p):
            return p
        i += 1


class Engine:
    def __init__(self):
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def cancel(self) -> None:
        self._cancel.set()

    def start(self, tasks: list[Task], plugin: ConverterPlugin,
              fmt: OutputFormat, out_dir: str | None, cb: EngineCallbacks) -> None:
        if self.running:
            return
        self._cancel.clear()
        self._thread = threading.Thread(
            target=self._run, args=(tasks, plugin, fmt, out_dir, cb), daemon=True)
        self._thread.start()

    def _run(self, tasks, plugin, fmt, out_dir, cb: EngineCallbacks):
        ok = fail = 0
        total = len(tasks)
        for idx, task in enumerate(tasks):
            if self._cancel.is_set():
                cb.on_task_status(idx, SKIPPED, "已取消")
                fail += 1
                continue
            cb.on_task_status(idx, RUNNING, "")
            directory = out_dir or os.path.dirname(task.src)
            try:
                os.makedirs(directory, exist_ok=True)
                dst = unique_dst(directory, os.path.splitext(
                    os.path.basename(task.src))[0], fmt.ext)

                def prog(f, _idx=idx):
                    overall = (idx + f) / total
                    cb.on_progress(min(max(overall, 0.0), 1.0))

                plugin.convert(task.src, dst, fmt, prog, self._cancel.is_set)
                task.dst = dst
                task.status = DONE
                size_kb = os.path.getsize(dst) / 1024
                cb.on_task_status(idx, DONE, f"→ {os.path.basename(dst)}（{size_kb:.0f} KB）")
                ok += 1
            except ConvertError as e:
                task.status = FAILED
                task.message = str(e)
                cb.on_task_status(idx, FAILED, str(e))
                fail += 1
            except Exception as e:   # 兜底，绝不因一个文件中断整批
                task.status = FAILED
                msg = f"{type(e).__name__}: {e}"
                task.message = msg
                cb.on_task_status(idx, FAILED, msg)
                fail += 1
            cb.on_progress((idx + 1) / total)
        cb.on_finish(ok, fail)
