#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地反向代理工具（图形界面版）

功能：
  - 自定义监听地址与端口
  - 多条转发规则：本地路径前缀 -> 上游地址（可含 scheme://host:port/path）
  - 一键启动 / 停止
  - 可选开启 CORS（自动应答 OPTIONS 预检 + 补 CORS 响应头）
  - 实时日志
  - 配置保存 / 加载（proxy_config.json）

只依赖 Python 标准库（tkinter + http.server + http.client）。
"""

import json
import os
import queue
import sys
import threading
import time
import traceback
import urllib.parse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText


# ------------------------- 常量 -------------------------
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}
CORS_HEADERS = {
    "access-control-allow-origin",
    "access-control-allow-credentials",
    "access-control-allow-methods",
    "access-control-allow-headers",
    "access-control-expose-headers",
    "access-control-max-age",
}
DEFAULT_CONFIG_FILE = "proxy_config.json"


def app_dir():
    """返回配置文件应存放的目录。

    打包成单文件 exe 后，__file__ 指向临时解压目录（会随退出被清理），
    因此这种情况下改用 exe 自身所在目录。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ------------------------- 配置 -------------------------
class ProxyConfig:
    def __init__(self):
        self.listen_host = "127.0.0.1"
        self.listen_port = 8021
        self.enable_cors = True
        # 每条规则：{"local": "/xcx/", "upstream": "https://www.qbjzhly.cn/xcx/"}
        self.routes = []

    def to_dict(self):
        return {
            "listen_host": self.listen_host,
            "listen_port": self.listen_port,
            "enable_cors": self.enable_cors,
            "routes": list(self.routes),
        }

    @classmethod
    def from_dict(cls, data):
        cfg = cls()
        cfg.listen_host = str(data.get("listen_host", cfg.listen_host))
        cfg.listen_port = int(data.get("listen_port", cfg.listen_port))
        cfg.enable_cors = bool(data.get("enable_cors", cfg.enable_cors))
        routes = []
        for r in data.get("routes", []):
            local = str(r.get("local", "")).strip()
            upstream = str(r.get("upstream", "")).strip()
            if local and upstream:
                routes.append({"local": local, "upstream": upstream})
        cfg.routes = routes
        return cfg

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# ------------------------- 代理处理逻辑 -------------------------
def make_handler(config, log):
    """根据配置与日志回调，动态生成一个请求处理器类。"""

    class ProxyHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "LocalReverseProxy/1.0"

        # ---- CORS 头 ----
        def _add_cors(self):
            origin = self.headers.get("Origin")
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Credentials", "true")
            else:
                self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header(
                "Access-Control-Allow-Methods",
                "GET, POST, PUT, DELETE, PATCH, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization, X-Requested-With, *")
            self.send_header("Access-Control-Max-Age", "86400")

        # ---- 简化的错误响应（也带 CORS，方便前端看到真实错误）----
        def _send_simple(self, code, message):
            body = message.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if config.enable_cors:
                self._add_cors()
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        # ---- 选最长匹配的本地前缀 ----
        def _find_route(self, path):
            best = None
            for r in config.routes:
                lp = r["local"]
                if path.startswith(lp):
                    if best is None or len(lp) > len(best["local"]):
                        best = r
            return best

        def _handle(self):
            # 0) CORS 预检：本地直接应答，避免被上游 301 等拦截
            if config.enable_cors and self.command == "OPTIONS":
                self.send_response(204)
                self._add_cors()
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()
                return

            # 1) 匹配路由
            route = self._find_route(self.path)
            if route is None:
                self._send_simple(
                    404, "No proxy route for: %s" % self.path)
                return

            up = urllib.parse.urlsplit(route["upstream"])
            scheme = up.scheme or "http"
            host = up.hostname
            if up.port:
                port = up.port
            else:
                port = 443 if scheme == "https" else 80
            base_path = up.path or "/"

            # 2) 拼装上游真实路径（本地前缀 -> 上游前缀，其余原样透传）
            parsed = urllib.parse.urlsplit(self.path)
            tail = parsed.path[len(route["local"]):]
            if not base_path.endswith("/") and tail:
                base_path += "/"
            upstream_path = base_path + tail
            if parsed.query:
                upstream_path += "?" + parsed.query

            # 3) 读取请求体
            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
            except ValueError:
                length = 0
            body = self.rfile.read(length) if length > 0 else None

            # 4) 透传请求头
            fwd_headers = {}
            for key in self.headers.keys():
                lk = key.lower()
                if lk in HOP_BY_HOP or lk == "host" or lk in CORS_HEADERS:
                    continue
                fwd_headers[key] = self.headers[key]

            # 5) 转发
            conn_cls = (http.client.HTTPSConnection if scheme == "https"
                        else http.client.HTTPConnection)
            conn = conn_cls(host, port, timeout=30)
            try:
                conn.request(self.command, upstream_path, body=body,
                             headers=fwd_headers)
                resp = conn.getresponse()
                resp_body = resp.read()

                self.send_response(resp.status)
                location = resp.getheader("Location")
                for key, value in resp.getheaders():
                    lk = key.lower()
                    if lk in HOP_BY_HOP or lk in CORS_HEADERS:
                        continue
                    if lk == "transfer-encoding":
                        continue
                    if lk == "location" and location:
                        value = location.replace(
                            "%s://%s" % (scheme, host),
                            "http://%s:%d" % (config.listen_host,
                                              config.listen_port))
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(resp_body)))
                if config.enable_cors:
                    self._add_cors()
                self.send_header("Connection", "close")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(resp_body)
            except Exception as exc:  # noqa
                log("上游错误 [%s %s]: %s" % (
                    self.command, upstream_path, exc))
                log(traceback.format_exc().rstrip())
                self._send_simple(502, "Bad gateway: %s" % exc)
            finally:
                conn.close()

        do_GET = _handle
        do_POST = _handle
        do_PUT = _handle
        do_DELETE = _handle
        do_HEAD = _handle
        do_PATCH = _handle
        do_OPTIONS = _handle

        def log_message(self, fmt, *args):
            log("%s - %s" % (self.address_string(), fmt % args))

    return ProxyHandler


# ------------------------- 代理引擎 -------------------------
class ProxyEngine:
    """负责按配置启停代理服务（在独立线程运行）。"""

    def __init__(self, config, log):
        self.config = config
        self.log = log
        self.httpd = None
        self.thread = None

    @property
    def running(self):
        return self.httpd is not None

    def start(self):
        if self.httpd:
            return
        handler = make_handler(self.config, self.log)
        self.httpd = ThreadingHTTPServer(
            (self.config.listen_host, self.config.listen_port), handler)
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, name="proxy-server", daemon=True)
        self.thread.start()
        self.log("代理已启动，监听 http://%s:%d" % (
            self.config.listen_host, self.config.listen_port))
        for r in self.config.routes:
            self.log("  %s*  ->  %s*" % (r["local"], r["upstream"]))

    def stop(self):
        if not self.httpd:
            return
        self.httpd.shutdown()
        self.httpd.server_close()
        self.httpd = None
        self.thread = None
        self.log("代理已停止。")


# ------------------------- 图形界面 -------------------------
class ProxyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("本地反向代理工具")
        self.root.geometry("760x560")
        self.root.minsize(680, 480)

        self.config = ProxyConfig()
        self.log_queue = queue.Queue()
        self.engine = ProxyEngine(self.config, self._log_async)

        self._build_ui()

        # 自动加载配置文件（若存在）
        default_path = os.path.join(app_dir(), DEFAULT_CONFIG_FILE)
        if os.path.exists(default_path):
            try:
                self.config = ProxyConfig.load(default_path)
                self.engine.config = self.config
                self._config_to_ui()
                self._log("已加载配置：%s" % default_path)
            except Exception as exc:  # noqa
                self._log("加载配置失败：%s" % exc)
        else:
            # 首次运行给一个示例规则
            self.config.routes = [
                {"local": "/yj/", "upstream": "https://www.qbjzhly.cn/yj/"},
                {"local": "/xcx/", "upstream": "https://www.qbjzhly.cn/xcx/"},
            ]
            self._config_to_ui()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_log()

    # ---------- 界面搭建 ----------
    def _build_ui(self):
        pad = {"padx": 6, "pady": 4}

        # 顶部：监听设置
        top = ttk.LabelFrame(self.root, text="监听设置")
        top.pack(fill="x", **pad)

        ttk.Label(top, text="监听地址：").grid(row=0, column=0, sticky="e", **pad)
        self.host_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(top, textvariable=self.host_var, width=18).grid(
            row=0, column=1, sticky="w", **pad)

        ttk.Label(top, text="端口：").grid(row=0, column=2, sticky="e", **pad)
        self.port_var = tk.StringVar(value="8021")
        ttk.Entry(top, textvariable=self.port_var, width=10).grid(
            row=0, column=3, sticky="w", **pad)

        self.cors_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="启用 CORS（跨域支持）",
                        variable=self.cors_var).grid(
            row=0, column=4, sticky="w", **pad)

        # 中部：转发规则
        rules = ttk.LabelFrame(self.root, text="转发规则（本地路径前缀 → 上游地址）")
        rules.pack(fill="both", expand=True, **pad)

        cols = ("local", "upstream")
        self.tree = ttk.Treeview(rules, columns=cols, show="headings", height=6)
        self.tree.heading("local", text="本地路径前缀")
        self.tree.heading("upstream", text="上游地址")
        self.tree.column("local", width=160, anchor="w")
        self.tree.column("upstream", width=460, anchor="w")
        self.tree.grid(row=0, column=0, columnspan=5, sticky="nsew", **pad)
        rules.rowconfigure(0, weight=1)
        rules.columnconfigure(0, weight=1)

        sb = ttk.Scrollbar(rules, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=5, sticky="ns", pady=4)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", self._on_row_double_click)

        # 输入行
        ttk.Label(rules, text="本地前缀：").grid(row=1, column=0, sticky="e", **pad)
        self.local_var = tk.StringVar()
        ttk.Entry(rules, textvariable=self.local_var, width=18).grid(
            row=1, column=1, sticky="w", **pad)

        ttk.Label(rules, text="上游地址：").grid(row=1, column=2, sticky="e", **pad)
        self.upstream_var = tk.StringVar()
        ttk.Entry(rules, textvariable=self.upstream_var, width=34).grid(
            row=1, column=3, columnspan=2, sticky="we", **pad)
        rules.columnconfigure(3, weight=1)

        btns = ttk.Frame(rules)
        btns.grid(row=2, column=0, columnspan=6, sticky="w", **pad)
        ttk.Button(btns, text="添加规则", command=self._add_route).pack(
            side="left", padx=4)
        ttk.Button(btns, text="更新选中", command=self._update_route).pack(
            side="left", padx=4)
        ttk.Button(btns, text="删除选中", command=self._delete_route).pack(
            side="left", padx=4)
        ttk.Button(btns, text="清空", command=self._clear_routes).pack(
            side="left", padx=4)

        # 控制区
        ctrl = ttk.Frame(self.root)
        ctrl.pack(fill="x", **pad)
        self.toggle_btn = ttk.Button(ctrl, text="启动代理",
                                     command=self._toggle_proxy)
        self.toggle_btn.pack(side="left", padx=4)
        ttk.Button(ctrl, text="保存配置",
                   command=self._save_config).pack(side="left", padx=4)
        ttk.Button(ctrl, text="加载配置",
                   command=self._load_config).pack(side="left", padx=4)
        self.status_var = tk.StringVar(value="未启动")
        ttk.Label(ctrl, textvariable=self.status_var,
                  foreground="#b00").pack(side="left", padx=12)

        # 日志区
        logf = ttk.LabelFrame(self.root, text="运行日志")
        logf.pack(fill="both", expand=True, **pad)
        self.log_text = ScrolledText(logf, height=8, state="disabled",
                                     wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    # ---------- 规则操作 ----------
    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.config.routes:
            self.tree.insert("", "end", values=(r["local"], r["upstream"]))

    def _validate_rule(self, local, upstream):
        local = local.strip()
        upstream = upstream.strip()
        if not local:
            messagebox.showwarning("提示", "请填写本地路径前缀，例如 /xcx/")
            return None
        if not local.startswith("/"):
            local = "/" + local
        if not upstream:
            messagebox.showwarning("提示", "请填写上游地址，例如 "
                                         "https://www.example.com/xcx/")
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
        idx = self.tree.index(sel[0])
        self.config.routes[idx] = rule
        self._refresh_tree()

    def _delete_route(self):
        sel = self.tree.selection()
        if not sel:
            return
        for item in sel:
            idx = self.tree.index(item)
            del self.config.routes[idx]
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

    # ---------- 配置读写 ----------
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

    def _config_to_ui(self):
        self.host_var.set(self.config.listen_host)
        self.port_var.set(str(self.config.listen_port))
        self.cors_var.set(self.config.enable_cors)
        self._refresh_tree()

    def _save_config(self):
        if self.engine.running:
            self._ui_to_config_soft()
        path = filedialog.asksaveasfilename(
            title="保存配置", defaultextension=".json",
            initialfile=DEFAULT_CONFIG_FILE,
            filetypes=[("JSON 配置", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            self._ui_to_config_soft()
            self.config.save(path)
            self._log("配置已保存：%s" % path)
        except Exception as exc:  # noqa
            messagebox.showerror("错误", "保存失败：%s" % exc)

    def _ui_to_config_soft(self):
        """保存/停止时不弹窗，尽量把界面值同步进配置。"""
        self.config.listen_host = self.host_var.get().strip() or "127.0.0.1"
        try:
            self.config.listen_port = int(self.port_var.get())
        except ValueError:
            pass
        self.config.enable_cors = bool(self.cors_var.get())

    def _load_config(self):
        path = filedialog.askopenfilename(
            title="加载配置", filetypes=[("JSON 配置", "*.json"),
                                        ("所有文件", "*.*")])
        if not path:
            return
        try:
            self.config = ProxyConfig.load(path)
            self.engine.config = self.config
            self._config_to_ui()
            self._log("配置已加载：%s" % path)
        except Exception as exc:  # noqa
            messagebox.showerror("错误", "加载失败：%s" % exc)

    # ---------- 启停 ----------
    def _toggle_proxy(self):
        if self.engine.running:
            self.engine.stop()
            self._set_running_ui(False)
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
                "启动失败",
                "无法监听 %s:%s\n%s\n\n（端口可能已被占用）" % (
                    self.config.listen_host, self.config.listen_port, exc))
            self.engine.httpd = None
            return
        self._set_running_ui(True)

    def _set_running_ui(self, running):
        if running:
            self.toggle_btn.configure(text="停止代理")
            self.status_var.set("运行中 ✔  http://%s:%d" % (
                self.config.listen_host, self.config.listen_port))
        else:
            self.toggle_btn.configure(text="启动代理")
            self.status_var.set("未启动")

    # ---------- 日志 ----------
    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_queue.put("[%s] %s" % (ts, msg))

    def _log_async(self, msg):
        # 来自代理线程，只入队，由主线程刷新
        self.log_queue.put(msg if msg.startswith("[") else
                           "[%s] %s" % (time.strftime("%H:%M:%S"), msg))

    def _poll_log(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", line + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(200, self._poll_log)

    # ---------- 关闭 ----------
    def _on_close(self):
        if self.engine.running:
            self.engine.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    ProxyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
