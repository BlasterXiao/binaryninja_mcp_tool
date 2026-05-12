# Binary Ninja MCP Server

在 Binary Ninja **GUI 进程**内运行 MCP（Streamable HTTP），供 Cursor 等客户端通过 `POST /mcp` + Bearer Token 调用逆向分析工具。

**面向用户的说明文档**（功能介绍、使用场景、`doc/` 与 `spec/` 分工等）见 [doc/README.md](doc/README.md) 与 [doc/用户指南.md](doc/用户指南.md)。

## 安装

1. 将整个 `bn-mcp-server` 文件夹复制到 Binary Ninja 用户插件目录，例如：
   - Windows: `%APPDATA%\Binary Ninja\plugins\`
   - macOS: `~/Library/Application Support/Binary Ninja/plugins/`
   - Linux: `~/.binaryninja/plugins/`

2. 在 **Binary Ninja 内置 Python** 中安装依赖：

   - **推荐**：`Shift+Ctrl+P` / `Shift+Command+P` → 输入 `Install Python Package` → 选择 **Install Python Package**，按提示安装 `requirements.txt` 中的包（如 `fastmcp`、`uvicorn`、`starlette`、`pydantic`）。
   - 或在 Binary Ninja 的 **Python 控制台** 中执行：  
     `pip install -r "<插件目录>/bn-mcp-server/requirements.txt"`

3. 重启 Binary Ninja，菜单 **Plugins → MCP Server → Start**。

### 菜单 Start / Stop / Settings

- **Start**：服务已运行时该项会**置灰**（`PluginCommand` 的 `is_valid`）；逻辑上也会拦截重复启动（以 uvicorn 是否在跑为准）。
- **Stop**：仅在服务运行时可选。
- **Settings**：使用 `get_int_input` 等官方交互 API；若旧版插件用了不存在的 `get_text_input`，表现为点击无反应，请更新本仓库 `ui/settings.py`。

## 配置 Cursor (`mcp.json`)

```json
{
  "mcpServers": {
    "binary-ninja-pro": {
      "url": "http://127.0.0.1:9090/mcp",
      "headers": {
        "Authorization": "Bearer <从 Plugins → MCP Server → Status 复制>"
      }
    }
  }
}
```

Token 与端口保存在 `%BINARY_NINJA_USER_DIRECTORY%/bn_mcp_server_config.json`（或 `~/.binaryninja/bn_mcp_server_config.json`）。

### Cursor 提示「does not support dynamic client registration」

插件已在 OAuth 元数据中声明 **`registration_endpoint`**，并实现了 **`POST /oauth/register`**（RFC 7591 占位实现），用于通过 Cursor 的兼容性检查。  
实际访问 MCP 仍使用 **Status 里的 Bearer Token**（与 OAuth 换到的 `access_token` 相同）。

### Cursor 仍打开浏览器 / `unsupported_response_type`

**Streamable HTTP** 下 Cursor 会走 **OAuth 授权码 + PKCE**（日志里会出现 `Redirect to authorization`、`needsAuth`）。  
仅配置 `mcp.json` 的 `headers.Authorization` **不能替代**这一步浏览器回调。

插件已实现最小 **`GET /oauth/authorize`**（302 带 `code`）与 **`POST /oauth/token`**（用 `code`+`code_verifier` 换 token）。  
在浏览器里完成一次授权后，拿到的 token 与 **Plugins → MCP Server → Status** 中的预共享 Token **一致**。  
若仍手动配 `headers`，建议使用 **`"Authorization": "Bearer <token>"`**（与 Status 完全一致）；也兼容仅填裸 token 的写法。

### 如何确认插件已更新、如何覆盖安装

1. **插件目录**（用户插件，优先于内置）：  
   `%APPDATA%\Binary Ninja\plugins\bn-mcp-server\`  
   （完整路径一般为 `C:\Users\<你>\AppData\Roaming\Binary Ninja\plugins\bn-mcp-server\`）
2. **确认已拷入新版本**（任选其一）：  
   - 存在文件 **`bv_hooks.py`**（全局 BinaryView 绑定，新版本才有）；  
   - 打开 **`context.py`**，搜索 **`_fetch_ui_binary_view`**，能搜到即包含「主线程取 UI 视图」逻辑；  
   - 资源管理器里对比 **`context.py` 修改日期**是否晚于你桌面/仓库里的拷贝时间。
3. **更新步骤**：**退出 Binary Ninja** → 用本仓库整个 **`bn-mcp-server` 文件夹覆盖**上述目录 → 再启动 BN。仅改一两个文件时也要保证 **`__init__.py`、`bv_hooks.py`、`context.py`、`plugin_main.py`** 一致。
4. **Python 解释器**：在 BN **Settings → Python** 指向本机 Python 3.13 时，依赖需装在该环境中，例如：  
   `"<你的python313>\python.exe" -m pip install -r "<插件路径>\requirements.txt"`  
   与 BN 实际加载的必须是**同一** `python.exe`，否则会出现「能起 uvicorn、但插件逻辑异常」的错觉。

### `No BinaryView available` / MCP 工具在 ScriptingProvider 里报错

常见原因与处理：

1. **插件不是最新**：按上一节覆盖安装并重启 BN。
2. **先起了 MCP、后开的样本**：新版本会在 **`BinaryViewType.add_binaryview_finalized_event`** 等全局回调里自动绑定当前打开的 `BinaryView`（见 `bv_hooks.py`）。若仍报错，可先 **Stop → 再 Start** 一次 MCP，或切换一下标签页再试。
3. **Start 时未绑定到当前样本**：菜单 **Plugins → MCP Server → Start** 时，部分版本里 `PluginCommand` 的 `ctx.binaryView` 可能为空。`plugin_main` 会回退到 **当前 UI 焦点下的 BinaryView**；若仍失败，请先**用鼠标点一下**反汇编/十六进制窗口再点 Start。
4. **HTTP 在工作线程**：`interaction.get_current_binary_view()` 等需在**主线程**调用；`try_get_active_binary_view()` 已用 `mainthread.execute_on_main_thread_and_wait`；成功解析后会把视图**写入缓存**，与 [Binary Ninja Python API](https://api.binary.ninja/) 中 `binaryninja.mainthread` 的用法一致。

### Cursor 连接失败（HTTP 404 / Invalid OAuth error response）

1. **`url` 必须带路径 `/mcp`**，例如 `http://127.0.0.1:9090/mcp`，不要写成 `http://127.0.0.1:9090`。
2. **必须配置** `headers.Authorization`：`Bearer ` 与 Status 里显示的 Token **完全一致**（无多余空格）。
3. Cursor 会访问 `/.well-known/oauth-authorization-server`（以及带路径的 `/mcp` 变体）等发现地址；插件返回**不含 `null` 字段**的 JSON（Cursor 严格校验会拒绝 `null`）。可在浏览器核对：  
   - `http://127.0.0.1:9090/.well-known/oauth-authorization-server`  
   - `http://127.0.0.1:9090/.well-known/oauth-authorization-server/mcp`

### 关于 `websockets` / `uvicorn` 的 DeprecationWarning

来自 **uvicorn** 依赖的旧版 `websockets` API，不影响 MCP 使用；升级 `websockets` 或等待 uvicorn 适配后可消失，可暂时忽略。

## 功能概览

- **63+ 工具**：二进制视图、函数/HLIL/LLIL/MLIL、交叉引用、符号、字符串、类型、重命名与注释、CFG、Patch、分析控制、启发式漏洞辅助等。
- **可选 Resources / Prompts**（取决于 FastMCP 版本）。
- **Bearer 认证**（FastMCP `RemoteAuthProvider` + 预共享 Token）+ **速率限制**（Starlette 中间件）。

## 说明

- 需 **已打开二进制** 后启动服务；当前活动视图会作为默认 `BinaryView`。
- 写操作（Patch、重命名等）在可能时通过 `execute_on_main_thread_and_wait` 执行。
- 部分 API 随 Binary Ninja 版本略有差异，工具内已做兼容与降级。

## 许可

MIT
