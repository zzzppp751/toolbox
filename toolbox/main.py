#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具箱主程序。

布局：
  ┌───────────┬──────────────────────────────┐
  │ 功能列表   │  当前工具标题 + 说明           │
  │           ├──────────────────────────────┤
  │           │  当前工具面板                  │
  ├───────────┴──────────────────────────────┤  ← 分界线可拖动
  │ 运行日志（可清空）                         │
  ├──────────────────────────────────────────┤
  │ 状态栏                                    │
  └──────────────────────────────────────────┘
"""

import os
import queue
import sys
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from core import theme
from core.base import ToolContext, resource_path
from core.registry import discover_tools

APP_TITLE = "工具箱"

SIDEBAR_W = 196
LOG_PREF_H = 152        # 日志区理想高度
LOG_MIN_H = 78          # 日志区最小高度，其余都给工具面板


class ToolboxApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1020x800")
        self.root.minsize(900, 660)

        theme.apply(root)

        self.log_queue = queue.Queue()
        self.context = ToolContext(root, self.log_queue)

        self.tools = []
        self.frames = {}
        self.current = None
        self._sidebar_labels = None

        self._build_ui()
        self._set_window_icon()
        self._load_tools()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(140, lambda: self._autofit_layout(force=True))
        self._poll_log()
        self._refresh_sidebar()

    # ---------------- 窗口图标 ----------------
    def _set_window_icon(self):
        ico = resource_path(os.path.join("assets", "icon.ico"))
        if sys.platform == "win32" and os.path.exists(ico):
            try:
                self.root.update_idletasks()
            except Exception:
                pass
            if self._win_set_icon(ico):
                return          # Windows 下装好了就不再用 Tk 那套覆盖

        if os.path.exists(ico):
            try:
                self.root.iconbitmap(ico)
            except Exception:
                pass
        png = resource_path(os.path.join("assets", "icon.png"))
        if os.path.exists(png):
            try:
                photo = tk.PhotoImage(file=png)
                self.root.iconphoto(True, photo)
                self.root._icon_photo = photo      # 防止被回收
            except Exception:
                pass

    def _win_set_icon(self, ico):
        """Windows：按系统要求的大小，从多尺寸 ico 里各取一张装上。

        Tk 自带的 iconbitmap 只装一个大图标，任务栏和资源管理器再自己缩，
        小尺寸就糊了。这里显式给 ICON_SMALL / ICON_BIG 各装一张合身的。
        """
        try:
            import ctypes
            from ctypes import wintypes as wt

            u32 = ctypes.windll.user32
            u32.GetSystemMetrics.restype = ctypes.c_int
            u32.LoadImageW.restype = wt.HANDLE
            u32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT,
                                       ctypes.c_int, ctypes.c_int, wt.UINT]
            u32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM,
                                         wt.LPARAM]

            IMAGE_ICON, LR_LOADFROMFILE = 1, 0x0010
            WM_SETICON, ICON_SMALL, ICON_BIG = 0x0080, 0, 1

            hwnd = int(self.root.frame(), 0)    # Tk 顶层窗口句柄（0x 开头）

            handles = []
            for metric_w, metric_h, which in ((49, 50, ICON_SMALL),
                                              (11, 12, ICON_BIG)):
                cx = u32.GetSystemMetrics(metric_w)     # SM_CXSMICON / SM_CXICON
                cy = u32.GetSystemMetrics(metric_h)
                handle = u32.LoadImageW(None, str(ico), IMAGE_ICON, cx, cy,
                                        LR_LOADFROMFILE)
                if handle:
                    u32.SendMessageW(hwnd, WM_SETICON, which, handle)
                    handles.append(handle)

            self._icon_handles = handles        # 留住句柄，别被回收
            return bool(handles)
        except Exception:
            return False

    # ---------------- 界面 ----------------
    def _build_ui(self):
        # 状态栏（最底部）
        bar = tk.Frame(self.root, bg=theme.SIDEBAR, height=28)
        bar.pack(side="bottom", fill="x")
        bar.pack_propagate(False)
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(bar, textvariable=self.status_var, bg=theme.SIDEBAR,
                 fg=theme.TEXT_SUB, font=theme.FONT_S).pack(side="left", padx=12)
        self.status_right_var = tk.StringVar(value="")
        tk.Label(bar, textvariable=self.status_right_var, bg=theme.SIDEBAR,
                 fg=theme.TEXT_SUB, font=theme.FONT_S).pack(side="right", padx=12)

        # 上下分栏：上=工具面板，下=运行日志；分界线可拖动
        self.paned = ttk.Panedwindow(self.root, orient="vertical")
        self.paned.pack(side="top", fill="both", expand=True,
                        padx=12, pady=(12, 8))

        # ---- 上半：功能面板 ----
        body = tk.Frame(self.paned, bg=theme.BG)
        self.paned.add(body, weight=1)

        side = tk.Frame(body, bg=theme.SIDEBAR, width=SIDEBAR_W)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        tk.Label(side, text="功  能", bg=theme.SIDEBAR, fg=theme.TEXT_SUB,
                 font=theme.FONT_S).pack(anchor="w", padx=16, pady=(14, 6))

        self.tree = ttk.Treeview(side, style="Side.Treeview", show="tree",
                                 selectmode="browse")
        self.tree.pack(fill="both", expand=True, padx=5, pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: "break")

        # 侧栏与内容之间的一条细线
        tk.Frame(body, bg=theme.BORDER, width=1).pack(side="left", fill="y")

        right = tk.Frame(body, bg=theme.BG)
        right.pack(side="left", fill="both", expand=True, padx=(18, 0))

        self.header = header = tk.Frame(right, bg=theme.BG)
        header.pack(fill="x")
        self.tool_title_var = tk.StringVar(value="")
        self.tool_desc_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.tool_title_var,
                  style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, textvariable=self.tool_desc_var,
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 8))
        tk.Frame(right, bg=theme.BORDER, height=1).pack(fill="x", pady=(0, 10))

        self.content = tk.Frame(right, bg=theme.BG)
        self.content.pack(fill="both", expand=True)

        # ---- 下半：运行日志 ----
        logf = tk.Frame(self.paned, bg=theme.BG)
        self.paned.add(logf, weight=0)
        self.log_frame = logf

        head = tk.Frame(logf, bg=theme.BG)
        head.pack(fill="x", pady=(6, 4))
        tk.Label(head, text="运行日志", bg=theme.BG, fg=theme.TEXT_SUB,
                 font=theme.FONT_S).pack(side="left")
        ttk.Button(head, text="清空", width=6,
                   command=self._clear_log).pack(side="right")

        self.log_text = ScrolledText(logf, height=6, width=1, state="disabled",
                                     wrap="word")
        theme.style_text(self.log_text, mono=True)
        self.log_text.pack(fill="both", expand=True)

    # ---------------- 布局自适应 ----------------
    def _autofit_layout(self, force=False):
        """摆好上下分界线。

        force=True（启动时）：把日志放到理想高度；
        force=False（切工具时）：只有在当前工具放不下时，才把日志压到最小。
        用户手动拖动分界线后，只要工具面板没被裁切，就不再打扰。
        """
        try:
            total = self.paned.winfo_height()
            if total <= 1:
                return
            need = self.content.winfo_y() + 4      # 标题头 + 分隔线占掉的高度
            frame = self.frames.get(self.current)
            if frame is not None:
                need += frame.winfo_reqheight()
            if not force and self.paned.sashpos(0) >= need:
                return          # 放得下，尊重当前分界位置
            log_h = max(LOG_MIN_H, min(LOG_PREF_H, total - need))
            self.paned.sashpos(0, max(180, total - log_h))
        except Exception:
            pass

    # ---------------- 工具加载 ----------------
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

        self._rebuild_sidebar()

        if self.tools:
            self._show_tool(0)
            self.log("已加载 %d 个工具。" % len(self.tools))
        else:
            self.log("未发现任何工具，请在 tools/ 目录下添加。")

        self.status_right_var.set("共 %d 个功能" % len(self.tools))

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if sel:
            self._show_tool(int(sel[0]))

    def _show_tool(self, idx):
        if self.current == idx:
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
        self.tool_title_var.set(tool.name)
        self.tool_desc_var.set(tool.description or "")

        if self.tree.selection() != (str(idx),):
            self.tree.selection_set(str(idx))
        try:
            tool.on_show()
        except Exception:
            pass

        self.root.after_idle(self._autofit_layout)

    # ---------------- 日志 ----------------
    def log(self, msg):
        self.log_queue.put(msg)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _poll_log(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                stamp = time.strftime("%H:%M:%S")
                self.log_text.configure(state="normal")
                self.log_text.insert("end", "[%s] %s\n" % (stamp, line))
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(200, self._poll_log)

    # ---------------- 侧栏 ----------------
    def _side_label(self, tool):
        return "  %s%s" % (tool.name, "   ●" if self._safe_running(tool) else "")

    def _rebuild_sidebar(self):
        self.tree.delete(*self.tree.get_children())
        for i, tool in enumerate(self.tools):
            self.tree.insert("", "end", iid=str(i), text=self._side_label(tool))

    def _refresh_sidebar(self):
        labels = [self._side_label(t) for t in self.tools]
        if labels != self._sidebar_labels:
            sel = self.tree.selection()
            for i, text in enumerate(labels):
                if self.tree.exists(str(i)):
                    self.tree.item(str(i), text=text)
            self._sidebar_labels = labels
            if sel and self.tree.exists(sel[0]):
                self.tree.selection_set(sel[0])

        running = [t.name for t in self.tools if self._safe_running(t)]
        self.status_var.set(
            "运行中：%s" % "、".join(running) if running else "就绪")

        self.root.after(1000, self._refresh_sidebar)

    @staticmethod
    def _safe_running(tool):
        try:
            return bool(tool.running)
        except Exception:
            return False

    # ---------------- 退出 ----------------
    def _on_close(self):
        for tool in self.tools:
            try:
                tool.close()
            except Exception:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    ToolboxApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
