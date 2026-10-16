#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接口调试器（工具箱插件：界面层）。

请求在后台线程发送，结果经队列回填到界面，避免卡住 UI。
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from core import theme
from core.base import BaseTool

from . import client

METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]


class ApiTesterTool(BaseTool):
    id = "api_tester"
    name = "接口调试器"
    order = 20

    def __init__(self, context):
        super().__init__(context)
        self._results = queue.Queue()

    # ---------------- 界面 ----------------
    def build(self, parent):
        f = ttk.Frame(parent)

        bar = ttk.Frame(f)
        bar.pack(fill="x", padx=6, pady=6)
        self.method_var = tk.StringVar(value="GET")
        ttk.Combobox(bar, textvariable=self.method_var, width=8,
                     state="readonly", values=METHODS).pack(side="left")
        self.url_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.url_var).pack(
            side="left", fill="x", expand=True, padx=6)
        self.send_btn = ttk.Button(bar, text="发送", style="Accent.TButton",
                                   command=self._send)
        self.send_btn.pack(side="left")

        opts = ttk.Frame(f)
        opts.pack(fill="x", padx=6)
        self.proxy_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="忽略系统代理", variable=self.proxy_var).pack(
            side="left")
        self.cert_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="忽略证书错误", variable=self.cert_var).pack(
            side="left", padx=12)
        self.redir_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="跟随重定向", variable=self.redir_var).pack(
            side="left")

        nb = ttk.Notebook(f)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        reqf = ttk.Frame(nb)
        nb.add(reqf, text="请求")
        ttk.Label(reqf, text="请求头（每行一个 Key: Value，例如 "
                            "Authorization: Bearer xxx）").pack(
            anchor="w", padx=6, pady=(6, 0))
        self.headers_text = ScrolledText(reqf, height=4)
        theme.style_text(self.headers_text, mono=True)
        self.headers_text.pack(fill="x", padx=6)
        ttk.Label(reqf, text="请求体（POST / PUT / PATCH 时使用）").pack(
            anchor="w", padx=6, pady=(6, 0))
        self.body_text = ScrolledText(reqf, height=7)
        theme.style_text(self.body_text, mono=True)
        self.body_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        respf = ttk.Frame(nb)
        nb.add(respf, text="响应")
        self.status_var = tk.StringVar(value="填写 URL 后点「发送」")
        ttk.Label(respf, textvariable=self.status_var).pack(
            anchor="w", padx=6, pady=6)
        self.resp_text = ScrolledText(respf, height=14)
        theme.style_text(self.resp_text, mono=True)
        self.resp_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.frame = f
        self._poll()
        return f

    # ---------------- 发送 ----------------
    def _send(self):
        url = self.url_var.get().strip()
        if not url:
            self.status_var.set("请先填写 URL")
            return

        method = self.method_var.get()
        headers = self.headers_text.get("1.0", "end").rstrip("\n")
        body = self.body_text.get("1.0", "end").rstrip("\n")
        options = {
            "ignore_proxy": self.proxy_var.get(),
            "ignore_cert": self.cert_var.get(),
            "follow_redirect": self.redir_var.get(),
        }

        self.send_btn.configure(state="disabled")
        self.status_var.set("请求中…")
        self.resp_text.delete("1.0", "end")

        def work():
            result = client.send_request(method, url, headers, body, **options)
            self._results.put(result)

        threading.Thread(target=work, name="api-tester", daemon=True).start()

    def _poll(self):
        """在主线程里消费后台线程的结果（Tkinter 只能在主线程更新）。"""
        try:
            while True:
                self._show(self._results.get_nowait())
        except queue.Empty:
            pass
        try:
            self.frame.after(150, self._poll)
        except Exception:
            pass

    def _show(self, r):
        self.send_btn.configure(state="normal")

        if r.error:
            self.status_var.set("请求失败：%s" % r.error)
            self.resp_text.insert("end", r.error)
            self.log("接口调试失败：%s %s -> %s" % (
                self.method_var.get(), self.url_var.get(), r.error))
            return

        size = len(r.body.encode("utf-8"))
        self.status_var.set("%d %s · %d ms · %d 字节" % (
            r.status, r.reason, r.elapsed_ms, size))

        lines = ["=== 响应头 ==="]
        lines += ["%s: %s" % (k, v) for k, v in r.headers]
        lines += ["", "=== 响应体 ==="]
        pretty = client.pretty_json(r.body)
        lines.append(pretty if pretty else r.body)
        self.resp_text.insert("end", "\n".join(lines))

        self.log("%s %s -> %s (%d ms)" % (
            self.method_var.get(), self.url_var.get(), r.status, r.elapsed_ms))
