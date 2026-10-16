#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一的界面主题：配色、字体与控件样式。

所有界面都走这里，改一处即可全局换肤。
"""

import tkinter as tk
from tkinter import ttk

# ---------------- 配色 ----------------
BG = "#FFFFFF"          # 内容区底色
SIDEBAR = "#F5F7FA"     # 侧栏底色
LOG_BG = "#FAFBFC"      # 日志区底色
BORDER = "#E9ECF1"
BORDER_2 = "#D9DEE7"
TEXT = "#1F2430"
TEXT_SUB = "#6B7480"
ACCENT = "#2F6FED"
ACCENT_D = "#2458C8"
SEL_BG = "#2F6FED"
HOVER = "#EDF1F7"
OK = "#1A7F37"
WARN = "#C0392B"

# ---------------- 字体 ----------------
FAMILY = "Microsoft YaHei UI"
FONT = (FAMILY, 10)
FONT_S = (FAMILY, 9)
FONT_L = (FAMILY, 15, "bold")
MONO = ("Consolas", 10)


def apply(root):
    """给根窗口套用主题，返回 ttk.Style 以便进一步定制。"""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")     # clam 才允许自由改配色
    except tk.TclError:
        pass

    root.configure(bg=BG)

    style.configure(".", font=FONT, background=BG, foreground=TEXT,
                    focuscolor=BG, bordercolor=BORDER_2)
    style.configure("TFrame", background=BG)
    style.configure("Sidebar.TFrame", background=SIDEBAR)
    style.configure("Log.TFrame", background=LOG_BG)

    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_SUB,
                    font=FONT_S)
    style.configure("Title.TLabel", background=BG, foreground=TEXT,
                    font=FONT_L)
    style.configure("Side.TLabel", background=SIDEBAR, foreground=TEXT_SUB,
                    font=FONT_S)
    style.configure("Ok.TLabel", background=BG, foreground=OK)
    style.configure("Warn.TLabel", background=BG, foreground=WARN)

    style.configure("TLabelframe", background=BG, bordercolor=BORDER_2,
                    relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=BG, foreground=TEXT_SUB,
                    font=FONT_S)

    # 按钮：默认描边款
    style.configure("TButton", background="#FFFFFF", foreground=TEXT,
                    bordercolor=BORDER_2, focuscolor=BG, relief="flat",
                    padding=(12, 6), borderwidth=1)
    style.map("TButton",
              background=[("active", HOVER), ("pressed", "#E2E8F2")],
              bordercolor=[("active", ACCENT)])

    # 主操作按钮：实心强调色
    style.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF",
                    bordercolor=ACCENT, focuscolor=ACCENT, relief="flat",
                    padding=(14, 7), borderwidth=1)
    style.map("Accent.TButton",
              background=[("active", ACCENT_D), ("pressed", ACCENT_D),
                          ("disabled", "#AEC4F7")],
              foreground=[("disabled", "#FFFFFF")],
              bordercolor=[("active", ACCENT_D)])

    # 输入框
    style.configure("TEntry", fieldbackground="#FFFFFF", foreground=TEXT,
                    bordercolor=BORDER_2, lightcolor=BORDER_2,
                    darkcolor=BORDER_2, padding=4)
    style.map("TEntry",
              bordercolor=[("focus", ACCENT)],
              lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)])

    style.configure("TCombobox", fieldbackground="#FFFFFF", background="#FFFFFF",
                    foreground=TEXT, bordercolor=BORDER_2, lightcolor=BORDER_2,
                    darkcolor=BORDER_2, arrowcolor=TEXT_SUB, padding=4)
    style.map("TCombobox",
              fieldbackground=[("readonly", "#FFFFFF")],
              bordercolor=[("focus", ACCENT)],
              lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)])

    style.configure("TCheckbutton", background=BG, foreground=TEXT,
                    focuscolor=BG, padding=2)
    style.map("TCheckbutton",
              background=[("active", BG)],
              indicatorcolor=[("selected", ACCENT), ("!selected", "#FFFFFF")])

    # 侧栏功能列表：去掉表头、加大行高
    style.configure("Side.Treeview", background=SIDEBAR,
                    fieldbackground=SIDEBAR, foreground=TEXT,
                    borderwidth=0, relief="flat", rowheight=34, font=FONT)
    style.map("Side.Treeview",
              background=[("selected", SEL_BG)],
              foreground=[("selected", "#FFFFFF")])
    style.layout("Side.Treeview",
                 [("Side.Treeview.treearea", {"sticky": "nswe"})])

    # 表格（转发规则等）
    style.configure("Treeview", background="#FFFFFF",
                    fieldbackground="#FFFFFF", foreground=TEXT,
                    bordercolor=BORDER_2, borderwidth=1, relief="solid",
                    rowheight=26, font=FONT)
    style.map("Treeview",
              background=[("selected", "#DCE8FD")],
              foreground=[("selected", TEXT)])
    style.configure("Treeview.Heading", background="#F2F5F9",
                    foreground=TEXT_SUB, relief="flat", borderwidth=0,
                    font=FONT_S, padding=(6, 6))
    style.map("Treeview.Heading", background=[("active", "#E8EDF4")])

    # 下拉弹出列表的配色（这部分要靠 option 数据库）
    root.option_add("*TCombobox*Listbox.background", "#FFFFFF")
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    root.option_add("*TCombobox*Listbox.font", FONT)

    # 选项卡
    style.configure("TNotebook", background=BG, bordercolor=BORDER_2,
                    tabmargins=(2, 6, 2, 0))
    style.configure("TNotebook.Tab", background="#F1F4F8",
                    foreground=TEXT_SUB, padding=(14, 7),
                    bordercolor=BORDER_2, font=FONT)
    style.map("TNotebook.Tab",
              background=[("selected", "#FFFFFF")],
              foreground=[("selected", ACCENT)])

    # 上下分栏（工具面板 / 日志）：细一点的分界线
    try:
        style.configure("TPanedwindow", background=BG, sashwidth=8,
                        sashrelief="flat", sashpad=0)
        style.configure("Sash", background=BORDER, sashthickness=8,
                        gripcount=0, relief="flat")
        style.map("Sash", background=[("active", ACCENT)])
    except tk.TclError:
        pass

    # 滚动条：细一点
    style.configure("Vertical.TScrollbar", background="#E7EBF1",
                    troughcolor=BG, bordercolor=BG, arrowcolor=TEXT_SUB,
                    width=11)
    style.map("Vertical.TScrollbar", background=[("active", "#CFD6E0")])

    return style


def style_text(widget, mono=False, height=None):
    """把 tk.Text / ScrolledText 调成卡片风格。"""
    widget.configure(
        background=LOG_BG if mono else "#FFFFFF",
        foreground=TEXT,
        relief="flat",
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=BORDER_2,
        highlightcolor=ACCENT,
        padx=8,
        pady=6,
        insertbackground=ACCENT,
        font=MONO if mono else FONT,
        selectbackground="#D6E2FD",
        selectforeground=TEXT,
    )
    if height:
        widget.configure(height=height)
