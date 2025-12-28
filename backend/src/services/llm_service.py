"""LLM provider wrapper (Module G)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import HTTPException, status

from src.core.config import Settings, get_settings

try:
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover
    tiktoken = None

try:
    from anthropic import AsyncAnthropic  # type: ignore
except Exception:  # pragma: no cover
    AsyncAnthropic = None


@dataclass(frozen=True)
class LlmCompletion:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int


class LlmService:
    """Service wrapper for LLM calls and token counting."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def llm_available(self) -> bool:
        if not self.settings.llm_enabled:
            return False
        if self.settings.llm_provider != "anthropic":
            return False
        if not self.settings.anthropic_api_key:
            return False
        if AsyncAnthropic is None:
            return False
        return True

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if tiktoken is None:
            return len(text.split())

        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        if tiktoken is None:
            words = text.split()
            if len(words) <= max_tokens:
                return text
            return " ".join(words[:max_tokens])

        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return encoding.decode(tokens[:max_tokens])

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int = 1024,
    ) -> LlmCompletion:
        if not self.llm_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM is unavailable",
            )
        if self.settings.llm_provider != "anthropic":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unsupported LLM provider",
            )

        assert AsyncAnthropic is not None
        client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

        started = time.perf_counter()
        try:
            message = await client.messages.create(
                model=self.settings.llm_model,
                max_tokens=max_output_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM provider error",
            ) from exc

        duration_ms = int((time.perf_counter() - started) * 1000)

        text_parts: list[str] = []
        for block in getattr(message, "content", []) or []:
            block_text = getattr(block, "text", None)
            if block_text:
                text_parts.append(block_text)
        text = "\n".join(text_parts).strip()

        input_tokens = self.count_tokens(system_prompt + "\n" + user_prompt)
        output_tokens = self.count_tokens(text)

        return LlmCompletion(
            text=text,
            model=self.settings.llm_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
        )
