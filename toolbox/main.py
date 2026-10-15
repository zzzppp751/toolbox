#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具箱主程序。

布局：
  ┌───────────────┬────────────────────────────┐
  │  功能列表      │        当前工具面板          │
  │  (自动发现)    │                            │
  ├───────────────┴────────────────────────────┤
  │                共享日志面板                  │
  └────────────────────────────────────────────┘
"""

import queue
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from core.base import ToolContext
from core.registry import discover_tools

APP_TITLE = "工具箱"


class ToolboxApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("920x680")
        self.root.minsize(780, 560)

        self.log_queue = queue.Queue()
        self.context = ToolContext(root, self.log_queue)

        self.tools = []              # 工具实例列表
        self.frames = {}             # 序号 -> 已构建的界面
        self.current = None
        self._sidebar_labels = None

        self._build_ui()
        self._load_tools()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_log()
        self._refresh_sidebar()

    # ---------- 界面 ----------
    def _build_ui(self):
        # 底部共享日志
        logf = ttk.LabelFrame(self.root, text="运行日志")
        logf.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        self.log_text = ScrolledText(logf, height=9, state="disabled",
                                     wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # 主体
        body = ttk.Frame(self.root)
        body.pack(side="top", fill="both", expand=True, padx=8, pady=8)

        # 左侧功能列表
        side = ttk.LabelFrame(body, text="功能")
        side.pack(side="left", fill="y", padx=(0, 8))
        self.listbox = tk.Listbox(
            side, width=18, activestyle="none", exportselection=False,
            font=("Microsoft YaHei", 10), borderwidth=0, highlightthickness=1)
        self.listbox.pack(fill="both", expand=True, padx=4, pady=4)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        # 右侧工具面板容器
        self.content = ttk.Frame(body)
        self.content.pack(side="left", fill="both", expand=True)

    # ---------- 工具加载 ----------
    def _load_tools(self):
        try:
            classes = discover_tools()
        except Exception as exc:  # noqa
            self.log("工具加载失败：%s" % exc)
            classes = []

        for cls in classes:
            try:
                tool = cls(self.context)
            except Exception as exc:  # noqa
                self.log("初始化工具「%s」失败：%s" % (
                    getattr(cls, "name", cls), exc))
                continue
            self.tools.append(tool)
            self.listbox.insert("end", "  " + tool.name)

        if self.tools:
            self.listbox.selection_set(0)
            self._show_tool(0)
            self.log("已加载 %d 个工具。" % len(self.tools))
        else:
            self.log("未发现任何工具，请在 tools/ 目录下添加。")

    def _on_select(self, _event=None):
        sel = self.listbox.curselection()
        if sel:
            self._show_tool(sel[0])

    def _show_tool(self, idx, force=False):
        if self.current == idx and not force:
            return
        if self.current is not None:
            try:
                self.tools[self.current].on_hide()
            except Exception:
                pass
            self.frames[self.current].pack_forget()

        tool = self.tools[idx]
        if idx not in self.frames:
            try:
                frame = tool.build(self.content)
            except Exception as exc:  # noqa
                import traceback
                self.log("构建「%s」失败：%s" % (tool.name, exc))
                self.log(traceback.format_exc().rstrip())
                frame = ttk.Frame(self.content)
                ttk.Label(frame, text="该工具加载失败，详见日志。").pack(
                    padx=20, pady=20)
            self.frames[idx] = frame

        self.frames[idx].pack(fill="both", expand=True)
        self.current = idx
        try:
            tool.on_show()
        except Exception:
            pass

    # ---------- 日志 ----------
    def log(self, msg):
        self.log_queue.put(msg)

    def _poll_log(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                ts = time.strftime("%H:%M:%S")
                self.log_text.configure(state="normal")
                self.log_text.insert("end", "[%s] %s\n" % (ts, line))
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(200, self._poll_log)

    # ---------- 侧栏运行标记 ----------
    def _refresh_sidebar(self):
        labels = []
        for t in self.tools:
            try:
                is_run = t.running
            except Exception:
                is_run = False
            labels.append("  %s%s" % (t.name, "  ●" if is_run else ""))

        if labels != self._sidebar_labels:
            sel = self.listbox.curselection()
            self.listbox.delete(0, "end")
            for lb in labels:
                self.listbox.insert("end", lb)
            self._sidebar_labels = labels
            if sel:
                self.listbox.selection_set(sel[0])

        self.root.after(1000, self._refresh_sidebar)

    # ---------- 退出 ----------
    def _on_close(self):
        for tool in self.tools:
            try:
                tool.close()
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    ToolboxApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
