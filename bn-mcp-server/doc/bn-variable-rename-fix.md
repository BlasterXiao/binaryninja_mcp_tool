# Binary Ninja Variable Rename Fix

## Problem
`fn.create_user_var(v, v.type, new_name)` only works for variables with `index=0`.
Non-zero-index SSA variants (compiler-generated temporaries) silently fail to rename.

## Solution (Method D)
Iterate ALL `fn.vars` at the same `storage` offset and call `create_user_var` on EACH one with the SAME base name:
```python
for v in fn.vars:
    if v.storage == target.storage and v.source_type == target.source_type:
        fn.create_user_var(v, v.type, new_name)
fn.request_advanced_analysis_data()
```
Then call `reanalyze_function` to force HLIL regeneration.

## Key Files
- Source: `C:\Users\32669\Documents\AI\bn_plugin\bn-mcp-server\tools\edit.py`
- Deploy: `C:\Users\32669\AppData\Roaming\Binary Ninja\plugins\bn-mcp-server\tools\edit.py`
- Must restart BN after code changes (no hot reload)
