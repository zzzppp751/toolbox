#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具箱核心：工具基类与运行时上下文。

新增一个功能工具，只需三步：
  1. 在 tools/ 下新建一个模块（.py 文件或包）；
  2. 定义 BaseTool 的子类，设置 id/name 并实现 build(parent)；
  3. 需要的话再实现 start/stop/close/on_show/on_hide。

它会被自动发现并出现在工具箱左侧的功能列表中，无需修改主程序。
"""

import os
import sys


def get_app_dir():
    """返回应用根目录（配置、资源放这里）。

    打包成单文件 exe 后，__file__ 指向临时解压目录（退出即清理），
    因此这种情况改用 exe 自身所在目录。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ToolContext:
    """传给每个工具的运行时上下文（共享资源的统一入口）。

    工具不要自己去碰根窗口或写日志文件，通过 context 拿：
      - context.log(msg)          写到底部共享日志（线程安全）
      - context.app_dir           应用根目录
      - context.config_path(name) 某个工具的配置文件路径
    """

    def __init__(self, root, log_queue):
        self.root = root
        self.log_queue = log_queue
        self.app_dir = get_app_dir()

    def log(self, msg):
        """写一条日志到底部共享日志面板（可从任意线程调用）。"""
        self.log_queue.put(str(msg))

    def config_path(self, name, ext="json"):
        """返回工具配置文件路径，统一放在 <app_dir>/config/<name>.<ext>。"""
        cfg_dir = os.path.join(self.app_dir, "config")
        os.makedirs(cfg_dir, exist_ok=True)
        return os.path.join(cfg_dir, "%s.%s" % (name, ext))


class BaseTool:
    """所有工具的基类（按约定实现，无需继承 ABC）。"""

    # ---- 元数据（子类覆盖）----
    id = ""                 # 唯一标识，建议用英文
    name = "未命名工具"      # 显示在左侧列表的名字
    description = ""        # 一句话说明（可选，用于提示）
    order = 100             # 排序，越小越靠前

    def __init__(self, context):
        self.context = context
        self.frame = None

    # ---- 必须实现 ----
    def build(self, parent):
        """构建并返回该工具的界面（ttk.Frame）。主程序只会调用一次。"""
        raise NotImplementedError("工具必须实现 build(parent)")

    # ---- 可选钩子 ----
    def on_show(self):
        """被切换到前台时触发。"""

    def on_hide(self):
        """被切到后台时触发。"""

    def start(self):
        """启动该工具的核心服务（若有）。"""

    def stop(self):
        """停止该工具的核心服务（若有）。"""

    def close(self):
        """应用退出时清理，默认停掉服务。"""
        try:
            self.stop()
        except Exception:
            pass

    @property
    def running(self):
        """是否正在运行，用于在左侧列表加「运行中」标记。"""
        return False

    # ---- 便捷方法 ----
    def log(self, msg):
        self.context.log(msg)
