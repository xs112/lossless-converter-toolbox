# -*- coding: utf-8 -*-
"""无损转换工具箱 —— 现代卡片式界面（CustomTkinter + 拖拽）。"""
from __future__ import annotations
import os
import sys
from tkinter import filedialog

import customtkinter as ctk
import tkinterdnd2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.engine import Engine, Task, EngineCallbacks
from core.engine import WAITING, RUNNING, DONE, FAILED, SKIPPED
from core.plugin_base import get_plugins, register
from converters.image_converter import ImageConverter
from converters.audio_converter import AudioConverter
from converters.video_converter import VideoConverter

register(ImageConverter())
register(AudioConverter())
register(VideoConverter())

# ---------------- 主题 ---------------- #
ACCENT = ("#5566e8", "#6b7bff")
ACCENT_SOFT = ("#eef0fe", "#262a4a")
BG = ("#f3f4fa", "#16171f")
CARD = ("#ffffff", "#1e202c")
CARD_SEL = ("#eef0fe", "#272b45")
TEXT = ("#1c1f2e", "#eef0fa")
MUTED = ("#8a8fa3", "#7d8298")
BAD_TXT = ("#d23f3f", "#ff7d7d")
WARN_TXT = ("#b97a14", "#f0b95a")

STATUS_STYLE = {
    WAITING: ("gray", "等待"),
    RUNNING: ("#3b7bef", "转换中"),
    DONE: ("#1a8a45", "完成"),
    FAILED: (BAD_TXT[0], "失败"),
    SKIPPED: ("gray", "跳过"),
}

CATEGORY_ICONS = {"图片": "🖼", "音频": "🎵", "视频": "🎬"}
BADGE_COLORS = {
    "png": ("#3fbf6f", "#2e9e57"), "jpg": ("#e0a23c", "#c98a20"),
    "jpeg": ("#e0a23c", "#c98a20"), "webp": ("#4ea8de", "#3b8ec4"),
    "tif": ("#9b7ede", "#7f60c4"), "tiff": ("#9b7ede", "#7f60c4"),
    "bmp": ("#6fb0c9", "#5590a8"), "jp2": ("#de7eb0", "#c45f90"),
    "avif": ("#58c9a8", "#3fae8e"), "heic": ("#7fd1c1", "#5fae9e"),
    "gif": ("#de9b7e", "#c47f5f"),
    "flac": ("#e8745c", "#cc563d"), "wav": ("#5ca8e8", "#3d8acc"),
    "m4a": ("#c47ede", "#a45fc4"), "alac": ("#c47ede", "#a45fc4"),
    "mp3": ("#6fd17a", "#50b55d"), "aac": ("#8fb8e8", "#6f98cc"),
    "ogg": ("#d1a86f", "#b58a4d"), "opus": ("#6fd1c4", "#4db5a6"),
    "aiff": ("#b8a0e0", "#9880c4"), "ape": ("#c46f8f", "#a44f6f"),
    "wv": ("#9bc46f", "#7da84d"), "wma": ("#7d7d7d", "#666666"),
    "mkv": ("#6f9bd1", "#4f7bb5"), "mp4": ("#d16f8f", "#b54f6f"),
    "mov": ("#c4a46f", "#a8874d"), "webm": ("#6fc49b", "#4da87d"),
    "avi": ("#b08fd1", "#906fb5"), "flv": ("#c46f6f", "#a44f4f"),
    "ts": ("#b0b06f", "#90904d"),
}


class App(tkinterdnd2.TkinterDnD.DnDWrapper, ctk.CTk):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = tkinterdnd2.TkinterDnD._require(self)

        ctk.set_appearance_mode("System")
        self.title("无损转换工具箱")
        self.geometry("1040x700")
        self.minsize(920, 600)
        self.configure(fg_color=BG)

        self.plugins = get_plugins()
        self.plugin = self.plugins[0]
        self.formats = []
        self.tasks: list[Task] = []
        self.engine = Engine()
        self._selected = -1
        self.current_fmt = None

        self._build()
        self._load_formats()
        self._refresh_cards()
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """缺少 ffmpeg 时给出明确指引，而不是转换时莫名失败。"""
        from core.runtime import have_ffmpeg, ffmpeg_hint
        if have_ffmpeg():
            self._set_status("就绪。拖入文件或点击选择，然后选格式转换。")
        else:
            self._set_status(ffmpeg_hint(), warn=True)

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self):
        side = ctk.CTkFrame(self, width=76, corner_radius=0,
                            fg_color=("#ffffff", "#12131b"))
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        side.grid_rowconfigure(20, weight=1)

        ctk.CTkLabel(side, text="◆", font=ctk.CTkFont(size=26),
                     text_color=ACCENT).grid(row=0, pady=(20, 4))
        ctk.CTkLabel(side, text="无损\n转换", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=MUTED).grid(row=1, pady=(0, 18))

        self.cat_buttons = {}
        for i, p in enumerate(self.plugins, start=2):
            b = ctk.CTkButton(
                side, text=f"{CATEGORY_ICONS.get(p.category, '📄')}\n{p.category}",
                width=58, height=54, font=ctk.CTkFont(size=11),
                fg_color="transparent", hover_color=ACCENT_SOFT,
                text_color=MUTED, command=lambda _p=p: self._select_category(_p))
            b.grid(row=i, padx=9, pady=4)
            self.cat_buttons[p.category] = b
        self._highlight_category()

        ctk.CTkButton(side, text="🌓", width=40, height=34, fg_color="transparent",
                      hover_color=ACCENT_SOFT, text_color=MUTED,
                      command=self._toggle_theme).grid(row=21, pady=14)

    def _build_main(self):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=26, pady=(20, 18))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(3, weight=1)

        head = ctk.CTkFrame(main, fg_color="transparent")
        head.grid(row=0, sticky="ew")
        ctk.CTkLabel(head, text=self._title_text(),
                     font=ctk.CTkFont(size=23, weight="bold"), text_color=TEXT
                     ).pack(side="left")
        self.file_count = ctk.CTkLabel(head, text="", text_color=MUTED,
                                       font=ctk.CTkFont(size=12))
        self.file_count.pack(side="left", padx=12, pady=(6, 0))

        self.dropzone = ctk.CTkFrame(
            main, height=118, corner_radius=16, border_width=2,
            border_color=(ACCENT[0], ACCENT[1]), fg_color=ACCENT_SOFT)
        self.dropzone.grid(row=1, sticky="ew", pady=(14, 6))
        self.dropzone.grid_propagate(False)
        inner = ctk.CTkFrame(self.dropzone, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        l1 = ctk.CTkLabel(inner, text="⬇  拖放文件到这里",
                          font=ctk.CTkFont(size=16, weight="bold"),
                          text_color=ACCENT)
        l1.pack()
        l2 = ctk.CTkLabel(inner, text="或点击选择文件 · 支持批量",
                          font=ctk.CTkFont(size=12), text_color=MUTED)
        l2.pack(pady=(3, 0))
        for w in (self.dropzone, inner, l1, l2):
            w.bind("<Button-1>", lambda e: self._add_files())

        fmt_wrap = ctk.CTkFrame(main, corner_radius=16, fg_color=CARD)
        fmt_wrap.grid(row=2, sticky="ew", pady=(6, 2))
        fmt_wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(fmt_wrap, text="目标格式",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT
                     ).grid(row=0, column=0, padx=16, pady=(12, 2), sticky="w")
        self.chips_frame = ctk.CTkFrame(fmt_wrap, fg_color="transparent")
        self.chips_frame.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="ew")
        self._chips_w = 0
        self.chips_frame.bind("<Configure>", self._on_chips_configure)
        self.fmt_note = ctk.CTkLabel(fmt_wrap, text="", text_color=WARN_TXT,
                                     font=ctk.CTkFont(size=11), anchor="w",
                                     justify="left")
        self.fmt_note.grid(row=2, column=0, padx=16, pady=(0, 10),
                           sticky="w")

        list_wrap = ctk.CTkFrame(main, corner_radius=16, fg_color=CARD)
        list_wrap.grid(row=3, sticky="nsew", pady=8)
        list_wrap.grid_columnconfigure(0, weight=1)
        list_wrap.grid_rowconfigure(0, weight=1)
        self.cards_frame = ctk.CTkScrollableFrame(
            list_wrap, fg_color="transparent", corner_radius=0)
        self.cards_frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.cards_frame.grid_columnconfigure(0, weight=1)

        for w in (self, self.cards_frame, list_wrap):
            w.drop_target_register(tkinterdnd2.DND_FILES)
            w.dnd_bind("<<Drop>>", self._on_drop)

        bottom = ctk.CTkFrame(main, corner_radius=16, fg_color=CARD)
        bottom.grid(row=4, sticky="ew", pady=(8, 0))
        bottom.grid_columnconfigure(4, weight=1)
        self.out_mode = ctk.StringVar(value="same")
        ctk.CTkRadioButton(bottom, text="源文件夹", variable=self.out_mode,
                           value="same", font=ctk.CTkFont(size=12),
                           command=self._toggle_outdir
                           ).grid(row=0, column=0, padx=(16, 6), pady=14)
        ctk.CTkRadioButton(bottom, text="自定义", variable=self.out_mode,
                           value="custom", font=ctk.CTkFont(size=12),
                           command=self._toggle_outdir
                           ).grid(row=0, column=1, padx=6)
        self.outdir_entry = ctk.CTkEntry(bottom, width=210, state="disabled",
                                         placeholder_text="选择输出文件夹")
        self.outdir_entry.grid(row=0, column=2, padx=6)
        self.browse_btn = ctk.CTkButton(bottom, text="浏览", width=56,
                                        state="disabled", command=self._choose_outdir)
        self.browse_btn.grid(row=0, column=3, padx=(0, 10))
        self.cancel_btn = ctk.CTkButton(bottom, text="取消", width=72, height=40,
                                        fg_color=("gray60", "gray35"),
                                        hover_color=("gray50", "gray30"),
                                        state="disabled", command=self._cancel)
        self.cancel_btn.grid(row=0, column=5, padx=(0, 6), pady=10)
        self.start_btn = ctk.CTkButton(
            bottom, text="开始转换  →", width=140, height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=ACCENT, hover_color=("#4455d8", "#5a6bf0"),
            command=self._start)
        self.start_btn.grid(row=0, column=6, padx=(0, 14), pady=10)

        prog_wrap = ctk.CTkFrame(main, fg_color="transparent")
        prog_wrap.grid(row=5, sticky="ew", pady=(10, 0))
        prog_wrap.grid_columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(prog_wrap, height=8, corner_radius=4,
                                           progress_color=ACCENT)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.progress.set(0)
        self.pct_label = ctk.CTkLabel(prog_wrap, text="0%", width=42,
                                      text_color=MUTED, font=ctk.CTkFont(size=12))
        self.pct_label.grid(row=0, column=1)
        self.status_label = ctk.CTkLabel(main, text="就绪。", text_color=MUTED,
                                         anchor="w", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=6, sticky="ew", pady=(6, 0))

    def _title_text(self):
        return f"{CATEGORY_ICONS.get(self.plugin.category, '📄')}  {self.plugin.category}转换"

    def _select_category(self, plugin):
        if self.engine.running or plugin is self.plugin:
            return
        self.plugin = plugin
        self.tasks.clear()
        self._selected = -1
        self._highlight_category()
        for w in self.winfo_children():
            if isinstance(w, ctk.CTkFrame) and w.grid_info().get("column") == "1":
                w.destroy()
        self._build_main()
        self._load_formats()

    def _highlight_category(self):
        for name, b in self.cat_buttons.items():
            active = name == self.plugin.category
            b.configure(fg_color=(ACCENT_SOFT if active else "transparent"),
                        text_color=(ACCENT if active else MUTED))

    def _on_chips_configure(self, event):
        if event.width == self._chips_w:
            return
        self._chips_w = event.width
        self._flow_chips()

    def _flow_chips(self):
        """按可用宽度把格式按钮自动换行排列，绝不溢出裁切。"""
        if not getattr(self, "_chip_list", None):
            return
        max_w = self.chips_frame.winfo_width()
        if max_w <= 1:
            self.after(60, self._flow_chips); return
        pad = 10
        row = col = 0
        used = 0
        for btn, w in [(b, b.winfo_reqwidth()) for b in self._chip_list]:
            if used and used + pad + w > max_w:
                row += 1; col = 0; used = 0
            btn.grid_configure(row=row, column=col, padx=5, pady=4)
            col += 1; used += w + pad

    def _load_formats(self):
        self.formats = self.plugin.output_formats()
        for w in self.chips_frame.winfo_children():
            w.destroy()
        self._chip_buttons = {}
        self._chip_list = []
        for i, f in enumerate(self.formats):
            b = ctk.CTkButton(
                self.chips_frame, text=f.label, width=92, height=30,
                font=ctk.CTkFont(size=12), corner_radius=9,
                fg_color=ACCENT, command=lambda _f=f: self._pick_format(_f))
            self._chip_buttons[f.key] = b
            self._chip_list.append(b)
        if self.formats:
            self._pick_format(self.formats[0])
        self._chips_w = 0
        self.update_idletasks()
        self._flow_chips()

    def _pick_format(self, fmt):
        self.current_fmt = fmt
        for k, b in self._chip_buttons.items():
            on = k == fmt.key
            b.configure(fg_color=(ACCENT if on else ("gray82", "gray30")),
                        text_color=("white" if on else TEXT))
        self.fmt_note.configure(text=("ℹ  " + fmt.note if fmt.note else ""))

    def _toggle_theme(self):
        ctk.set_appearance_mode(
            "Light" if ctk.get_appearance_mode() == "Dark" else "Dark")

    def _refresh_cards(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()
        if not self.tasks:
            ctk.CTkLabel(self.cards_frame, text="📂\n\n列表为空", text_color=MUTED,
                         font=ctk.CTkFont(size=14), justify="center"
                         ).grid(row=0, column=0, pady=60)
        for i, t in enumerate(self.tasks):
            card = ctk.CTkFrame(self.cards_frame, corner_radius=12,
                                fg_color=(CARD_SEL if i == self._selected else CARD))
            card.grid(row=i, column=0, sticky="ew", padx=6, pady=4)
            card.grid_columnconfigure(1, weight=1)

            ext = os.path.splitext(t.src)[1].lstrip(".").lower()
            c = BADGE_COLORS.get(ext, ("#9aa0b5", "#787f96"))
            badge = ctk.CTkFrame(card, width=42, height=42, corner_radius=11,
                                 fg_color=c)
            badge.grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=10)
            badge.grid_propagate(False)
            ctk.CTkLabel(badge, text=ext[:4].upper(),
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="white").place(relx=0.5, rely=0.5, anchor="center")

            ctk.CTkLabel(card, text=os.path.basename(t.src), anchor="w",
                         justify="left", font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=TEXT
                         ).grid(row=0, column=1, sticky="ew", padx=(2, 8), pady=(9, 0))
            sub = t.message if (t.status not in (WAITING, "") and t.message) \
                else os.path.dirname(t.src)
            ctk.CTkLabel(card, text=sub, anchor="w", justify="left",
                         font=ctk.CTkFont(size=11), text_color=MUTED
                         ).grid(row=1, column=1, sticky="ew", padx=(2, 8), pady=(0, 9))

            _, st_text = STATUS_STYLE.get(t.status, STATUS_STYLE[WAITING])
            pill = ctk.CTkLabel(card, text=f" {st_text} ",
                                font=ctk.CTkFont(size=11, weight="bold"),
                                corner_radius=8,
                                fg_color=("gray85", "gray33") if t.status == WAITING else "transparent",
                                text_color=STATUS_STYLE.get(t.status, ("gray", ""))[0])
            pill.grid(row=0, column=2, rowspan=2, padx=(4, 14))

            def bind_card(widget, idx=i):
                widget.bind("<Button-1>", lambda e: self._select_card(idx))
            for w in tuple(card.winfo_children()) + (card,):
                bind_card(w)

        self.file_count.configure(
            text=f"共 {len(self.tasks)} 个文件" if self.tasks else "")

    def _select_card(self, idx):
        self._selected = idx
        self._refresh_cards()

    def _on_drop(self, event):
        if self.engine.running:
            return
        self._ingest(self.tk.splitlist(event.data))

    def _add_files(self):
        if self.engine.running:
            return
        exts = self.plugin.input_exts
        patterns = " ".join(f"*{e}" for e in exts)
        files = filedialog.askopenfilenames(
            filetypes=[(self.plugin.category, patterns), ("所有文件", "*.*")])
        self._ingest(files)

    def _ingest(self, paths):
        existing = {t.src for t in self.tasks}
        added = rejected = 0
        for f in paths:
            if not os.path.isfile(f) or f in existing:
                continue
            if self.plugin.supports(f):
                self.tasks.append(Task(src=f)); added += 1
            else:
                rejected += 1
        self._refresh_cards()
        if rejected and not added:
            self._set_status(f"{rejected} 个文件与「{self.plugin.category}」类别不匹配。", warn=True)
        elif added:
            msg = f"已添加 {added} 个文件"
            if rejected:
                msg += f"，{rejected} 个类型不匹配已忽略"
            self._set_status(msg)

    def _toggle_outdir(self):
        custom = self.out_mode.get() == "custom"
        self.outdir_entry.configure(state="normal" if custom else "disabled")
        self.browse_btn.configure(state="normal" if custom else "disabled")

    def _choose_outdir(self):
        d = filedialog.askdirectory()
        if d:
            self.outdir_entry.delete(0, "end")
            self.outdir_entry.insert(0, d)

    def _start(self):
        if self.engine.running:
            return
        if not self.tasks:
            self._set_status("请先添加文件。", warn=True); return
        out_dir = None
        if self.out_mode.get() == "custom":
            out_dir = self.outdir_entry.get().strip()
            if not out_dir or not os.path.isdir(out_dir):
                self._set_status("输出文件夹无效。", warn=True); return
        for t in self.tasks:
            t.status = WAITING; t.message = ""; t.dst = ""
        self._refresh_cards()
        self._set_progress(0)
        self._set_busy(True)
        cb = EngineCallbacks(
            on_task_status=lambda i, s, m: self.after(0, self._update_task, i, s, m),
            on_progress=lambda f: self.after(0, self._set_progress, f),
            on_finish=lambda ok, fail: self.after(0, self._finished, ok, fail))
        self.engine.start(list(self.tasks), self.plugin, self.current_fmt, out_dir, cb)

    def _cancel(self):
        self.engine.cancel()
        self._set_status("正在取消…", warn=True)

    def _update_task(self, idx, status, message):
        if idx < len(self.tasks):
            self.tasks[idx].status = status
            self.tasks[idx].message = message
            self._refresh_cards()
            if status == RUNNING:
                self._set_status(f"转换中：{os.path.basename(self.tasks[idx].src)}")

    def _finished(self, ok, fail):
        self._set_busy(False)
        self._set_progress(1)
        self._set_status(f"完成 ✅ 成功 {ok} 个" + (
            f"，失败/取消 {fail} 个，详见列表" if fail else ""), warn=bool(fail))

    def _set_busy(self, busy):
        self.start_btn.configure(state="disabled" if busy else "normal")
        self.cancel_btn.configure(state="normal" if busy else "disabled")

    def _set_progress(self, f):
        f = min(max(f, 0.0), 1.0)
        self.progress.set(f)
        self.pct_label.configure(text=f"{f*100:.0f}%")

    def _set_status(self, text, warn=False):
        self.status_label.configure(text=text, text_color=(BAD_TXT[0] if warn else MUTED))


if __name__ == "__main__":
    App().mainloop()
