#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反向代理：把本地 8021 端口的请求转发到上游服务器，并补齐 CORS 支持。

  http://localhost:8021/yj/   => https://www.qbjzhly.cn/yj/
  http://localhost:8021/xcx/  => https://www.qbjzhly.cn/xcx/

说明：
  - 上游 www.qbjzhly.cn 强制 http->https，因此这里直接用 https 转发，
    避免被 301 跳走（CORS 预检请求也不允许被重定向）。
  - 浏览器 localhost:8020 访问 localhost:8021 属于跨域，本代理会自行补上
    CORS 响应头，并直接应答 OPTIONS 预检，确保 XHR/fetch 可用。
  - 仅依赖 Python 标准库。
"""

import sys
import ssl
import http.client
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------- 配置区域 ----------
UPSTREAM_SCHEME = "https"          # 上游协议（强制 https，避免 301 跳走）
UPSTREAM_HOST = "www.qbjzhly.cn"
UPSTREAM_PORT = 443                # https 默认 443
UPSTREAM_TIMEOUT = 30              # 秒

# 本地监听
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8021

# 本地路径前缀 -> 上游路径前缀（前缀保持一致即可，其余路径原样透传）
ROUTES = {
    "/yj/": "/yj/",
    "/xcx/": "/xcx/",
}

# 本地对外暴露的源（用于回写 Location 重定向，避免浏览器逃逸出代理）
PROXY_ORIGIN = "http://localhost:8021"
# --------------------------------

# 不转发的逐跳（hop-by-hop）头
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}
# 由本代理自行管理的 CORS 头（来自上游的一律丢弃，避免冲突）
CORS_HEADERS = {
    "access-control-allow-origin",
    "access-control-allow-credentials",
    "access-control-allow-methods",
    "access-control-allow-headers",
    "access-control-expose-headers",
    "access-control-max-age",
}


class ReverseProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LocalReverseProxy/1.0"

    def _add_cors(self):
        """根据请求里的 Origin，补上 CORS 响应头。"""
        origin = self.headers.get("Origin")
        if origin:
            # 携带凭据（cookie）时必须回显具体源，不能用 "*"
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

    def _handle(self):
        # 0. CORS 预检：直接应答，不转发（防止被上游 301 重定向拦截）
        if self.command == "OPTIONS":
            self.send_response(204)
            self._add_cors()
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
            return

        # 1. 匹配路由
        route = None
        for prefix in ROUTES:
            if self.path.startswith(prefix):
                route = prefix
                break
        if route is None:
            self.send_error(404, "No proxy route for: %s" % self.path)
            return

        # 2. 还原上游真实路径（保留 query string）
        parsed = urllib.parse.urlsplit(self.path)
        upstream_path = parsed.path
        if parsed.query:
            upstream_path += "?" + parsed.query

        # 3. 读取请求体
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length > 0 else None

        # 4. 透传请求头（去掉 hop-by-hop、Host 和上游 CORS 头）
        fwd_headers = {}
        for key in self.headers.keys():
            lk = key.lower()
            if lk in HOP_BY_HOP or lk == "host" or lk in CORS_HEADERS:
                continue
            fwd_headers[key] = self.headers[key]

        # 5. 转发到上游
        if UPSTREAM_SCHEME == "https":
            conn = http.client.HTTPSConnection(
                UPSTREAM_HOST, UPSTREAM_PORT, timeout=UPSTREAM_TIMEOUT)
        else:
            conn = http.client.HTTPConnection(
                UPSTREAM_HOST, UPSTREAM_PORT, timeout=UPSTREAM_TIMEOUT)
        try:
            conn.request(self.command, upstream_path, body=body,
                         headers=fwd_headers)
            resp = conn.getresponse()
            resp_body = resp.read()

            # 6. 回写响应
            self.send_response(resp.status)

            # 6a. 若上游有 3xx 重定向，把主机改写为代理自身，避免浏览器逃逸
            location = resp.getheader("Location")
            for key, value in resp.getheaders():
                lk = key.lower()
                if lk in HOP_BY_HOP or lk in CORS_HEADERS:
                    continue
                if lk == "transfer-encoding":
                    # 已解码为完整字节，统一用 Content-Length 回传
                    continue
                if lk == "location" and location:
                    value = location.replace(
                        "https://" + UPSTREAM_HOST, PROXY_ORIGIN
                    ).replace(
                        "http://" + UPSTREAM_HOST, PROXY_ORIGIN)
                self.send_header(key, value)

            self.send_header("Content-Length", str(len(resp_body)))
            self._add_cors()
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(resp_body)
        except Exception as exc:
            import traceback
            sys.stderr.write("UPSTREAM ERROR [%s %s]: %s\n" % (
                self.command, upstream_path, traceback.format_exc()))
            self.send_error(502, "Bad gateway: %s" % exc)
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
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT),
                                 ReverseProxyHandler)
    print("反向代理已启动：http://%s:%d" % (LISTEN_HOST, LISTEN_PORT))
    print("  (https 转发到 %s://%s:%d)" % (
        UPSTREAM_SCHEME, UPSTREAM_HOST, UPSTREAM_PORT))
    for local, upstream in ROUTES.items():
        print("  %s*  -> %s://%s%s*" % (
            local, UPSTREAM_SCHEME, UPSTREAM_HOST, upstream))
    print("已启用 CORS（允许 localhost:8020 等跨域 XHR/fetch）。")
    print("按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭...")
        server.shutdown()


if __name__ == "__main__":
    main()
