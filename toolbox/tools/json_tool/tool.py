#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JSON 工具（工具箱插件）：格式化 / 压缩 / 校验 / 转义 / 去转义。"""

import json
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from core.base import BaseTool


class JsonTool(BaseTool):
    id = "json_tool"
    name = "JSON 工具"
    order = 30

    # ---------------- 界面 ----------------
    def build(self, parent):
        f = ttk.Frame(parent)

        bar = ttk.Frame(f)
        bar.pack(fill="x", padx=6, pady=6)
        ttk.Button(bar, text="格式化", command=self._format).pack(
            side="left", padx=(0, 6))
        ttk.Button(bar, text="压缩成一行", command=self._minify).pack(
            side="left", padx=(0, 6))
        ttk.Button(bar, text="校验", command=self._validate).pack(
            side="left", padx=(0, 6))
        ttk.Button(bar, text="转义", command=self._escape).pack(
            side="left", padx=(0, 6))
        ttk.Button(bar, text="去转义", command=self._unescape).pack(
            side="left", padx=(0, 12))
        ttk.Label(bar, text="缩进：").pack(side="left")
        self.indent_var = tk.StringVar(value="2 空格")
        ttk.Combobox(bar, textvariable=self.indent_var, width=8,
                     state="readonly",
                     values=["2 空格", "4 空格", "Tab"]).pack(side="left")

        in_frame = ttk.LabelFrame(f, text="输入")
        in_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.input_text = ScrolledText(in_frame, height=10)
        self.input_text.pack(fill="both", expand=True, padx=4, pady=4)

        mid = ttk.Frame(f)
        mid.pack(fill="x", padx=6)
        ttk.Button(mid, text="↑ 结果写回输入", command=self._use_output).pack(
            side="left")
        ttk.Button(mid, text="清空", command=self._clear).pack(
            side="left", padx=6)
        self.status_var = tk.StringVar(value="粘贴 JSON 后点上面的按钮")
        ttk.Label(mid, textvariable=self.status_var,
                  foreground="#0a7a3f").pack(side="left", padx=12)

        out_frame = ttk.LabelFrame(f, text="输出")
        out_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.output_text = ScrolledText(out_frame, height=10)
        self.output_text.pack(fill="both", expand=True, padx=4, pady=4)

        self.frame = f
        return f

    # ---------------- 辅助 ----------------
    def _indent(self):
        value = self.indent_var.get()
        if value == "Tab":
            return "\t"
        if value == "4 空格":
            return 4
        return 2

    def _read(self):
        return self.input_text.get("1.0", "end").rstrip("\n")

    def _write(self, text, status, error=False):
        self.output_text.delete("1.0", "end")
        self.output_text.insert("end", text)
        self.status_var.set(status)
        self.log(status) if error else None

    def _use_output(self):
        text = self.output_text.get("1.0", "end").rstrip("\n")
        if text:
            self.input_text.delete("1.0", "end")
            self.input_text.insert("end", text)

    def _clear(self):
        self.input_text.delete("1.0", "end")
        self.output_text.delete("1.0", "end")
        self.status_var.set("已清空")

    # ---------------- 操作 ----------------
    def _format(self):
        raw = self._read()
        try:
            data = json.loads(raw)
        except Exception as exc:
            self._write(str(exc), "JSON 解析失败：%s" % exc, error=True)
            return
        self._write(json.dumps(data, ensure_ascii=False,
                               indent=self._indent()),
                    "格式化完成 ✔")

    def _minify(self):
        raw = self._read()
        try:
            data = json.loads(raw)
        except Exception as exc:
            self._write(str(exc), "JSON 解析失败：%s" % exc, error=True)
            return
        self._write(json.dumps(data, ensure_ascii=False,
                               separators=(",", ":")),
                    "已压缩为一行 ✔")

    def _validate(self):
        raw = self._read()
        try:
            data = json.loads(raw)
        except Exception as exc:
            self._write(str(exc), "❌ 不是合法 JSON：%s" % exc, error=True)
            return
        if isinstance(data, dict):
            detail = "对象，%d 个键" % len(data)
        elif isinstance(data, list):
            detail = "数组，%d 个元素" % len(data)
        else:
            detail = "基本类型：%s" % type(data).__name__
        self.status_var.set("✅ 合法 JSON（%s）" % detail)
        self.log("JSON 校验通过：%s" % detail)

    def _escape(self):
        """把整段文本转成 JSON 字符串字面量（便于嵌进别的 JSON）。"""
        raw = self._read()
        self._write(json.dumps(raw, ensure_ascii=False), "已转义 ✔")

    def _unescape(self):
        """还原被转义的字符串字面量。"""
        raw = self._read().strip()
        try:
            data = json.loads(raw)
        except Exception as exc:
            self._write(str(exc), "去转义失败：%s" % exc, error=True)
            return
        if not isinstance(data, str):
            self._write(json.dumps(data, ensure_ascii=False, indent=2),
                        "输入不是字符串，已按 JSON 格式化输出")
            return
        self._write(data, "已去转义 ✔")
