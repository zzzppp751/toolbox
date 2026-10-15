#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具发现：收集 tools/ 包下的所有 BaseTool 子类。

两种发现方式并用：
  1. 显式清单 —— 读取 tools.TOOL_MODULES（打包成 exe 后唯一可靠的方式）；
  2. 自动扫描 —— 用 pkgutil 扫描 tools/ 目录（源码运行时方便，免登记）。
两者结果取并集，因此新增工具即使忘了登记，源码运行时也能被看到。
"""

import importlib
import inspect
import pkgutil
import traceback

from core.base import BaseTool

TOOLS_PACKAGE = "tools"


def _iter_module_names(package):
    """返回待扫描的模块名集合（显式清单 ∪ 自动扫描结果）。"""
    names = set()

    declared = getattr(package, "TOOL_MODULES", None) or []
    names.update(str(n).strip() for n in declared if str(n).strip())

    # 自动扫描：源码运行时可用；打包成 exe 后 pkgutil 无法枚举 PYZ，失败可忽略
    try:
        for _, modname, _ in pkgutil.iter_modules(package.__path__):
            if modname.startswith("_"):
                continue
            names.add(modname)
    except Exception:
        pass

    return sorted(names)


def discover_tools(package_name=TOOLS_PACKAGE):
    """返回所有已发现工具类（按 order 排序）。

    单个工具导入失败不影响其它工具，错误会打印出来便于排查。
    """
    try:
        package = importlib.import_module(package_name)
    except Exception:
        traceback.print_exc()
        return []

    found = {}

    for modname in _iter_module_names(package):
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
