#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具自动发现：扫描 tools/ 包，收集所有 BaseTool 子类。"""

import importlib
import inspect
import pkgutil
import traceback

from core.base import BaseTool

TOOLS_PACKAGE = "tools"


def discover_tools(package_name=TOOLS_PACKAGE):
    """扫描指定包下的所有模块，返回其中定义的 BaseTool 子类（已排序）。

    单个工具导入失败不会影响其它工具，错误会打印出来便于排查。
    """
    package = importlib.import_module(package_name)
    found = {}

    for _, modname, _ in pkgutil.iter_modules(package.__path__):
        full = "%s.%s" % (package_name, modname)
        try:
            module = importlib.import_module(full)
        except Exception:
            traceback.print_exc()
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseTool) or obj is BaseTool:
                continue
            key = getattr(obj, "id", None) or "%s.%s" % (
                obj.__module__, obj.__name__)
            # 只收第一个（避免同一工具被多个模块重复导入时覆盖）
            found.setdefault(key, obj)

    return sorted(found.values(), key=lambda t: getattr(t, "order", 100))
