# Binary Ninja MCP Server 需求文档

**文档版本：** v1.0  
**日期：** 2026-03-23  
**协议：** HTTP（Streamable HTTP，符合 MCP 2025-06-18 规范）  
**目标环境：** Binary Ninja Pro（GUI 插件模式）

---

## 一、项目背景与目标

### 1.1 背景

Binary Ninja 是业界领先的可交互反汇编与反编译平台，具备深度的 Python API 支持和多层中间语言（BNIL）架构。Model Context Protocol（MCP）是由 Anthropic 推出的标准化 AI 工具接入协议，允许大型语言模型（LLM）通过统一接口访问外部工具和数据源。

本项目旨在将 Binary Ninja 的分析能力通过 MCP 协议暴露给 AI 助手（如 Cursor），从而实现 AI 辅助逆向工程的工作流。

### 1.2 版本约束

Binary Ninja Pro 版本不支持无头模式（Headless Mode），即无法在独立 Python 进程中通过 `import binaryninja` 使用其 API。因此，MCP 服务器**必须以 GUI 插件的形式**运行于 Binary Ninja 主进程内。

### 1.3 项目目标

- 以 Binary Ninja GUI 插件形式实现 MCP 服务器
- 采用标准 **HTTP 协议**（Streamable HTTP）作为传输层，不使用 SSE
- 完整暴露 Binary Ninja 的分析、编辑、查询等核心能力
- 与 Cursor 等 AI 客户端无缝集成
- 保证线程安全、响应性能与数据安全

---

## 二、系统架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────┐
│            AI 客户端（Cursor 等）              │
│         MCP Client over HTTP                │
└──────────────────┬──────────────────────────┘
                   │ HTTP POST (JSON-RPC 2.0)
                   ▼
┌─────────────────────────────────────────────┐
│         Binary Ninja GUI 进程               │
│  ┌──────────────────────────────────────┐   │
│  │       MCP Server Plugin              │   │
│  │  ┌────────────────────────────────┐  │   │
│  │  │  HTTP Server (FastMCP/uvicorn) │  │   │
│  │  │  监听: 127.0.0.1:9090          │  │   │
│  │  └───────────┬────────────────────┘  │   │
│  │              │ 调用 BN API            │   │
│  │  ┌───────────▼────────────────────┐  │   │
│  │  │  BackgroundTaskThread          │  │   │
│  │  │  (异步执行，不阻塞 GUI)          │  │   │
│  │  └───────────┬────────────────────┘  │   │
│  │              │ 主线程安全调用          │   │
│  │  ┌───────────▼────────────────────┐  │   │
│  │  │  Binary Ninja API Layer        │  │   │
│  │  │  (BinaryView / BNIL / Types)   │  │   │
│  │  └────────────────────────────────┘  │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 2.2 传输协议

| 属性 | 规格 |
|:---|:---|
| **协议** | HTTP/1.1 |
| **传输格式** | Streamable HTTP（MCP 2025-06-18 标准） |
| **消息格式** | JSON-RPC 2.0 |
| **监听地址** | `127.0.0.1:9090`（可在插件设置中修改） |
| **端点** | `POST /mcp` |
| **认证** | Bearer Token（HTTP Header: `Authorization: Bearer <token>`） |

> **说明：** 本项目明确采用 Streamable HTTP 协议，不使用 SSE（Server-Sent Events）。客户端通过标准 HTTP POST 请求发送 JSON-RPC 调用，服务端通过 HTTP 响应体返回结果，支持流式分块传输（chunked transfer）用于长耗时任务的进度推送。

### 2.3 线程模型

- MCP HTTP Server 运行于 `BackgroundTaskThread`，不阻塞 Binary Ninja GUI
- 所有**只读 API 调用**（分析、查询）直接在后台线程执行
- 所有**写操作 API 调用**（重命名、注释、Patch、类型定义）通过 `execute_on_main_thread_and_wait()` 调度至主线程执行
- 引入全局读写锁防止并发写冲突

---

## 三、功能需求

### 3.1 MCP 工具（Tools）规范

工具为 LLM 可调用的函数接口，具有明确的输入参数和返回值。

#### 3.1.1 二进制文件与视图管理

| 工具名 | 描述 | 参数 | 返回值 |
|:---|:---|:---|:---|
| `get_binary_info` | 获取当前加载二进制的基本信息 | 无 | 文件路径、架构、平台、加载基址、文件大小、入口点地址 |
| `list_binary_views` | 列出当前所有已打开的 BinaryView | 无 | view_id 列表及对应文件名 |
| `switch_binary_view` | 切换当前活跃的 BinaryView | `view_id: str` | 操作成功/失败 |
| `get_segments` | 获取二进制的所有段（Segments） | `view_id?: str` | 段名、起始地址、大小、权限（R/W/X）列表 |
| `get_sections` | 获取二进制的所有节（Sections） | `view_id?: str` | 节名、起始地址、大小列表 |
| `read_memory` | 读取指定地址的原始字节 | `address: int, length: int` | 十六进制字符串 |
| `write_memory` | 向指定地址写入字节（Patch） | `address: int, data: str (hex)` | 操作成功/失败 |
| `get_entry_points` | 获取所有入口点地址 | 无 | 地址列表 |

#### 3.1.2 函数分析

| 工具名 | 描述 | 参数 | 返回值 |
|:---|:---|:---|:---|
| `list_functions` | 列出二进制中所有已识别函数 | `offset?: int, limit?: int` | 函数名、起始地址、大小、是否有符号 |
| `get_function_by_address` | 根据地址获取函数信息 | `address: int` | 函数名、地址、参数列表、返回类型 |
| `get_function_by_name` | 根据名称获取函数信息 | `name: str` | 同上 |
| `decompile_function` | 反编译函数并返回 HLIL 伪代码 | `address_or_name: str` | HLIL 伪代码字符串（C 风格） |
| `get_function_llil` | 获取函数的 LLIL 中间语言 | `address_or_name: str` | LLIL 指令列表 |
| `get_function_mlil` | 获取函数的 MLIL 中间语言 | `address_or_name: str` | MLIL 指令列表 |
| `get_function_hlil` | 获取函数的 HLIL 中间语言（结构化） | `address_or_name: str` | HLIL AST JSON |
| `get_function_ssa` | 获取函数的 SSA 形式 | `address_or_name: str, il_level: str` | SSA 指令列表 |
| `get_function_assembly` | 获取函数的原始汇编指令 | `address_or_name: str` | 汇编指令列表（地址 + 助记符 + 操作数） |
| `get_function_callees` | 获取函数所调用的所有函数 | `address_or_name: str` | 被调用函数地址与名称列表 |
| `get_function_callers` | 获取调用指定函数的所有调用者 | `address_or_name: str` | 调用者函数地址与名称列表 |
| `get_function_variables` | 获取函数的所有局部变量 | `address_or_name: str` | 变量名、类型、存储位置列表 |
| `get_function_parameters` | 获取函数的参数列表 | `address_or_name: str` | 参数名、类型列表 |
| `get_function_return_type` | 获取函数的返回类型 | `address_or_name: str` | 类型字符串 |
| `get_function_tags` | 获取函数上挂载的所有 Tag | `address_or_name: str` | Tag 类型与内容列表 |
| `get_function_complexity` | 获取函数的圈复杂度（Cyclomatic Complexity） | `address_or_name: str` | 整数 |

#### 3.1.3 交叉引用（Cross References）

| 工具名 | 描述 | 参数 | 返回值 |
|:---|:---|:---|:---|
| `get_code_xrefs_to` | 获取所有引用指定地址的代码位置 | `address: int` | 引用地址列表及所在函数 |
| `get_code_xrefs_from` | 获取指定地址引用的所有目标 | `address: int` | 目标地址列表 |
| `get_data_xrefs_to` | 获取所有引用指定数据地址的位置 | `address: int` | 引用位置列表 |
| `get_data_xrefs_from` | 获取指定地址引用的数据地址 | `address: int` | 数据地址列表 |
| `get_call_graph` | 获取以指定函数为根节点的调用图（深度可限） | `address_or_name: str, depth?: int` | 调用图 JSON（节点 + 边） |

#### 3.1.4 符号与导入导出

| 工具名 | 描述 | 参数 | 返回值 |
|:---|:---|:---|:---|
| `list_symbols` | 列出所有符号 | `type?: str` (function/data/import/export) | 符号名、地址、类型列表 |
| `get_symbol_at` | 获取指定地址的符号 | `address: int` | 符号名、类型、绑定信息 |
| `list_imports` | 列出所有导入函数 | 无 | 导入函数名、地址、所属库 |
| `list_exports` | 列出所有导出函数 | 无 | 导出函数名、地址 |
| `find_symbol_by_name` | 按名称搜索符号（支持模糊匹配） | `pattern: str` | 匹配的符号列表 |

#### 3.1.5 字符串与数据

| 工具名 | 描述 | 参数 | 返回值 |
|:---|:---|:---|:---|
| `list_strings` | 列出二进制中所有已识别字符串 | `min_length?: int, encoding?: str` | 字符串内容、地址、长度、编码 |
| `search_string` | 在字符串列表中搜索关键词 | `keyword: str` | 匹配字符串及地址 |
| `get_data_at` | 获取指定地址的数据变量信息 | `address: int` | 变量名、类型、值 |
| `list_data_variables` | 列出所有已定义的数据变量 | 无 | 数据变量列表（名称、地址、类型） |
| `search_bytes` | 在二进制中搜索特定字节序列 | `pattern: str (hex or regex)` | 匹配地址列表 |

#### 3.1.6 类型系统

| 工具名 | 描述 | 参数 | 返回值 |
|:---|:---|:---|:---|
| `list_types` | 列出所有已定义的类型 | 无 | 类型名、类型定义列表 |
| `get_type` | 获取指定类型的定义 | `name: str` | 类型结构（struct/enum/typedef/union） |
| `define_struct` | 定义或更新一个结构体类型 | `name: str, fields: [{name, type, offset}]` | 操作成功/失败 |
| `define_enum` | 定义或更新一个枚举类型 | `name: str, members: [{name, value}]` | 操作成功/失败 |
| `define_typedef` | 定义类型别名 | `name: str, target_type: str` | 操作成功/失败 |
| `apply_type_to_address` | 将类型应用到指定地址 | `address: int, type_name: str` | 操作成功/失败 |
| `set_function_type` | 设置函数的完整类型签名 | `address_or_name: str, signature: str` | 操作成功/失败 |
| `import_type_from_header` | 从 C 头文件解析并导入类型 | `header_content: str` | 导入的类型列表 |

#### 3.1.7 重命名与注释（写操作）

| 工具名 | 描述 | 参数 | 返回值 |
|:---|:---|:---|:---|
| `rename_function` | 重命名函数 | `address_or_name: str, new_name: str` | 操作成功/失败 |
| `rename_variable` | 重命名函数内局部变量 | `function: str, var_name: str, new_name: str` | 操作成功/失败 |
| `batch_rename_variables` | 批量重命名变量（AI 建议的 JSON 映射） | `function: str, mapping: {old: new}` | 成功/失败条目统计 |
| `rename_data_variable` | 重命名数据变量 | `address: int, new_name: str` | 操作成功/失败 |
| `set_function_comment` | 为函数设置注释 | `address_or_name: str, comment: str` | 操作成功/失败 |
| `set_address_comment` | 为指定地址设置注释 | `address: int, comment: str` | 操作成功/失败 |
| `get_comments` | 获取指定函数或地址范围的所有注释 | `address_or_name: str` | 注释内容与地址列表 |
| `add_tag` | 为地址或函数添加 Tag 标记 | `address: int, tag_type: str, data: str` | 操作成功/失败 |

#### 3.1.8 控制流图（CFG）

| 工具名 | 描述 | 参数 | 返回值 |
|:---|:---|:---|:---|
| `get_basic_blocks` | 获取函数的所有基本块 | `address_or_name: str` | 基本块列表（起止地址、后继块） |
| `get_cfg` | 获取函数控制流图 | `address_or_name: str` | CFG JSON（节点为基本块，边为跳转关系） |
| `get_dominators` | 获取基本块的支配关系 | `address_or_name: str` | 支配树 JSON |

#### 3.1.9 二进制 Patch 与修改

| 工具名 | 描述 | 参数 | 返回值 |
|:---|:---|:---|:---|
| `patch_bytes` | 在指定地址写入原始字节 | `address: int, data: str (hex)` | 操作成功/失败 |
| `nop_range` | 将指定地址范围填充为 NOP 指令 | `start: int, end: int` | 操作成功/失败 |
| `assemble_and_patch` | 将汇编代码组装并写入指定地址 | `address: int, asm: str` | 操作成功/失败 |
| `undo_last_patch` | 撤销最后一次 Patch 操作 | 无 | 操作成功/失败 |

#### 3.1.10 分析控制

| 工具名 | 描述 | 参数 | 返回值 |
|:---|:---|:---|:---|
| `start_analysis` | 启动/重启对当前二进制的完整分析 | 无 | 操作成功/失败 |
| `wait_for_analysis` | 等待分析完成（含超时） | `timeout_ms?: int` | 完成/超时状态 |
| `get_analysis_progress` | 获取当前分析进度 | 无 | 进度百分比及当前阶段描述 |
| `define_function_at` | 在指定地址手动定义一个函数 | `address: int, name?: str` | 操作成功/失败 |
| `undefine_function` | 取消定义函数 | `address: int` | 操作成功/失败 |
| `reanalyze_function` | 重新分析指定函数 | `address_or_name: str` | 操作成功/失败 |

#### 3.1.11 高级分析与漏洞辅助

| 工具名 | 描述 | 参数 | 返回值 |
|:---|:---|:---|:---|
| `find_dangerous_functions` | 查找对危险函数（strcpy/sprintf 等）的所有调用 | `func_list?: [str]` | 调用位置及上下文列表 |
| `get_data_flow` | 追踪指定变量的数据流向（基于 MLIL SSA） | `function: str, var_name: str` | 数据流路径列表 |
| `get_taint_sources` | 获取函数中所有外部输入点 | `address_or_name: str` | 输入来源地址及类型 |
| `find_buffer_operations` | 查找函数中所有的内存拷贝/读写操作 | `address_or_name: str` | 操作地址、类型及大小 |
| `compare_functions` | 比较两个函数的 HLIL 相似度（用于 Diff 分析） | `func_a: str, func_b: str` | 相似度分数及差异摘要 |

---

### 3.2 MCP 资源（Resources）规范

资源为静态或动态的数据源，客户端可按需拉取。

| 资源 URI | 描述 | MIME 类型 |
|:---|:---|:---|
| `binja://binary/info` | 当前二进制文件元信息 | `application/json` |
| `binja://functions/list` | 全量函数列表 | `application/json` |
| `binja://symbols/table` | 符号表 | `application/json` |
| `binja://strings/all` | 全量字符串列表 | `application/json` |
| `binja://types/all` | 所有自定义类型 | `application/json` |
| `binja://function/{address_or_name}/hlil` | 指定函数 HLIL 伪代码 | `text/plain` |
| `binja://function/{address_or_name}/cfg` | 指定函数控制流图 | `application/json` |
| `binja://analysis/progress` | 当前分析进度 | `application/json` |

### 3.3 MCP 提示（Prompts）规范

预定义模板，引导 AI 完成常见逆向任务。

| 提示名 | 描述 | 参数 |
|:---|:---|:---|
| `analyze_function` | 引导 AI 对函数进行全面分析并给出功能描述 | `function_name: str` |
| `find_vulnerability` | 引导 AI 在函数中查找潜在漏洞 | `function_name: str` |
| `rename_all_variables` | 引导 AI 为函数内所有变量提供语义化命名建议 | `function_name: str` |
| `document_api` | 引导 AI 为函数生成 API 文档注释 | `function_name: str` |
| `compare_patch` | 引导 AI 分析两个函数的差异（Patch Diff） | `original: str, patched: str` |
| `identify_algorithm` | 引导 AI 识别函数实现的算法类型 | `function_name: str` |

---

## 四、非功能需求

### 4.1 性能需求

| 指标 | 要求 |
|:---|:---|
| 简单查询响应时间 | ≤ 200ms（函数列表、符号查询等） |
| 单函数反编译响应时间 | ≤ 2000ms |
| 大型函数（>1000 行 IL）反编译 | ≤ 10000ms，支持流式分块返回 |
| 并发请求数 | 支持至少 5 个并发 HTTP 请求 |
| 内存占用（缓存层） | ≤ 256MB |

#### 4.1.1 缓存策略

- **HLIL 伪代码缓存：** 以函数地址为键，缓存已生成的伪代码，缓存失效条件为函数被修改（重命名/Patch）
- **符号表缓存：** 全量缓存，失效条件为分析完成或用户手动刷新
- **CFG 缓存：** 以函数地址为键，缓存控制流图 JSON
- 缓存采用 LRU 策略，最大条目数可在插件设置中配置（默认 500 条）

### 4.2 安全需求

| 要求 | 实现方式 |
|:---|:---|
| 访问认证 | HTTP Header 携带 Bearer Token，Token 在插件首次启动时随机生成（32位十六进制） |
| 监听范围限制 | 默认仅监听 `127.0.0.1`，禁止监听 `0.0.0.0` |
| 写操作二次确认 | Patch 字节、大批量重命名（>20条）操作须通过插件 UI 弹窗确认 |
| 请求速率限制 | 同一连接每秒最多 30 次请求，超出返回 429 Too Many Requests |
| Token 管理 | 插件 UI 提供 Token 查看与重新生成功能 |

### 4.3 兼容性需求

| 需求项 | 要求 |
|:---|:---|
| Binary Ninja 版本 | Pro 版本，API v5.2 及以上 |
| Python 版本 | Binary Ninja 内置 Python 3.x |
| MCP 协议版本 | 2025-06-18（Streamable HTTP） |
| 客户端兼容 | Cursor、Claude Desktop、任何支持 MCP HTTP 传输的客户端 |
| 操作系统 | Windows / macOS / Linux |

### 4.4 可靠性需求

- 服务器崩溃时自动重启（最多 3 次），超过后通知用户
- 所有写操作在执行前记录操作日志，支持 Binary Ninja 原生 Undo（`bv.begin_undo_actions` / `bv.commit_undo_actions`）
- HTTP 服务端异常返回标准 JSON-RPC 错误对象，不暴露内部堆栈信息

---

## 五、插件 UI 需求

### 5.1 插件菜单项

在 Binary Ninja 菜单栏的 `Plugins` 菜单下添加：

- `MCP Server → Start`：启动 HTTP 服务器
- `MCP Server → Stop`：停止 HTTP 服务器
- `MCP Server → Status`：查看服务器状态（端口、Token、连接数）
- `MCP Server → Settings`：打开设置面板

### 5.2 设置面板

| 配置项 | 类型 | 默认值 |
|:---|:---|:---|
| 监听端口 | 整数 | `9090` |
| Bearer Token | 字符串（只读 + 重新生成按钮） | 随机生成 |
| 写操作确认 | 开关 | 开启 |
| HLIL 缓存大小 | 整数 | `500` |
| 日志级别 | 下拉（DEBUG/INFO/WARNING） | INFO |
| 开机自启 | 开关 | 关闭 |

### 5.3 状态栏指示器

在 Binary Ninja 状态栏显示 MCP 服务器运行状态（绿点=运行中，红点=已停止）。

---

## 六、HTTP API 规范

### 6.1 端点定义

```
POST http://127.0.0.1:9090/mcp
Content-Type: application/json
Authorization: Bearer <token>
```

### 6.2 请求格式（JSON-RPC 2.0）

```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "method": "tools/call",
  "params": {
    "name": "decompile_function",
    "arguments": {
      "address_or_name": "main"
    }
  }
}
```

### 6.3 响应格式

**成功响应：**

```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "int main(int argc, char** argv) {\n  ...\n}"
      }
    ]
  }
}
```

**错误响应：**

```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "error": {
    "code": -32602,
    "message": "Function not found: 'foo'",
    "data": null
  }
}
```

### 6.4 标准错误码

| 错误码 | 含义 |
|:---|:---|
| `-32700` | 解析错误（无效 JSON） |
| `-32600` | 无效请求 |
| `-32601` | 方法不存在 |
| `-32602` | 参数无效（如函数名不存在） |
| `-32000` | 服务器内部错误 |
| `-32001` | Binary Ninja API 调用失败 |
| `-32002` | 操作被用户取消 |

### 6.5 Cursor 客户端配置示例

在 Cursor 的 `mcp.json` 配置文件中添加：

```json
{
  "mcpServers": {
    "binary-ninja-pro": {
      "url": "http://127.0.0.1:9090/mcp",
      "headers": {
        "Authorization": "Bearer <your-token>"
      }
    }
  }
}
```

---

## 七、开发实现路线图

### 阶段一：核心框架搭建（Week 1-2）

- [ ] 创建 Binary Ninja 插件工程结构
- [ ] 实现 `BackgroundTaskThread` 中的 HTTP 服务器（基于 FastMCP / uvicorn）
- [ ] 实现 Bearer Token 认证中间件
- [ ] 实现 `get_binary_info`、`list_functions`、`decompile_function` 三个核心工具
- [ ] 实现插件菜单（Start / Stop / Status）
- [ ] 完成与 Cursor 的基础连通性验证

### 阶段二：完整工具集实现（Week 3-4）

- [ ] 实现全部查询类工具（3.1.1 ~ 3.1.5）
- [ ] 实现交叉引用与调用图工具（3.1.3）
- [ ] 实现类型系统工具（3.1.6）
- [ ] 实现 CFG 工具（3.1.8）
- [ ] 实现 HLIL / LLIL / MLIL / SSA 多层 IL 工具
- [ ] 实现缓存层

### 阶段三：写操作与高级功能（Week 5-6）

- [ ] 实现重命名与注释类工具（主线程安全调用）
- [ ] 实现 Patch 与分析控制工具（含 Undo 支持）
- [ ] 实现类型定义工具
- [ ] 实现高级分析辅助工具（3.1.11）
- [ ] 实现写操作二次确认 UI
- [ ] 实现 MCP 资源（Resources）接口

### 阶段四：稳定性与用户体验（Week 7）

- [ ] 完善插件设置面板
- [ ] 实现状态栏指示器
- [ ] 实现 MCP Prompts 接口
- [ ] 性能压测与优化
- [ ] 编写用户文档

---

## 八、依赖与技术栈

| 依赖 | 版本要求 | 用途 |
|:---|:---|:---|
| Binary Ninja Python API | v5.2+ | 核心分析能力 |
| `fastmcp` | latest | MCP 协议封装 |
| `uvicorn` | latest | ASGI HTTP 服务器 |
| `starlette` | latest | HTTP 路由与中间件 |
| `pydantic` | v2+ | 请求参数验证 |

安装方式（在 Binary Ninja 内置 Python 环境中执行）：

```bash
pip install fastmcp uvicorn starlette pydantic
```

---

## 九、已知限制与风险

| 风险项 | 说明 | 缓解措施 |
|:---|:---|:---|
| GIL 竞争 | Python GIL 限制多线程并发 API 调用性能 | 使用 asyncio 事件循环 + 队列化请求 |
| 主线程死锁 | 写操作回调中不当使用 `execute_on_main_thread_and_wait` 可能死锁 | 严格区分读写路径，避免嵌套等待 |
| 大型二进制性能 | 超大二进制的全量函数列表可能超时 | 实现分页参数，默认返回前 1000 条 |
| Binary Ninja 版本升级 | API 变更可能导致插件失效 | 引入版本检查，最低支持 v5.2 |
| 本地网络安全 | localhost 端口可能被本机其他进程访问 | 强制 Bearer Token 认证，不可禁用 |

---

*文档结束*
