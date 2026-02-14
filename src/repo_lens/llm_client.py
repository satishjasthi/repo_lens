from __future__ import annotations

from __future__ import annotations

import re
from typing import Any, Self

import litellm
from litellm import completion

from .config import Settings


def _messages(context: str, question: str, system_prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Repository context:\n{context}\n\nQuestion:{question}",
        },
    ]


def _extract_content(content: str) -> str:
    if not content:
        return ""
    # Strip thinking tags that some models (like Nemotron/DeepSeek) include
    if "</think>" in content:
        content = content.split("</think>", 1)[-1].strip()
    
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    return content


class LiteLLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Configure LiteLLM defaults if needed, though arguments to completion are preferred
        litellm.suppress_instrumentation = True  # Optional: reduce log noise

    def close(self) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def chat_messages(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
    ) -> str:
        # Map generic settings to LiteLLM arguments
        # If llm_provider is "openai" (default), we might simply use the model name.
        # If it's something else, we might need to prefix the model or use specific args.
        # However, specifically for generic OpenAI-compatible endpoints (like LM Studio),
        # usage is usually provider="openai", api_base="...", model="...".
        
        # We construct the model string. If provider is standard (openai, anthropic), 
        # LiteLLM often expects just "gpt-4" or "claude-3".
        # But for custom providers/local setups, explicit params are best.
        
        response = completion(
            model=self.settings.llm_model,
            messages=messages,
            api_base=self.settings.llm_api_base,
            api_key=self.settings.llm_api_key,
            custom_llm_provider=self.settings.llm_provider,
            temperature=temperature,
            timeout=self.settings.request_timeout,
        )
        
        # LiteLLM object access
        content = response.choices[0].message.content or ""  # type: ignore
        return _extract_content(content)

    def chat(self, *, context: str, question: str) -> str:
        return self.chat_messages(
            _messages(context, question, self.settings.system_prompt)
        )


def create_llm_client(settings: Settings) -> LiteLLMClient:
    return LiteLLMClient(settings)
