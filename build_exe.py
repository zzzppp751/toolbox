#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把工具箱打包成单文件 exe。

用法（在仓库根目录执行）：
    py build_exe.py                 # 生成 dist/Toolbox.exe
    py build_exe.py --name 工具箱    # 自定义名字
    py build_exe.py --console       # 保留控制台窗口，便于看报错

为什么要单独写这个脚本？
    工具箱里的功能是运行时动态加载的，PyInstaller 的静态分析发现不了它们，
    所以必须显式把它们声明成 --hidden-import。
    本脚本会自动读取 toolbox/tools/__init__.py 里的 TOOL_MODULES 清单，
    逐个加上；以后新增工具只要在那个清单里登记一行，这里无需改动。
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TOOLBOX_DIR = os.path.join(ROOT, "toolbox")


def read_tool_modules():
    """读取工具清单（来自 toolbox/tools/__init__.py 的 TOOL_MODULES）。"""
    sys.path.insert(0, TOOLBOX_DIR)
    try:
        import tools  # noqa: WPS433
    except Exception as exc:  # noqa
        print("读取工具清单失败：%s" % exc)
        return []
    return [str(m).strip() for m in (getattr(tools, "TOOL_MODULES", []) or [])
            if str(m).strip()]


def main():
    parser = argparse.ArgumentParser(description="打包工具箱为单文件 exe")
    parser.add_argument("--name", default="Toolbox", help="exe 名称（默认 Toolbox）")
    parser.add_argument("--console", action="store_true",
                        help="保留控制台窗口（调试用；正式版不要加）")
    args = parser.parse_args()

    modules = read_tool_modules()
    if not modules:
        print("警告：工具清单为空，打包后可能看不到任何功能。")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "-F", "--clean", "--noconfirm",
        "--name", args.name,
        "--paths", TOOLBOX_DIR,
        "--console" if args.console else "--windowed",
    ]
    for modname in modules:
        cmd += ["--hidden-import", "tools.%s" % modname]
    cmd.append(os.path.join(TOOLBOX_DIR, "main.py"))

    print("工具清单 : %s" % (", ".join(modules) or "(空)"))
    print("输出     : dist/%s.exe" % args.name)
    print("执行命令 : %s" % " ".join(cmd))
    print("-" * 60)

    code = subprocess.call(cmd, cwd=ROOT)
    if code == 0:
        print("-" * 60)
        print("打包完成：%s" % os.path.join(ROOT, "dist", args.name + ".exe"))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
