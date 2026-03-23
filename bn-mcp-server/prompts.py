"""MCP Prompt templates."""


def register(mcp, get_bv) -> None:
    _ = get_bv
    p = getattr(mcp, "prompt", None)
    if p is None:
        return
    try:

        @p()
        def analyze_function(function_name: str) -> str:
            return (
                f"对 Binary Ninja 中的函数 `{function_name}` 进行全面逆向分析："
                "描述其目的、关键逻辑、输入输出与潜在安全问题。"
            )

        @p()
        def find_vulnerability(function_name: str) -> str:
            return (
                f"在函数 `{function_name}` 的 HLIL/MLIL 层面查找潜在漏洞模式"
                "（缓冲区溢出、格式化字符串、UAF 等），并给出证据地址。"
            )

        @p()
        def rename_all_variables(function_name: str) -> str:
            return (
                f"读取函数 `{function_name}` 的变量列表，为每个局部变量提出语义化重命名建议，"
                "并说明理由。"
            )

        @p()
        def document_api(function_name: str) -> str:
            return f"为函数 `{function_name}` 生成简洁的 API 文档注释（参数、返回值、副作用）。"

        @p()
        def compare_patch(original: str, patched: str) -> str:
            return (
                f"比较两个函数 `{original}` 与 `{patched}` 的 HLIL 差异，"
                "解释补丁可能修复或引入的行为变化。"
            )

        @p()
        def identify_algorithm(function_name: str) -> str:
            return (
                f"根据函数 `{function_name}` 的反编译代码，推断其实现的算法或协议（如哈希、加密、压缩）。"
            )

    except Exception:
        pass
