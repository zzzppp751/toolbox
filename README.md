# 工具箱（Toolbox）

一个用 Python + Tkinter 写的本地工具箱，采用**插件式架构**：主程序只负责左侧功能列表、右侧面板和底部日志，具体功能以插件形式放在 `tools/` 目录下，**丢进去就自动被发现**，无需改动主程序。

当前内置功能：**本地反向代理**。

## 特性

- **零第三方依赖**：只用 Python 标准库（`tkinter` + `http.server` + `http.client`）。
- **插件式扩展**：新增功能 = 在 `tools/` 下加一个模块。
- **界面与逻辑分离**：代理引擎不依赖界面，可被 Web / 命令行等其它前端复用。
- **配置隔离**：每个工具独立配置文件，互不干扰。

## 目录结构

```
toolbox/
├─ main.py                     主程序：功能列表 + 面板 + 共享日志
├─ run_toolbox.bat             双击启动（Windows）
├─ core/
│  ├─ base.py                  BaseTool 基类 + ToolContext
│  └─ registry.py              扫描 tools/ 自动发现工具
└─ tools/
   └─ proxy/                   本地反向代理插件
      ├─ config.py             配置数据模型
      ├─ engine.py             代理引擎（纯逻辑，不依赖界面）
      └─ tool.py               界面层
```

## 运行

需要 Python 3.8+（且安装时勾选了 `tcl/tk`，Windows 官方安装包默认包含）。

```bash
py toolbox/main.py
```

或双击 `toolbox/run_toolbox.bat`。

## 内置功能：本地反向代理

把本地路径转发到指定上游地址，常用于解决前端开发时的跨域问题。

1. **监听设置**：填监听地址（默认 `127.0.0.1`）和端口（默认 `8021`），按需勾选"启用 CORS"。
2. **转发规则**：填"本地路径前缀 → 上游地址"，例如
   - `/xcx/` → `https://www.example.com/xcx/`
   - `/api/` → `https://api.example.com/v1/`
3. 点 **启动代理**，然后前端直接请求 `http://localhost:8021/...` 即可。

### 关于 CORS

浏览器判断"同源"看 `协议 + 域名 + 端口` 三者是否完全一致。前端在 `:8020`、代理在 `:8021` 时端口不同，仍属跨域。勾选"启用 CORS"后，代理会：

- 自行应答 `OPTIONS` 预检请求（绕开上游重定向导致的预检失败）；
- 给响应补上 `Access-Control-Allow-*` 头。

## 如何新增一个工具

在 `tools/` 下新建模块，定义 `BaseTool` 子类即可：

```python
from core.base import BaseTool
from tkinter import ttk

class MyTool(BaseTool):
    id = "my_tool"
    name = "我的工具"
    order = 30                      # 侧栏排序，越小越靠前

    def build(self, parent):        # 构建界面，返回一个 Frame
        f = ttk.Frame(parent)
        ttk.Label(f, text="Hello").pack()
        return f

    def start(self): ...            # 可选：启动服务
    def stop(self): ...             # 可选：停止服务

    @property
    def running(self):              # 运行中侧栏会显示 ●
        return False
```

日志用 `self.log("...")`（线程安全，输出到底部共享日志）；配置文件路径用 `self.context.config_path("my_tool")`。

> **记得登记**：把模块名加入 `toolbox/tools/__init__.py` 的 `TOOL_MODULES` 列表。
> 源码运行时即使不登记也能靠自动扫描发现，但打包成 exe 后必须靠这份清单才能被收录。

## 打包为 exe

```bash
py -m pip install pyinstaller
py build_exe.py                    # 生成 dist/Toolbox.exe
py build_exe.py --name 工具箱       # 自定义名字
py build_exe.py --console          # 保留控制台，便于看报错
```

产物在 `dist/<名字>.exe`，单文件、免装 Python。

> **为什么不用直接跑 PyInstaller？**
> 工具箱的功能是运行时动态加载的，PyInstaller 的静态分析发现不了，
> 必须显式声明 `--hidden-import`。`build_exe.py` 会自动读取 `TOOL_MODULES`
> 清单逐个加上，以后新增工具无需改动打包命令。
> 另外 PyInstaller 冻结后 `pkgutil` 无法枚举已打包模块，所以清单是打包版的唯一可靠来源。

## 其它

仓库根目录还保留了早期版本的单文件脚本：

- `proxy.py`：只做转发、规则写死的简易代理；
- `proxy_gui.py`：带图形界面的单文件版代理工具。

`toolbox/` 是重构后的推荐版本。

## License

未指定。如需开源请自行添加 LICENSE 文件。
