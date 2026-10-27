# -*- coding: utf-8 -*-
"""转换器插件基类与注册表。插件式架构，后续音频/视频/文档转换器各写一个插件即可。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable

ProgressCB = Callable[[float], None]  # 0.0~1.0
CancelCB = Callable[[], bool]


@dataclass
class OutputFormat:
    key: str                 # 内部标识，如 "png"
    label: str               # GUI 显示，如 "PNG（无损）"
    ext: str                 # 输出扩展名（带点，小写），如 ".png"
    lossless: bool
    note: str = ""           # 限制说明，如 "不支持透明通道"


@dataclass
class ConvertError(Exception):
    """转换器抛出的业务错误：信息可直接展示给用户。"""
    message: str
    def __str__(self) -> str:
        return self.message


class ConverterPlugin:
    """所有转换器插件的基类。"""
    name: str = "未命名转换器"
    category: str = "其他"
    input_exts: tuple[str, ...] = ()

    def output_formats(self) -> list[OutputFormat]:
        raise NotImplementedError

    def convert(self, src: str, dst: str, fmt: OutputFormat,
                progress: ProgressCB, is_cancelled: CancelCB) -> None:
        """把 src 转成 dst（dst 已含目标扩展名）。失败抛 ConvertError。"""
        raise NotImplementedError

    # -- 辅助 --
    def supports(self, path: str) -> bool:
        return path.lower().endswith(self.input_exts)


REGISTRY: dict[str, ConverterPlugin] = {}

def register(plugin: ConverterPlugin) -> ConverterPlugin:
    REGISTRY[plugin.category] = plugin
    return plugin

def get_plugins() -> list[ConverterPlugin]:
    return list(REGISTRY.values())
