"""Compat shim: ragas 0.4.x × langchain-community 0.4.x.

Every released ragas (0.3.x–0.4.x) hard-imports
`langchain_community.chat_models.vertexai` / `langchain_community.llms.VertexAI`
in `ragas/llms/base.py`, but langchain-community 0.4.x removed those modules
(VertexAI moved to the `langchain-google-vertexai` partner package). Our
production stack pins community 0.4.2, so downgrading community for an eval
dependency is not acceptable.

This shim injects minimal stand-in classes under the affected module paths
BEFORE `import ragas`. Each stub is injected only when its specific
submodule is missing, so an existing `langchain_community.llms.VertexAI`
lazy import is never shadowed. Ragas uses them only for `isinstance` checks
when classifying LLM backends; our judge path (Bedrock via langchain-aws)
never touches them. REMOVE this file when a ragas release drops the VertexAI
imports or realigns with community 0.4.x — the `test_ragas_import` test in
`tests/eval/` will tell you (it imports ragas both with and without the
shim path asserted).
"""

from __future__ import annotations

import sys
import types


def _ensure_vertexai_stubs() -> None:
    def _submodule_missing(name: str) -> bool:
        try:
            __import__(name)
        except ImportError:
            return True
        return False

    if _submodule_missing("langchain_community.chat_models.vertexai"):
        import langchain_community.chat_models as chat_models_pkg

        chat_mod = types.ModuleType("langchain_community.chat_models.vertexai")

        class ChatVertexAI:  # noqa: D101
            def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
                raise RuntimeError(
                    "ChatVertexAI stub (occlusion eval shim) — not a real backend"
                )

        chat_mod.ChatVertexAI = ChatVertexAI
        sys.modules["langchain_community.chat_models.vertexai"] = chat_mod
        setattr(chat_models_pkg, "vertexai", chat_mod)

    if _submodule_missing("langchain_community.llms.vertexai"):
        import langchain_community.llms as llms_pkg

        llms_mod = types.ModuleType("langchain_community.llms.vertexai")

        class VertexAI:  # noqa: D101
            def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
                raise RuntimeError(
                    "VertexAI stub (occlusion eval shim) — not a real backend"
                )

        llms_mod.VertexAI = VertexAI
        # ragas does `from langchain_community.llms import VertexAI`
        setattr(llms_pkg, "VertexAI", VertexAI)
        sys.modules["langchain_community.llms.vertexai"] = llms_mod


_ensure_vertexai_stubs()
