#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地反向代理工具（工具箱插件：界面层）。"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.base import BaseTool

from .config import ProxyConfig
from .engine import ProxyEngine

CONFIG_NAME = "proxy"


class ProxyTool(BaseTool):
    id = "proxy"
    name = "本地反向代理"
    description = "把本地路径转发到指定上游地址，自带 CORS 支持"
    order = 10

    def __init__(self, context):
        super().__init__(context)
        self.config = ProxyConfig()
        self.engine = ProxyEngine(self.config, context.log)

    # ---------------- 界面 ----------------
    def build(self, parent):
        f = ttk.Frame(parent)

        top = ttk.LabelFrame(f, text="监听设置")
        top.pack(fill="x", padx=6, pady=6)
        ttk.Label(top, text="监听地址：").grid(row=0, column=0, sticky="e",
                                          padx=6, pady=4)
        self.host_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(top, textvariable=self.host_var, width=16).grid(
            row=0, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(top, text="端口：").grid(row=0, column=2, sticky="e",
                                         padx=6, pady=4)
        self.port_var = tk.StringVar(value="8021")
        ttk.Entry(top, textvariable=self.port_var, width=8).grid(
            row=0, column=3, sticky="w", padx=6, pady=4)
        self.cors_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="启用 CORS（跨域支持）",
                        variable=self.cors_var).grid(
            row=0, column=4, sticky="w", padx=6, pady=4)

        rules = ttk.LabelFrame(f, text="转发规则（本地路径前缀 → 上游地址）")
        rules.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree = ttk.Treeview(rules, columns=("local", "upstream"),
                                 show="headings", height=5)
        self.tree.heading("local", text="本地路径前缀")
        self.tree.heading("upstream", text="上游地址")
        self.tree.column("local", width=150, anchor="w")
        self.tree.column("upstream", width=430, anchor="w")
        self.tree.grid(row=0, column=0, columnspan=4, sticky="nsew",
                       padx=6, pady=4)
        rules.rowconfigure(0, weight=1)
        rules.columnconfigure(0, weight=1)
        sb = ttk.Scrollbar(rules, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=4, sticky="ns", pady=4)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", self._on_row_double_click)

        ttk.Label(rules, text="本地前缀：").grid(row=1, column=0, sticky="e",
                                            padx=6, pady=4)
        self.local_var = tk.StringVar()
        ttk.Entry(rules, textvariable=self.local_var, width=16).grid(
            row=1, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(rules, text="上游地址：").grid(row=1, column=2, sticky="e",
                                            padx=6, pady=4)
        self.upstream_var = tk.StringVar()
        ttk.Entry(rules, textvariable=self.upstream_var).grid(
            row=1, column=3, sticky="we", padx=6, pady=4)
        rules.columnconfigure(3, weight=1)

        btns = ttk.Frame(rules)
        btns.grid(row=2, column=0, columnspan=5, sticky="w", padx=6, pady=4)
        ttk.Button(btns, text="添加规则", command=self._add_route).pack(
            side="left", padx=4)
        ttk.Button(btns, text="更新选中", command=self._update_route).pack(
            side="left", padx=4)
        ttk.Button(btns, text="删除选中", command=self._delete_route).pack(
            side="left", padx=4)
        ttk.Button(btns, text="清空", command=self._clear_routes).pack(
            side="left", padx=4)

        ctrl = ttk.Frame(f)
        ctrl.pack(fill="x", padx=6, pady=6)
        self.toggle_btn = ttk.Button(ctrl, text="启动代理",
                                     style="Accent.TButton",
                                     command=self._toggle)
        self.toggle_btn.pack(side="left", padx=(0, 8))
        ttk.Button(ctrl, text="保存配置",
                   command=self._save_config).pack(side="left", padx=4)
        ttk.Button(ctrl, text="加载配置",
                   command=self._load_config).pack(side="left", padx=4)
        self.status_var = tk.StringVar(value="未启动")
        self.status_label = ttk.Label(ctrl, textvariable=self.status_var,
                                      style="Muted.TLabel")
        self.status_label.pack(side="left", padx=14)

        self._load_saved_config()
        self.frame = f
        return f

    # ---------------- 规则操作 ----------------
    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.config.routes:
            self.tree.insert("", "end", values=(r["local"], r["upstream"]))

    def _validate_rule(self, local, upstream):
        local = (local or "").strip()
        upstream = (upstream or "").strip()
        if not local:
            messagebox.showwarning("提示", "请填写本地路径前缀，例如 /xcx/")
            return None
        if not local.startswith("/"):
            local = "/" + local
        if not upstream:
            messagebox.showwarning(
                "提示", "请填写上游地址，例如 https://www.example.com/xcx/")
            return None
        if not upstream.startswith(("http://", "https://")):
            upstream = "http://" + upstream
        return {"local": local, "upstream": upstream}

    def _add_route(self):
        rule = self._validate_rule(self.local_var.get(), self.upstream_var.get())
        if not rule:
            return
        self.config.routes.append(rule)
        self._refresh_tree()
        self.local_var.set("")
        self.upstream_var.set("")

    def _update_route(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表里选中要更新的规则。")
            return
        rule = self._validate_rule(self.local_var.get(), self.upstream_var.get())
        if not rule:
            return
        self.config.routes[self.tree.index(sel[0])] = rule
        self._refresh_tree()

    def _delete_route(self):
        sel = self.tree.selection()
        if not sel:
            return
        for item in sel:
            del self.config.routes[self.tree.index(item)]
        self._refresh_tree()

    def _clear_routes(self):
        if self.config.routes and messagebox.askyesno("确认", "清空所有规则？"):
            self.config.routes = []
            self._refresh_tree()

    def _on_row_double_click(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        self.local_var.set(vals[0])
        self.upstream_var.set(vals[1])

    # ---------------- 配置读写 ----------------
    def _config_to_ui(self):
        self.host_var.set(self.config.listen_host)
        self.port_var.set(str(self.config.listen_port))
        self.cors_var.set(self.config.enable_cors)
        self._refresh_tree()

    def _ui_to_config(self):
        try:
            port = int(self.port_var.get())
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "端口必须是 1-65535 的整数。")
            return False
        self.config.listen_host = self.host_var.get().strip() or "127.0.0.1"
        self.config.listen_port = port
        self.config.enable_cors = bool(self.cors_var.get())
        return True

    def _load_saved_config(self):
        path = self.context.config_path(CONFIG_NAME)
        if os.path.exists(path):
            try:
                self.config = ProxyConfig.load(path)
                self.engine.config = self.config
                self._config_to_ui()
                self.log("已加载配置：%s" % path)
                return
            except Exception as exc:  # noqa
                self.log("加载配置失败：%s" % exc)
        # 首次使用：给两条示例规则
        self.config.routes = [
            {"local": "/yj/", "upstream": "https://www.qbjzhly.cn/yj/"},
            {"local": "/xcx/", "upstream": "https://www.qbjzhly.cn/xcx/"},
        ]
        self._config_to_ui()

    def _save_config(self):
        self._ui_to_config()
        path = filedialog.asksaveasfilename(
            title="保存配置", defaultextension=".json",
            initialfile="%s.json" % CONFIG_NAME,
            filetypes=[("JSON 配置", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            self.config.save(path)
            self.log("配置已保存：%s" % path)
        except Exception as exc:  # noqa
            messagebox.showerror("错误", "保存失败：%s" % exc)

    def _load_config(self):
        path = filedialog.askopenfilename(
            title="加载配置",
            filetypes=[("JSON 配置", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            self.config = ProxyConfig.load(path)
            self.engine.config = self.config
            self._config_to_ui()
            self.log("配置已加载：%s" % path)
        except Exception as exc:  # noqa
            messagebox.showerror("错误", "加载失败：%s" % exc)

    # ---------------- 启停 ----------------
    def _toggle(self):
        if self.engine.running:
            self.stop()
        else:
            self.start()

    def start(self):
        if self.engine.running:
            return
        if not self._ui_to_config():
            return
        if not self.config.routes:
            messagebox.showwarning("提示", "请至少添加一条转发规则。")
            return
        try:
            self.engine.start()
        except OSError as exc:
            messagebox.showerror(
                "启动失败", "无法监听 %s:%s\n%s\n\n（端口可能已被占用）" % (
                    self.config.listen_host, self.config.listen_port, exc))
            self.engine.httpd = None
            return
        self._set_running_ui(True)

    def stop(self):
        self.engine.stop()
        self._set_running_ui(False)

    @property
    def running(self):
        return self.engine.running

    def _set_running_ui(self, running):
        if not hasattr(self, "toggle_btn"):
            return
        if running:
            self.toggle_btn.configure(text="停止代理", style="TButton")
            self.status_label.configure(style="Ok.TLabel")
            self.status_var.set("运行中  http://%s:%d" % (
                self.config.listen_host, self.config.listen_port))
        else:
            self.toggle_btn.configure(text="启动代理", style="Accent.TButton")
            self.status_label.configure(style="Muted.TLabel")
            self.status_var.set("未启动")
