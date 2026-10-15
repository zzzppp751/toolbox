#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反向代理的配置模型（纯数据，不依赖界面）。"""

import json


class ProxyConfig:
    def __init__(self):
        self.listen_host = "127.0.0.1"
        self.listen_port = 8021
        self.enable_cors = True
        # 规则：{"local": "/xcx/", "upstream": "https://www.qbjzhly.cn/xcx/"}
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
        try:
            cfg.listen_port = int(data.get("listen_port", cfg.listen_port))
        except (TypeError, ValueError):
            pass
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
