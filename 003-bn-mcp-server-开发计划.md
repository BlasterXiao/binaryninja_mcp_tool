# Binary Ninja MCP Server 开发计划

**文档版本：** v1.0  
**日期：** 2026-03-23  
**参考文档：** `002-bn-mcp-server-需求文档.md`  
**开发周期：** 7 周（4 个阶段）

---

## 一、总体开发时间线

```mermaid
gantt
    title Binary Ninja MCP Server 开发甘特图
    dateFormat  YYYY-MM-DD
    section 阶段一：核心框架
        插件工程初始化          :a1, 2026-03-23, 2d
        HTTP服务器实现           :a2, after a1, 3d
        Bearer Token 认证        :a3, after a2, 2d
        3个核心工具实现          :a4, after a2, 3d
        插件菜单UI               :a5, after a3, 2d
        Cursor连通性验证         :a6, after a4, 2d

    section 阶段二：完整工具集
        查询类工具(3.1.1~3.1.5) :b1, 2026-04-06, 5d
        交叉引用与调用图         :b2, after b1, 3d
        类型系统工具             :b3, after b1, 3d
        CFG工具                  :b4, after b2, 2d
        多层IL工具               :b5, after b2, 3d
        缓存层实现               :b6, after b3, 2d

    section 阶段三：写操作与高级功能
        重命名注释工具           :c1, 2026-04-20, 3d
        Patch与分析控制          :c2, after c1, 3d
        类型定义工具             :c3, after c1, 2d
        高级分析辅助工具         :c4, after c2, 3d
        写操作确认UI             :c5, after c3, 2d
        Resources接口            :c6, after c4, 2d

    section 阶段四：稳定性与体验
        插件设置面板             :d1, 2026-05-04, 2d
        状态栏指示器             :d2, after d1, 1d
        MCP Prompts接口          :d3, after d1, 2d
        性能压测与优化           :d4, after d2, 3d
        用户文档编写             :d5, after d4, 2d
```

---

## 二、整体系统架构图

```mermaid
graph TB
    subgraph Client["AI 客户端层"]
        Cursor["Cursor IDE<br/>MCP Client"]
        Claude["Claude Desktop<br/>MCP Client"]
        Other["其他 MCP 客户端"]
    end

    subgraph Transport["传输层 · HTTP/1.1 · JSON-RPC 2.0"]
        HTTP["POST http://127.0.0.1:9090/mcp<br/>Authorization: Bearer TOKEN"]
    end

    subgraph Plugin["Binary Ninja GUI 进程 · MCP Server Plugin"]
        subgraph HTTPLayer["HTTP 服务层"]
            Uvicorn["uvicorn ASGI 服务器"]
            FastMCP["FastMCP 框架<br/>JSON-RPC 路由"]
            Auth["Bearer Token<br/>认证中间件"]
            RateLimit["速率限制<br/>30 req/s"]
        end

        subgraph ThreadLayer["线程调度层"]
            BGThread["BackgroundTaskThread<br/>后台线程（不阻塞GUI）"]
            MainThread["execute_on_main_thread_and_wait()<br/>主线程调度（写操作专用）"]
            RWLock["全局读写锁<br/>防并发写冲突"]
        end

        subgraph CacheLayer["缓存层 · LRU · 最大500条"]
            HLILCache["HLIL 伪代码缓存<br/>key: func_address"]
            SymCache["符号表缓存<br/>全量缓存"]
            CFGCache["CFG 控制流图缓存<br/>key: func_address"]
        end

        subgraph ToolLayer["工具层 · 63个 MCP Tools"]
            T1["二进制视图管理<br/>8个工具"]
            T2["函数分析<br/>16个工具"]
            T3["交叉引用<br/>5个工具"]
            T4["符号与导入导出<br/>5个工具"]
            T5["字符串与数据<br/>5个工具"]
            T6["类型系统<br/>8个工具"]
            T7["重命名与注释<br/>8个工具"]
            T8["控制流图CFG<br/>3个工具"]
            T9["Patch与修改<br/>4个工具"]
            T10["分析控制<br/>6个工具"]
            T11["高级漏洞分析<br/>5个工具"]
        end

        subgraph BNAPILayer["Binary Ninja API 层"]
            BV["BinaryView<br/>二进制视图对象"]
            BNIL["BNIL 中间语言<br/>LLIL / MLIL / HLIL / SSA"]
            TypeSys["类型系统<br/>Struct / Enum / Typedef"]
            SymTable["符号表<br/>Imports / Exports"]
        end
    end

    Cursor --> HTTP
    Claude --> HTTP
    Other --> HTTP
    HTTP --> Uvicorn
    Uvicorn --> Auth
    Auth --> RateLimit
    RateLimit --> FastMCP
    FastMCP --> BGThread
    BGThread --> RWLock
    RWLock --> CacheLayer
    RWLock --> ToolLayer
    BGThread --> MainThread
    MainThread --> T7
    MainThread --> T9
    ToolLayer --> BNAPILayer
```

---

## 三、模块依赖关系图

```mermaid
graph LR
    subgraph Core["核心模块"]
        plugin_main["plugin_main.py<br/>插件入口 & 菜单注册"]
        server["server.py<br/>HTTP服务器启动/停止"]
        bg_task["bg_task.py<br/>BackgroundTaskThread"]
    end

    subgraph Middleware["中间件模块"]
        auth["middleware/auth.py<br/>Bearer Token 认证"]
        ratelimit["middleware/ratelimit.py<br/>速率限制"]
        logger["middleware/logger.py<br/>请求日志"]
    end

    subgraph Tools["工具模块"]
        tools_binary["tools/binary_view.py<br/>视图管理 8个工具"]
        tools_func["tools/functions.py<br/>函数分析 16个工具"]
        tools_xref["tools/xrefs.py<br/>交叉引用 5个工具"]
        tools_sym["tools/symbols.py<br/>符号 5个工具"]
        tools_str["tools/strings.py<br/>字符串 5个工具"]
        tools_types["tools/types.py<br/>类型系统 8个工具"]
        tools_edit["tools/edit.py<br/>重命名注释 8个工具"]
        tools_cfg["tools/cfg.py<br/>控制流图 3个工具"]
        tools_patch["tools/patch.py<br/>Patch修改 4个工具"]
        tools_analysis["tools/analysis.py<br/>分析控制 6个工具"]
        tools_adv["tools/advanced.py<br/>高级分析 5个工具"]
    end

    subgraph Resources["资源模块"]
        resources["resources.py<br/>MCP Resources 8个URI"]
        prompts["prompts.py<br/>MCP Prompts 6个模板"]
    end

    subgraph Cache["缓存模块"]
        cache["cache/lru_cache.py<br/>LRU缓存 最大500条"]
        cache_hlil["cache/hlil_cache.py"]
        cache_sym["cache/symbol_cache.py"]
        cache_cfg["cache/cfg_cache.py"]
    end

    subgraph UI["UI模块"]
        ui_menu["ui/menu.py<br/>Plugins菜单项"]
        ui_settings["ui/settings.py<br/>设置面板"]
        ui_statusbar["ui/statusbar.py<br/>状态栏指示器"]
        ui_confirm["ui/confirm_dialog.py<br/>写操作确认弹窗"]
    end

    subgraph Config["配置模块"]
        config["config.py<br/>端口/Token/缓存大小"]
    end

    plugin_main --> server
    plugin_main --> ui_menu
    plugin_main --> ui_statusbar
    server --> bg_task
    server --> auth
    server --> ratelimit
    server --> logger
    bg_task --> Tools
    bg_task --> Resources
    bg_task --> prompts
    Tools --> cache
    cache --> cache_hlil
    cache --> cache_sym
    cache --> cache_cfg
    tools_edit --> ui_confirm
    tools_patch --> ui_confirm
    ui_menu --> ui_settings
    config --> server
    config --> cache
    config --> auth
```

---

## 四、阶段一详细开发流程

### 4.1 阶段一总览

```mermaid
flowchart TD
    Start([🚀 开始阶段一]) --> S1

    S1["📁 初始化插件工程结构
    ├── __init__.py
    ├── plugin_main.py
    ├── server.py
    ├── bg_task.py
    ├── config.py
    └── requirements.txt"]

    S1 --> S2["⚙️ 实现 BackgroundTaskThread
    继承 BN 后台任务基类
    在后台线程启动 uvicorn"]

    S2 --> S3["🌐 启动 FastMCP HTTP 服务
    绑定 127.0.0.1:9090
    注册 POST /mcp 端点"]

    S3 --> S4["🔐 实现 Bearer Token 中间件
    首次启动随机生成 32位 Token
    存储于 config.py"]

    S4 --> S5["🔧 实现3个核心工具"]
    S5 --> S5a["get_binary_info
    → bv.file.filename
    → bv.arch, bv.platform
    → bv.start, bv.length"]
    S5 --> S5b["list_functions
    → bv.functions
    → 分页: offset + limit"]
    S5 --> S5c["decompile_function
    → bv.get_functions_by_name()
    → func.hlil → str()"]

    S5a --> S6["🖥️ 实现插件菜单"]
    S5b --> S6
    S5c --> S6

    S6["📋 注册 Plugins 菜单项
    ├── MCP Server → Start
    ├── MCP Server → Stop
    └── MCP Server → Status"]

    S6 --> S7["✅ Cursor 连通性验证
    配置 mcp.json
    发送 tools/list 请求
    验证3个工具可调用"]

    S7 --> End1([✔️ 阶段一完成])
```

### 4.2 工程目录结构

```
bn-mcp-server/
├── __init__.py                  # BN 插件入口，注册菜单
├── plugin_main.py               # 插件生命周期管理
├── server.py                    # HTTP 服务器核心
├── bg_task.py                   # BackgroundTaskThread 封装
├── config.py                    # 全局配置（端口/Token/缓存）
├── requirements.txt             # Python 依赖
├── middleware/
│   ├── auth.py                  # Bearer Token 认证
│   ├── ratelimit.py             # 速率限制（30 req/s）
│   └── logger.py                # 请求日志
├── tools/
│   ├── binary_view.py           # 视图管理（8个工具）
│   ├── functions.py             # 函数分析（16个工具）
│   ├── xrefs.py                 # 交叉引用（5个工具）
│   ├── symbols.py               # 符号（5个工具）
│   ├── strings.py               # 字符串（5个工具）
│   ├── types.py                 # 类型系统（8个工具）
│   ├── edit.py                  # 重命名注释（8个工具）
│   ├── cfg.py                   # 控制流图（3个工具）
│   ├── patch.py                 # Patch修改（4个工具）
│   ├── analysis.py              # 分析控制（6个工具）
│   └── advanced.py              # 高级漏洞分析（5个工具）
├── cache/
│   ├── lru_cache.py             # LRU 缓存基类
│   ├── hlil_cache.py            # HLIL 伪代码缓存
│   ├── symbol_cache.py          # 符号表缓存
│   └── cfg_cache.py             # CFG 缓存
├── resources.py                 # MCP Resources（8个URI）
├── prompts.py                   # MCP Prompts（6个模板）
└── ui/
    ├── menu.py                  # Plugins菜单
    ├── settings.py              # 设置面板
    ├── statusbar.py             # 状态栏指示器
    └── confirm_dialog.py        # 写操作确认弹窗
```

---

## 五、阶段二详细开发流程

### 5.1 工具集实现顺序

```mermaid
flowchart LR
    Start([🚀 开始阶段二]) --> G1

    subgraph G1["第1优先级·只读查询工具"]
        direction TB
        T11["tools/binary_view.py
        get_segments
        get_sections
        read_memory
        get_entry_points
        list_binary_views
        switch_binary_view"]

        T12["tools/functions.py
        get_function_by_address
        get_function_by_name
        get_function_assembly
        get_function_variables
        get_function_parameters
        get_function_return_type
        get_function_tags
        get_function_complexity
        get_function_callees
        get_function_callers"]

        T13["tools/symbols.py
        list_symbols
        get_symbol_at
        list_imports
        list_exports
        find_symbol_by_name"]

        T14["tools/strings.py
        list_strings
        search_string
        get_data_at
        list_data_variables
        search_bytes"]
    end

    G1 --> G2

    subgraph G2["第2优先级·IL多层分析"]
        direction TB
        IL1["tools/functions.py (续)
        get_function_llil
        get_function_mlil
        get_function_hlil
        get_function_ssa"]

        IL2["tools/xrefs.py
        get_code_xrefs_to
        get_code_xrefs_from
        get_data_xrefs_to
        get_data_xrefs_from
        get_call_graph"]

        IL3["tools/cfg.py
        get_basic_blocks
        get_cfg
        get_dominators"]
    end

    G2 --> G3

    subgraph G3["第3优先级·类型系统 & 缓存"]
        direction TB
        TP1["tools/types.py
        list_types
        get_type"]

        CA["cache/lru_cache.py
        cache/hlil_cache.py
        cache/symbol_cache.py
        cache/cfg_cache.py"]
    end

    G3 --> End2([✔️ 阶段二完成])
```

### 5.2 BNIL 多层中间语言获取流程

```mermaid
flowchart TD
    Req["AI 请求: get_function_hlil('main')"] --> Lookup

    Lookup{"缓存命中？"} -->|"✅ 命中"| ReturnCache["直接返回缓存数据"]
    Lookup -->|"❌ 未命中"| FindFunc

    FindFunc["bv.get_functions_by_name('main')
    或 bv.get_function_at(address)"] --> CheckFunc

    CheckFunc{"函数存在？"} -->|"❌ 不存在"| ErrNotFound["返回错误 -32602
    Function not found"]
    CheckFunc -->|"✅ 存在"| ChooseIL

    ChooseIL{"IL 层级选择"} -->|"llil"| LLIL["func.llil
    低级中间语言
    接近汇编"]
    ChooseIL -->|"mlil"| MLIL["func.mlil
    中级中间语言
    含变量抽象"]
    ChooseIL -->|"hlil（默认）"| HLIL["func.hlil
    高级中间语言
    C风格伪代码"]
    ChooseIL -->|"ssa"| SSA["func.mlil.ssa_form
    或 func.hlil.ssa_form
    静态单赋值"]

    LLIL --> Serialize["序列化为 JSON / 纯文本"]
    MLIL --> Serialize
    HLIL --> Serialize
    SSA --> Serialize

    Serialize --> StoreCache["写入 LRU 缓存"]
    StoreCache --> Response["返回 JSON-RPC 响应"]
    ReturnCache --> Response
```

---

## 六、阶段三详细开发流程

### 6.1 写操作安全调度流程

```mermaid
sequenceDiagram
    participant AI as AI 客户端 (Cursor)
    participant HTTP as HTTP Server
    participant Auth as 认证中间件
    participant BG as BackgroundTaskThread
    participant UI as 确认弹窗 (主线程)
    participant Main as 主线程调度器
    participant BN as Binary Ninja API

    AI->>HTTP: POST /mcp {"method":"tools/call","name":"rename_function"}
    HTTP->>Auth: 验证 Bearer Token
    Auth-->>HTTP: ✅ Token 合法
    HTTP->>BG: 转发请求至后台线程

    BG->>BG: 参数校验 (address_or_name, new_name)

    alt 批量操作 > 20 条
        BG->>Main: execute_on_main_thread_and_wait(show_confirm_dialog)
        Main->>UI: 弹出确认对话框 "是否重命名 X 个变量？"
        UI-->>Main: 用户点击 "确认"
        Main-->>BG: 返回 True
    end

    BG->>Main: execute_on_main_thread_and_wait(do_rename)
    Main->>BN: bv.begin_undo_actions()
    Main->>BN: func.name = new_name
    Main->>BN: bv.commit_undo_actions()
    BN-->>Main: 操作完成
    Main-->>BG: 返回成功
    BG->>BG: 使缓存失效 (invalidate cache)
    BG-->>HTTP: 返回成功响应
    HTTP-->>AI: {"result": {"content": [{"type":"text","text":"ok"}]}}
```

### 6.2 Patch 操作完整流程

```mermaid
flowchart TD
    PReq["AI 请求: patch_bytes
    address=0x401000
    data='90 90 90'"] --> PAuth

    PAuth["Bearer Token 验证"] --> PVal

    PVal["参数验证
    ① address 在合法范围内？
    ② data 是合法 hex 字符串？
    ③ 长度不超过段边界？"] --> PConfirm

    PConfirm{"需要用户确认？
    (默认开启)"}

    PConfirm -->|"是"| PDialog["主线程弹出确认框
    '是否在 0x401000 写入 90 90 90？'"]
    PDialog -->|"用户取消"| PCancel["返回错误 -32002
    操作被用户取消"]
    PDialog -->|"用户确认"| PLog

    PConfirm -->|"否(设置已关闭)"| PLog

    PLog["记录操作日志
    {ts, address, old_bytes, new_bytes}"]
    PLog --> PUndo["bv.begin_undo_actions()"]
    PUndo --> PWrite["主线程执行:
    bv.write(address, bytes.fromhex(data))"]
    PWrite --> PCommit["bv.commit_undo_actions()"]
    PCommit --> PInvalidate["使相关缓存失效
    (HLIL/CFG of affected functions)"]
    PInvalidate --> PReanalyze["bv.reanalyze() 触发重新分析"]
    PReanalyze --> PResp["返回成功响应"]
```

### 6.3 MCP Resources 数据流

```mermaid
flowchart LR
    Client["AI 客户端"] -->|"resources/read
    binja://function/main/hlil"| Router

    Router{"资源路由"} -->|"binary/info"| R1["get_binary_info()
    → JSON"]
    Router -->|"functions/list"| R2["list_functions()
    → JSON 分页"]
    Router -->|"symbols/table"| R3["全量符号表
    → JSON"]
    Router -->|"strings/all"| R4["全量字符串列表
    → JSON"]
    Router -->|"types/all"| R5["所有自定义类型
    → JSON"]
    Router -->|"function/{x}/hlil"| R6["decompile_function(x)
    → text/plain"]
    Router -->|"function/{x}/cfg"| R7["get_cfg(x)
    → JSON"]
    Router -->|"analysis/progress"| R8["get_analysis_progress()
    → JSON 实时"]

    R1 --> Resp["HTTP 响应"]
    R2 --> Resp
    R3 --> Resp
    R4 --> Resp
    R5 --> Resp
    R6 --> Resp
    R7 --> Resp
    R8 --> Resp
```

---

## 七、阶段四详细开发流程

### 7.1 插件 UI 完整结构

```mermaid
graph TD
    BN_Menu["Binary Ninja 菜单栏"] --> Plugins

    Plugins["Plugins 菜单"] --> MCP["MCP Server"]

    MCP --> Start["▶ Start
    调用 server.start()
    状态栏变绿"]
    MCP --> Stop["⏹ Stop
    调用 server.stop()
    状态栏变红"]
    MCP --> Status["ℹ Status
    显示: 端口/Token/连接数/运行时间"]
    MCP --> Settings["⚙ Settings
    打开设置面板"]

    Settings --> SettingsPanel["设置面板"]

    SettingsPanel --> P1["监听端口
    默认: 9090"]
    SettingsPanel --> P2["Bearer Token
    只读显示 + [重新生成] 按钮"]
    SettingsPanel --> P3["写操作确认
    开关: 默认开启"]
    SettingsPanel --> P4["HLIL缓存大小
    默认: 500 条"]
    SettingsPanel --> P5["日志级别
    DEBUG / INFO / WARNING"]
    SettingsPanel --> P6["开机自启
    开关: 默认关闭"]

    StatusBar["状态栏指示器"]
    StatusBar --> Green["🟢 MCP Server: Running :9090"]
    StatusBar --> Red["🔴 MCP Server: Stopped"]
```

### 7.2 性能优化策略

```mermaid
graph TB
    subgraph Problems["性能瓶颈"]
        P1["大型函数反编译耗时 > 2s"]
        P2["全量函数列表数据量大"]
        P3["GIL 限制并发 API 调用"]
        P4["重复调用相同函数"]
    end

    subgraph Solutions["优化方案"]
        S1["LRU 缓存
        HLIL / CFG / 符号表
        命中率目标 > 80%"]
        S2["分页参数
        offset + limit
        默认每页 100 条"]
        S3["asyncio 事件循环
        队列化请求
        避免 GIL 争抢"]
        S4["缓存失效策略
        写操作后精确失效
        不做全量清除"]
    end

    P1 --> S1
    P2 --> S2
    P3 --> S3
    P4 --> S1
    S1 --> S4
```

---

## 八、核心数据流转图

### 8.1 完整 HTTP 请求处理链路

```mermaid
sequenceDiagram
    participant C as Cursor (MCP Client)
    participant U as uvicorn (ASGI)
    participant A as auth.py
    participant R as ratelimit.py
    participant F as FastMCP Router
    participant BG as BackgroundTaskThread
    participant Cache as LRU Cache
    participant BN as Binary Ninja API

    C->>U: POST /mcp<br/>Authorization: Bearer TOKEN<br/>Body: JSON-RPC 2.0

    U->>A: 请求转发
    A->>A: 验证 Bearer Token
    alt Token 无效
        A-->>C: HTTP 401 Unauthorized
    end

    A->>R: Token 合法
    R->>R: 检查速率 ≤ 30 req/s
    alt 超出速率
        R-->>C: HTTP 429 Too Many Requests
    end

    R->>F: 速率合法
    F->>F: 解析 JSON-RPC<br/>路由到对应工具函数

    F->>BG: 在后台线程执行工具

    BG->>Cache: 查询缓存
    alt 缓存命中
        Cache-->>BG: 返回缓存数据
    else 缓存未命中
        BG->>BN: 调用 Binary Ninja API
        BN-->>BG: 返回分析结果
        BG->>Cache: 写入缓存
    end

    BG-->>F: 返回工具执行结果
    F-->>U: 构造 JSON-RPC 响应
    U-->>C: HTTP 200<br/>Body: JSON-RPC 2.0 Result
```

### 8.2 缓存失效机制

```mermaid
stateDiagram-v2
    [*] --> Empty: 初始化

    Empty --> Valid: 首次调用工具<br/>写入缓存

    Valid --> Valid: 只读工具调用<br/>命中缓存直接返回

    Valid --> Invalidated: 触发写操作
    note right of Invalidated
        触发条件:
        - rename_function / rename_variable
        - patch_bytes / nop_range / assemble_and_patch
        - define_struct / set_function_type
        - reanalyze_function
    end note

    Invalidated --> Valid: 下次只读调用<br/>重新生成缓存

    Valid --> Empty: 用户手动清除缓存
    Valid --> Empty: 切换 BinaryView
    Valid --> Empty: Binary Ninja 关闭
```

---

## 九、工具分类与实现优先级矩阵

```mermaid
quadrantChart
    title 工具实现优先级矩阵（价值 vs 实现难度）
    x-axis 实现难度低 --> 实现难度高
    y-axis 使用价值低 --> 使用价值高
    quadrant-1 优先实现
    quadrant-2 核心价值
    quadrant-3 延后实现
    quadrant-4 按需实现

    list_functions: [0.15, 0.95]
    decompile_function: [0.25, 0.98]
    get_binary_info: [0.10, 0.75]
    list_strings: [0.20, 0.80]
    get_code_xrefs_to: [0.30, 0.85]
    rename_variable: [0.40, 0.90]
    batch_rename_variables: [0.50, 0.92]
    set_function_comment: [0.35, 0.78]
    get_function_hlil: [0.30, 0.95]
    get_function_llil: [0.28, 0.70]
    get_cfg: [0.45, 0.72]
    define_struct: [0.55, 0.75]
    get_data_flow: [0.75, 0.85]
    compare_functions: [0.80, 0.65]
    find_buffer_operations: [0.70, 0.80]
    patch_bytes: [0.60, 0.70]
    assemble_and_patch: [0.85, 0.65]
    get_dominators: [0.65, 0.45]
    import_type_from_header: [0.80, 0.55]
```

---

## 十、各阶段交付物与验收标准

### 10.1 阶段一验收标准

```mermaid
flowchart LR
    subgraph 验收项
        V1["✅ 插件可在 BN Pro 中安装并启动"]
        V2["✅ HTTP 服务器在 127.0.0.1:9090 监听"]
        V3["✅ Bearer Token 认证生效"]
        V4["✅ Cursor mcp.json 配置后可连接"]
        V5["✅ tools/list 返回3个工具定义"]
        V6["✅ decompile_function('main') 返回伪代码"]
        V7["✅ 关闭插件时服务器正常停止"]
        V8["✅ GUI 无卡顿（后台线程隔离验证）"]
    end
```

### 10.2 阶段二验收标准

```mermaid
flowchart LR
    subgraph 验收项
        V1["✅ 全部 63 个工具在 tools/list 中可见"]
        V2["✅ list_functions 支持 offset/limit 分页"]
        V3["✅ 4 层 IL 工具均返回正确结构"]
        V4["✅ get_call_graph 返回有效 JSON 图结构"]
        V5["✅ LRU 缓存命中率 > 50%（重复调用测试）"]
        V6["✅ 响应时间: 简单查询 ≤ 200ms"]
    end
```

### 10.3 阶段三验收标准

```mermaid
flowchart LR
    subgraph 验收项
        V1["✅ rename_function 在主线程安全执行"]
        V2["✅ batch_rename_variables > 20 条时弹出确认框"]
        V3["✅ patch_bytes 后 BN GUI 正确更新显示"]
        V4["✅ Undo 操作可回滚 patch_bytes 的修改"]
        V5["✅ define_struct 在类型列表中可查询"]
        V6["✅ resources/read 8 个 URI 全部可访问"]
        V7["✅ 写操作后相关缓存自动失效"]
    end
```

### 10.4 阶段四验收标准

```mermaid
flowchart LR
    subgraph 验收项
        V1["✅ 设置面板所有配置项可持久化保存"]
        V2["✅ 状态栏绿点/红点随服务启停正确切换"]
        V3["✅ 6 个 Prompts 模板可在 AI 客户端中调用"]
        V4["✅ 并发 5 个请求无超时无崩溃"]
        V5["✅ 服务器崩溃后自动重启（模拟测试）"]
        V6["✅ 用户文档包含安装、配置、使用三部分"]
    end
```

---

## 十一、风险应对计划

```mermaid
flowchart TD
    subgraph Risks["识别到的风险"]
        R1["🔴 主线程死锁
        严重性: 高
        概率: 中"]
        R2["🟡 GIL 性能瓶颈
        严重性: 中
        概率: 高"]
        R3["🟡 大型二进制超时
        严重性: 中
        概率: 中"]
        R4["🟢 BN API 版本变更
        严重性: 低
        概率: 低"]
    end

    subgraph Mitigations["应对措施"]
        M1["严格区分只读/写路径
        只读: 直接在后台线程
        写操作: execute_on_main_thread_and_wait
        禁止嵌套 wait 调用"]
        M2["asyncio 事件循环 + 请求队列
        限制并发 BN API 调用数 ≤ 3
        非阻塞轮询替代阻塞等待"]
        M3["分页参数强制限制
        函数列表默认 limit=100
        反编译超时 10s 后返回部分结果"]
        M4["版本兼容检查
        插件启动时验证 BN API 版本 ≥ 5.2
        不满足时弹出警告并禁用插件"]
    end

    R1 --> M1
    R2 --> M2
    R3 --> M3
    R4 --> M4
```

---

## 十二、技术依赖安装与环境准备

```mermaid
flowchart TD
    Start([开始环境准备]) --> Step1

    Step1["确认 Binary Ninja Pro 版本
    Plugins → Python Console
    import binaryninja; print(binaryninja.__version__)
    ✅ 要求 ≥ 5.2"]

    Step1 --> Step2["定位 BN 内置 Python 路径
    Windows: %APPDATA%/Binary Ninja/python/
    macOS: ~/Library/Application Support/Binary Ninja/python/
    Linux: ~/.binaryninja/python/"]

    Step2 --> Step3["安装依赖库
    pip install fastmcp uvicorn starlette pydantic
    （使用 BN 内置 pip）"]

    Step3 --> Step4["复制插件到 BN 插件目录
    Windows: %APPDATA%/Binary Ninja/plugins/
    macOS: ~/Library/Application Support/Binary Ninja/plugins/
    Linux: ~/.binaryninja/plugins/"]

    Step4 --> Step5["重启 Binary Ninja
    Plugins 菜单中出现 'MCP Server' 子菜单"]

    Step5 --> Step6["首次启动 MCP Server
    自动生成 Bearer Token
    查看 Status 确认监听地址"]

    Step6 --> Step7["配置 Cursor mcp.json
    url: http://127.0.0.1:9090/mcp
    headers.Authorization: Bearer <token>"]

    Step7 --> End([✅ 环境就绪])
```

---

## 十三、开发里程碑汇总

| 里程碑 | 目标日期 | 核心交付物 | 验收关键指标 |
|:---|:---|:---|:---|
| **M1** 框架 MVP | Week 2 末 | HTTP 服务器 + 认证 + 3个核心工具 | Cursor 可成功调用 decompile_function |
| **M2** 完整工具集 | Week 4 末 | 全部 63 个只读工具 + 缓存层 | tools/list 返回 63 个工具，查询响应 ≤ 200ms |
| **M3** 写操作就绪 | Week 6 末 | 写操作工具 + Patch + 类型系统 + Resources | rename + patch 可正常执行并支持 Undo |
| **M4** 正式发布 | Week 7 末 | 完整 UI + Prompts + 文档 + 稳定性优化 | 全部验收标准通过，文档完整 |

---

*文档结束*
