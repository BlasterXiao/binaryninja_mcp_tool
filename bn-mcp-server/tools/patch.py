from __future__ import annotations

from typing import Optional

from .helpers import run_on_main

from .. import config as cfgmod
from .. import state


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def patch_bytes(address: int, data: str) -> str:
        """Write raw bytes (hex string) at address."""

        def confirm() -> bool:
            cfg = cfgmod.load_config()
            if not cfg.get("require_write_confirm", True):
                return True
            from ..ui import confirm_dialog

            return confirm_dialog.confirm_write(
                f"Patch {len(data.replace(' ', '')) // 2} bytes at 0x{address:x}?"
            )

        if not confirm():
            return "cancelled"

        def _do():
            bv = get_bv()
            raw = bytes.fromhex(data.replace(" ", ""))
            bv.begin_undo_actions()
            try:
                bv.write(address, raw)
                bv.commit_undo_actions()
            except Exception:
                bv.undo_undo_actions()
                raise
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def nop_range(start: int, end: int) -> str:
        """Fill NOP slide in range (architecture-specific NOP)."""

        def _do():
            bv = get_bv()
            nop = b"\x90"
            if hasattr(bv.arch, "assemble"):
                try:
                    asm = bv.arch.assemble("nop", start)
                    if isinstance(asm, (bytes, bytearray)):
                        nop = bytes(asm[:1])
                    elif isinstance(asm, (list, tuple)) and asm:
                        nop = bytes(asm[0][:1]) if asm[0] else nop
                except Exception:
                    nop = b"\x90"
            bv.begin_undo_actions()
            try:
                addr = start
                while addr < end:
                    bv.write(addr, nop[:1])
                    addr += len(nop[:1])
                bv.commit_undo_actions()
            except Exception:
                bv.undo_undo_actions()
                raise
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def assemble_and_patch(address: int, asm: str) -> str:
        """Assemble one instruction and patch."""

        def _do():
            bv = get_bv()
            if not hasattr(bv.arch, "assemble"):
                return "assemble not available"
            insns = bv.arch.assemble(asm, address)
            if not insns:
                return "assemble failed"
            data = insns[0] if isinstance(insns, (list, tuple)) else insns
            if isinstance(data, int):
                return "assemble returned unexpected int"
            if not isinstance(data, (bytes, bytearray)):
                data = bytes(data)
            bv.begin_undo_actions()
            try:
                bv.write(address, data)
                bv.commit_undo_actions()
            except Exception:
                bv.undo_undo_actions()
                raise
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def undo_last_patch() -> str:
        """Undo last BinaryView undo action."""

        def _do():
            bv = get_bv()
            if hasattr(bv, "undo"):
                bv.undo()
                state.invalidate_after_write(bv)
                return "ok"
            return "undo not available"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"
