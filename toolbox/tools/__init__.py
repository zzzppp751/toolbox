"""工具箱的插件目录。

每个子模块（文件或包）= 一个功能工具。

新增工具时，请把这个模块名登记到下面的 TOOL_MODULES 里，例如：

    TOOL_MODULES = ["proxy", "my_new_tool"]

为什么必须登记？
  - 源码运行时，core.registry 能用 pkgutil 自动扫描发现新工具，不登记也能用；
  - 但打包成 exe 后，PyInstaller 无法在运行时枚举打包进 PYZ 的模块
    （pkgutil 的限制），必须依靠这份清单在构建时把它们打进去。
  登记之后，用仓库根目录的 build_exe.py 打包即可，会自动带上。
"""

TOOL_MODULES = ["proxy"]
