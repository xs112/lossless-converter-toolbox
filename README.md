# 无损转换工具箱 · Lossless Converter Toolbox

一个把「无损」当硬性标准的文件格式转换工具栏，支持图片、音频、视频三大类共 23 种目标格式。桌面 GUI，拖拽批量转换。

> 所有标注为「无损」的转换，都经过**逐像素 / 逐样本 / 逐字节的自动化实测验证**，而非根据文档推测。做不到无损的场景，程序会**拒绝转换并说明原因**，绝不静默降级。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## 为什么需要它

大部分格式转换工具会把文件「悄悄」弄坏：

- 图片转 BMP 时丢掉透明通道
- 音频转 FLAC 时把 32bit 截成 16bit
- 视频换个容器结果整个重编码一遍，画质掉一轮

这个工具对每一种转换都先实测验证，做不到真无损就**直接拒绝**，而不是给你一个看起来成功、实际已损坏的文件。

## 功能

### 图片

| 目标格式 | 无损 | 说明 |
|---|:---:|---|
| PNG | ✅ | |
| TIFF (LZW) | ✅ | |
| WebP | ✅ | 带透明通道强制 `exact=True`，否则透明像素 RGB 被清零（伪装无损） |
| JPEG2000 | ✅ | |
| BMP | ✅ | 不支持透明；含 alpha 的源拒绝转换 |
| AVIF | ✅ | ffmpeg libaom `-crf 0`；不支持透明 |
| JPEG | ⚠️ | 质量 100，JPEG 本身无无损模式 |
| HEIC | ⚠️ | 质量 100 / chroma 444，当前后端无真正无损模式 |

### 音频

| 目标格式 | 无损 | 说明 |
|---|:---:|---|
| FLAC | ✅ | 最高 24bit；32bit / 浮点源拒绝 |
| WAV | ✅ | 按源位深显式编码（16/24/32bit、浮点） |
| ALAC (m4a) | ✅ | 最高 24bit；32bit / 浮点源拒绝 |
| AIFF | ✅ | 大端 PCM，按源位深 |
| MP3 / AAC / OGG / Opus | ⚠️ | 有损，提供最高质量档 |

### 视频

| 目标格式 | 无损 | 说明 |
|---|:---:|---|
| MKV / MP4 / WebM 换封装 | ✅ | `-c copy` 流复制，编码裸流逐字节不变；容器不兼容时拒绝 |
| MKV / FFV1 | ✅ | 重编码但逐像素保留源画面，音频转 FLAC |
| H.264 / H.265 / VP9 CRF | ⚠️ | 高质量有损 |

## 使用

### 方式一：直接下载 exe

从 [Releases](../../releases) 下载，解压后双击 `无损转换工具箱.exe`。

```
无损转换工具箱.exe
bin/
  ffmpeg.exe
  ffprobe.exe
```

保留 `bin/` 文件夹。删除后图片转换仍可用，音视频会提示缺少 ffmpeg。

### 方式二：从源码运行

```bash
pip install -r requirements.txt
python app.py
```

需要系统已安装 `ffmpeg` 与 `ffprobe`（用于音视频转换和 AVIF 输出）。

### 自己打包

```bash
python make_icon.py                   # 生成图标（可选）
python build_exe.py                   # 单文件 exe，约 37MB
python build_exe.py --embed-ffmpeg    # 内置 ffmpeg，约 350MB
```

ffmpeg 查找顺序：`bin/` → exe 同级 → `ffmpeg/bin/` → 系统 PATH。

## 实测验证

项目自带完整测试，每条「无损」结论都有对应的自动化证据：

| 测试 | 项数 | 验证方式 |
|---|---:|---|
| `test_converter.py` | 18 | 图片转出后逐像素比对 |
| `test_audio.py` | 30 | 解码到整数域逐样本比对，含位深/浮点拒绝逻辑 |
| `test_video.py` | 15 | 流复制后编码裸流逐字节比对；FFV1 解码帧逐像素比对 |
| `test_gui.py` | — | 三类切换、卡片渲染、输入拦截 |
| `test_chips_flow.py` | — | 格式按钮流式换行不溢出（含最小窗口） |
| `selftest_exe.py` | 9 | **打包后 exe 环境**内的资源与真实转换自检 |

```bash
python test_converter.py && python test_audio.py && python test_video.py
```

## 技术要点

几个踩过并写进代码的坑：

- **WebP 透明通道**：`lossless=True` 不够，必须同时 `exact=True`，否则完全透明的像素 RGB 会被清零，解码回来颜色就变了。
- **ffmpeg 转 WAV 默认降 16bit**：必须按源位深显式指定 `pcm_s16le/s24le/s32le`，否则 24bit 母带转出来就是 16bit。
- **FLAC / ALAC 上限 24bit**：32bit 源会被截掉低 8 位，所以对这类源直接拒绝而不是转换。
- **AVIF 无损**：pillow_heif 的 `enc_params={"lossless":"1"}` 实测不生效，只有 ffmpeg `libaom-av1 -crf 0` 才是真无损。
- **视频容器兼容性**：不做静态编码对照表（极易过期），而是在临时目录实际跑一次流复制，muxer 拒绝就判定不兼容。
- **JPEG2000 保存键**：Pillow 用的是 `JPEG2000` 而非 `JP2`，拼错直接 KeyError。
- **PyInstaller 打包**：必须收集 `customtkinter` 数据文件和 `tkinterdnd2` 的 tkdnd 原生库，否则主题消失或拖拽崩溃。

## 项目结构

```
core/plugin_base.py    ConverterPlugin 基类 + OutputFormat + 注册表
core/engine.py         批量任务、后台线程、取消、输出去重（绝不覆盖）
core/ffmpeg_utils.py   ffprobe 探测 + ffmpeg 进度解析
core/runtime.py        冻结/源码双环境路径解析、ffmpeg 定位
converters/            image / audio / video 三个转换插件
app.py                 卡片式 GUI（CustomTkinter + tkinterdnd2）
build_exe.py           PyInstaller 打包脚本
```

新增一类文件只需写一个插件：

```python
class DocConverter(ConverterPlugin):
    category = "文档"
    input_exts = (".docx",)

    def output_formats(self) -> list[OutputFormat]:
        return [OutputFormat("pdf", "PDF", ".pdf", True)]

    def convert(self, src, dst, fmt, progress, is_cancelled):
        ...  # 失败时 raise ConvertError("原因")
```

然后在 `app.py` 里 `register(DocConverter())`。

## 设计原则

1. **无损必须实测**，不接受「文档说是无损」；
2. **会丢信息就拒绝**，而不是静默降级；
3. **绝不覆盖**已有文件，重名自动加序号；
4. 单文件失败不影响整批。

## 许可

MIT
