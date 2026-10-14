"""Chat model factory, including a deterministic dry-run fake."""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class DryRunChatModel(BaseChatModel):
    """Deterministic stand-in so CI and local runs need no API key."""

    model_name: str = Field(default="dry-run")

    @property
    def _llm_type(self) -> str:
        return "dry-run"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        text = self._reply("\n".join(str(m.content) for m in messages))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def _reply(self, prompt: str) -> str:
        lower = prompt.lower()
        if "write concise learner-facing feedback" in lower or "feedback writer" in lower:
            return (
                "## Feedback\n"
                "Your submission covers the core word-counting behavior. "
                "Review edge cases and keep the public API clear before panel review."
            )
        if "verify" in lower and "evidence" in lower:
            return self._verify_payload(prompt)
        if "assess the following criteria" in lower or "specialist" in lower:
            return self._specialist_payload(prompt)
        return json.dumps({"findings": []})

    def _specialist_payload(self, prompt: str) -> str:
        findings = []
        for line in prompt.splitlines():
            if line.strip().startswith("- id:"):
                criterion_id = line.split("id:", 1)[1].strip()
                level = "met" if "structure" in prompt.lower() or "clear_structure" in criterion_id else "partial"
                if "handles_edge" in criterion_id:
                    level = "partial"
                findings.append(
                    {
                        "id": criterion_id,
                        "level": level,
                        "evidence": f"Dry-run evidence for {criterion_id}.",
                    }
                )
        return json.dumps({"findings": findings})

    def _verify_payload(self, prompt: str) -> str:
        try:
            start = prompt.index("{")
            end = prompt.rindex("}") + 1
            payload = json.loads(prompt[start:end])
        except (ValueError, json.JSONDecodeError):
            return json.dumps({"findings": []})
        verified = []
        for row in payload.get("findings") or []:
            verified.append(
                {
                    "id": row.get("id"),
                    "level": row.get("level") or "missing",
                    "evidence": row.get("evidence") or "No evidence.",
                }
            )
        return json.dumps({"findings": verified})


def get_chat_model(*, dry_run: bool = False) -> BaseChatModel:
    if dry_run or os.environ.get("EVAL_DRY_RUN", "").lower() in {"1", "true", "yes"}:
        return DryRunChatModel()
    from langchain.chat_models import init_chat_model

    model_name = os.environ.get("EVAL_MODEL", "gpt-4o-mini")
    return init_chat_model(model_name, model_provider="openai")
