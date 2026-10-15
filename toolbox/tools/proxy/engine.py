#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反向代理引擎：纯逻辑，不依赖界面，可被任意前端复用。

引擎接受一个 config 对象（需具备 listen_host / listen_port /
enable_cors / routes 属性）和一个 log 回调。
"""

import http.client
import threading
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 不转发的逐跳（hop-by-hop）头
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}
# 由本代理自行管理的 CORS 头（上游带的一律丢弃，避免冲突）
CORS_HEADERS = {
    "access-control-allow-origin",
    "access-control-allow-credentials",
    "access-control-allow-methods",
    "access-control-allow-headers",
    "access-control-expose-headers",
    "access-control-max-age",
}


def make_handler(config, log):
    """根据配置与日志回调，动态生成请求处理器类。"""

    class ProxyHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "LocalReverseProxy/1.0"

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

        def _find_route(self, path):
            best = None
            for r in config.routes:
                lp = r["local"]
                if path.startswith(lp):
                    if best is None or len(lp) > len(best["local"]):
                        best = r
            return best

        def _handle(self):
            # 0) CORS 预检：本地直接应答，避免被上游重定向拦截
            if config.enable_cors and self.command == "OPTIONS":
                self.send_response(204)
                self._add_cors()
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()
                return

            route = self._find_route(self.path)
            if route is None:
                self._send_simple(404, "No proxy route for: %s" % self.path)
                return

            up = urllib.parse.urlsplit(route["upstream"])
            scheme = up.scheme or "http"
            host = up.hostname
            port = up.port or (443 if scheme == "https" else 80)
            base_path = up.path or "/"

            parsed = urllib.parse.urlsplit(self.path)
            tail = parsed.path[len(route["local"]):]
            if not base_path.endswith("/") and tail:
                base_path += "/"
            upstream_path = base_path + tail
            if parsed.query:
                upstream_path += "?" + parsed.query

            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
            except ValueError:
                length = 0
            body = self.rfile.read(length) if length > 0 else None

            fwd_headers = {}
            for key in self.headers.keys():
                lk = key.lower()
                if lk in HOP_BY_HOP or lk == "host" or lk in CORS_HEADERS:
                    continue
                fwd_headers[key] = self.headers[key]

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
                log("上游错误 [%s %s]: %s" % (self.command, upstream_path, exc))
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


class ProxyEngine:
    """按配置启停代理服务（在独立线程运行）。"""

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
