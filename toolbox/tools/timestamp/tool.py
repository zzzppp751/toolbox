#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""时间戳转换（工具箱插件）。

演示两个生命周期钩子：
  - on_show / on_hide 控制“当前时间”的实时刷新，切走就停，省资源。
"""

import time
import tkinter as tk
from datetime import datetime, timezone
from tkinter import ttk

from core.base import BaseTool

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

TIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%Y%m%d%H%M%S",
    "%Y-%m-%dT%H:%M:%S",
]


class TimestampTool(BaseTool):
    id = "timestamp"
    name = "时间戳转换"
    order = 40

    def __init__(self, context):
        super().__init__(context)
        self._tick_id = None

    # ---------------- 界面 ----------------
    def build(self, parent):
        f = ttk.Frame(parent)

        box1 = ttk.LabelFrame(f, text="当前时间")
        box1.pack(fill="x", padx=6, pady=6)
        self.now_var = tk.StringVar()
        ttk.Label(box1, textvariable=self.now_var,
                  font=("Consolas", 10), justify="left").pack(
            anchor="w", padx=10, pady=8)

        box2 = ttk.LabelFrame(f, text="时间戳 → 时间")
        box2.pack(fill="x", padx=6, pady=6)
        row = ttk.Frame(box2)
        row.pack(fill="x", padx=10, pady=8)
        self.ts_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.ts_var, width=26).pack(side="left")
        ttk.Button(row, text="转换", command=self._ts_to_time).pack(
            side="left", padx=6)
        ttk.Button(row, text="填入当前", command=self._fill_now_ts).pack(
            side="left")
        self.ts_out = tk.StringVar(value="支持秒（10 位）或毫秒（13 位）")
        ttk.Label(box2, textvariable=self.ts_out, justify="left").pack(
            anchor="w", padx=10, pady=(0, 8))

        box3 = ttk.LabelFrame(f, text="时间 → 时间戳")
        box3.pack(fill="x", padx=6, pady=6)
        row2 = ttk.Frame(box3)
        row2.pack(fill="x", padx=10, pady=8)
        self.dt_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.dt_var, width=26).pack(side="left")
        ttk.Button(row2, text="转换", command=self._time_to_ts).pack(
            side="left", padx=6)
        ttk.Button(row2, text="填入当前", command=self._fill_now_dt).pack(
            side="left")
        self.dt_out = tk.StringVar(value="支持 2026-10-16 11:30:00 等常见格式")
        ttk.Label(box3, textvariable=self.dt_out, justify="left").pack(
            anchor="w", padx=10, pady=(0, 8))

        self.frame = f
        return f

    # ---------------- 生命周期 ----------------
    def on_show(self):
        self._start_tick()

    def on_hide(self):
        self._stop_tick()

    def close(self):
        self._stop_tick()

    def _start_tick(self):
        if self._tick_id is not None or self.frame is None:
            return
        self._tick()

    def _stop_tick(self):
        if self._tick_id is not None:
            try:
                self.frame.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None

    def _tick(self):
        now = time.time()
        self.now_var.set("%s   %s\n秒: %d      毫秒: %d" % (
            datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
            WEEKDAYS[datetime.fromtimestamp(now).weekday()],
            int(now), int(now * 1000)))
        try:
            self._tick_id = self.frame.after(1000, self._tick)
        except Exception:
            self._tick_id = None

    # ---------------- 转换 ----------------
    def _fill_now_ts(self):
        self.ts_var.set(str(int(time.time())))

    def _fill_now_dt(self):
        self.dt_var.set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def _ts_to_time(self):
        raw = self.ts_var.get().strip()
        if not raw:
            self.ts_out.set("请输入时间戳")
            return
        try:
            value = float(raw)
        except ValueError:
            self.ts_out.set("无法解析：%s" % raw)
            return

        # 大于 1e11 视为毫秒（13 位）
        seconds = value / 1000.0 if abs(value) > 1e11 else value
        try:
            local = datetime.fromtimestamp(seconds).astimezone()
            utc = datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            self.ts_out.set("数值超出可表示范围：%s" % raw)
            return

        self.ts_out.set(
            "本地时间：%s  %s\n"
            "UTC 时间：%s\n"
            "ISO 8601：%s" % (
                local.strftime("%Y-%m-%d %H:%M:%S"),
                WEEKDAYS[local.weekday()],
                utc.strftime("%Y-%m-%d %H:%M:%S"),
                local.isoformat(timespec="seconds")))
        self.log("时间戳 %s → %s" % (raw, local.strftime("%Y-%m-%d %H:%M:%S")))

    def _time_to_ts(self):
        raw = self.dt_var.get().strip()
        if not raw:
            self.dt_out.set("请输入时间，例如 2026-10-16 11:30:00")
            return

        dt = None
        for fmt in TIME_FORMATS:
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            self.dt_out.set("无法解析时间：%s\n支持的格式如 2026-10-16 11:30:00" % raw)
            return

        ts = dt.timestamp()
        self.dt_out.set("秒级（10 位）：%d\n毫秒级（13 位）：%d" % (
            int(ts), int(ts * 1000)))
        self.log("时间 %s → %d" % (raw, int(ts)))
