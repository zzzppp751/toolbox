#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP 请求发送：纯逻辑，不依赖界面，可被任意前端复用。"""

import json
import ssl
import time
import urllib.error
import urllib.request


class Response:
    """一次请求的结果。"""

    def __init__(self):
        self.ok = False         # 是否拿到了服务器响应（含 4xx/5xx）
        self.status = 0
        self.reason = ""
        self.headers = []       # [(key, value)]
        self.body = ""
        self.elapsed_ms = 0
        self.error = ""         # 网络层面的错误信息


def parse_headers(text):
    """把多行 "Key: Value" 文本解析成 dict，忽略空行和 # 注释。"""
    headers = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


def _build_opener(ignore_proxy, ignore_cert):
    handlers = []
    if ignore_proxy:
        handlers.append(urllib.request.ProxyHandler({}))

    ctx = ssl.create_default_context()
    if ignore_cert:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    handlers.append(urllib.request.HTTPSHandler(context=ctx))

    return urllib.request.build_opener(*handlers)


def send_request(method, url, headers_text="", body="", timeout=30,
                 ignore_proxy=True, ignore_cert=False, follow_redirect=True):
    """发送一次 HTTP 请求，返回 Response（网络错误也通过 Response.error 返回）。"""
    resp = Response()

    url = (url or "").strip()
    if not url:
        resp.error = "请填写 URL"
        return resp
    if not url.lower().startswith(("http://", "https://")):
        url = "http://" + url

    headers = parse_headers(headers_text)
    if not any(k.lower() == "user-agent" for k in headers):
        headers["User-Agent"] = "Toolbox/1.0"

    data = body.encode("utf-8") if body else None

    opener = _build_opener(ignore_proxy, ignore_cert)
    if not follow_redirect:
        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener.add_handler(_NoRedirect())

    req = urllib.request.Request(url, data=data, method=(method or "GET").upper())
    for key, value in headers.items():
        req.add_header(key, value)

    start = time.time()
    try:
        with opener.open(req, timeout=timeout) as r:
            raw = r.read()
            resp.status = r.status
            resp.reason = getattr(r, "reason", "") or ""
            resp.headers = list(r.headers.items())
            resp.body = _decode(raw, r.headers.get("Content-Type", ""))
            resp.ok = True
    except urllib.error.HTTPError as e:      # 4xx / 5xx 也算“拿到响应”
        raw = e.read()
        resp.status = e.code
        resp.reason = e.reason or ""
        resp.headers = list(e.headers.items()) if e.headers else []
        resp.body = _decode(
            raw, (e.headers.get("Content-Type", "") if e.headers else ""))
        resp.ok = True
    except Exception as e:                   # 连不上、超时、DNS 失败等
        resp.error = "%s: %s" % (type(e).__name__, e)

    resp.elapsed_ms = int((time.time() - start) * 1000)
    return resp


def _decode(raw, content_type):
    charset = "utf-8"
    if "charset=" in (content_type or ""):
        charset = content_type.split("charset=")[-1].strip().split(";")[0].strip()
    try:
        return raw.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def pretty_json(text, indent=2):
    """尝试把文本美化输出；不是合法 JSON 时返回 None。"""
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=indent)
    except Exception:
        return None
