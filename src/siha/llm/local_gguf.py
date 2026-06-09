"""In-process GGUF provider using llama-cpp-python."""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_chunk import Choice as ChunkChoice
from openai.types.chat.chat_completion_chunk import ChoiceDelta
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from siha.config import settings
from siha.llm.client import LLMProvider


class _FakeCompletion:
    """Minimal iterator wrapper to satisfy the OpenAI chunk type."""

    def __init__(self, chunks: List[ChatCompletionChunk]):
        self._chunks = chunks
        self._idx = 0

    def __iter__(self):
        return iter(self._chunks)

    def __next__(self):
        if self._idx >= len(self._chunks):
            raise StopIteration
        chunk = self._chunks[self._idx]
        self._idx += 1
        return chunk


class LocalGGUFClient(LLMProvider):
    """Loads a tiny GGUF model directly into memory for fully offline inference."""

    def __init__(self, model: Optional[str] = None):
        # The 'model' arg is ignored for local; we always use the configured GGUF
        super().__init__(model=model or settings.local_model_file)
        self._llm = None
        self._model_path: Optional[Path] = None

    @property
    def llm(self):
        """Lazy-load the llama-cpp model."""
        if self._llm is None:
            self._ensure_model()
            from llama_cpp import Llama

            n_threads = settings.local_model_n_threads or None
            self._llm = Llama(
                model_path=str(self._model_path),
                n_ctx=settings.local_model_context_size,
                verbose=False,
                n_threads=n_threads,
            )
        return self._llm

    def _ensure_model(self) -> None:
        """Download the GGUF if it's not already cached."""
        cache_dir = Path(settings.local_model_cache_dir).expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
        target = cache_dir / settings.local_model_file

        if target.exists():
            self._model_path = target
            return

        # Auto-download via huggingface_hub
        try:
            from huggingface_hub import hf_hub_download
        except ImportError as e:
            raise RuntimeError(
                "huggingface_hub is required for the local provider. "
                'Install with: pip install -e ".[local]"'
            ) from e

        downloaded = hf_hub_download(
            repo_id=settings.local_model_repo,
            filename=settings.local_model_file,
            local_dir=str(cache_dir),
            local_dir_use_symlinks=False,
        )
        self._model_path = Path(downloaded)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> ChatCompletion:
        if stream:
            # Accumulate from the generator and return a single completion
            chunks = list(
                self.stream(messages, tools=tools, temperature=temperature, max_tokens=max_tokens)
            )
            content_parts = []
            for c in chunks:
                if c.choices and c.choices[0].delta and c.choices[0].delta.content:
                    content_parts.append(c.choices[0].delta.content)
            full = "".join(content_parts)
            return ChatCompletion(
                id="local-gguf-0",
                object="chat.completion",
                created=0,
                model=self.model,
                choices=[
                    Choice(
                        index=0,
                        message=ChatCompletionMessage(role="assistant", content=full),
                        finish_reason="stop",
                    )
                ],
            )

        prompt = self._build_prompt(messages, tools)
        output = self.llm(
            prompt,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=max_tokens or 512,
            stop=["<|im_end|>", "<|endoftext|>", "</s>"],
        )
        text = output["choices"][0]["text"]
        tool_calls = self._try_parse_tool_calls(text) if tools else []
        return ChatCompletion(
            id="local-gguf-0",
            object="chat.completion",
            created=0,
            model=self.model,
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=text if not tool_calls else "",
                        tool_calls=tool_calls if tool_calls else None,
                    ),
                    finish_reason="stop",
                )
            ],
        )

    def chat_constrained(
        self,
        messages: List[Dict[str, Any]],
        grammar: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> ChatCompletion:
        """Chat completion with GBNF grammar-constrained decoding.

        The decoder can only sample tokens that keep the output inside the
        grammar, so the response is guaranteed to be syntactically valid
        (e.g. a well-formed tool-call JSON object).
        """
        from llama_cpp import LlamaGrammar

        prompt = self._build_prompt(messages, tools=None)
        grammar_obj = LlamaGrammar.from_string(grammar, verbose=False)
        output = self.llm(
            prompt,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=max_tokens or 512,
            grammar=grammar_obj,
        )
        text = output["choices"][0]["text"]
        return ChatCompletion(
            id="local-gguf-constrained-0",
            object="chat.completion",
            created=0,
            model=self.model,
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content=text),
                    finish_reason="stop",
                )
            ],
        )

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Iterator[ChatCompletionChunk]:
        prompt = self._build_prompt(messages, tools)
        output = self.llm(
            prompt,
            temperature=temperature if temperature is not None else self.temperature,
            max_tokens=max_tokens or 512,
            stop=["<|im_end|>", "<|endoftext|>", "</s>"],
            stream=True,
        )
        for token in output:
            text = token["choices"][0]["text"]
            yield ChatCompletionChunk(
                id="local-gguf-0",
                object="chat.completion.chunk",
                created=0,
                model=self.model,
                choices=[
                    ChunkChoice(
                        index=0,
                        delta=ChoiceDelta(content=text),
                        finish_reason=None,
                    )
                ],
            )
        # Emit finish chunk
        yield ChatCompletionChunk(
            id="local-gguf-0",
            object="chat.completion.chunk",
            created=0,
            model=self.model,
            choices=[
                ChunkChoice(
                    index=0,
                    delta=ChoiceDelta(),
                    finish_reason="stop",
                )
            ],
        )

    def _build_prompt(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]]) -> str:
        """Build a simple chat prompt. For Qwen2.5-Instruct models."""
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                parts.append(f"<|im_start|>system\n{content}<|im_end|>")
            elif role == "assistant":
                parts.append(f"<|im_start|>assistant\n{content}<|im_end|>")
            elif role == "tool":
                parts.append(f"<|im_start|>user\n[Tool result]\n{content}<|im_end|>")
            else:
                parts.append(f"<|im_start|>user\n{content}<|im_end|>")
        if tools:
            tool_desc = self._render_tools_as_text(tools)
            parts.append(f"<|im_start|>user\n{tool_desc}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)

    def _render_tools_as_text(self, tools: List[Dict[str, Any]]) -> str:
        """Inject tool descriptions into the prompt for models that don't support native tool calling."""
        lines = ["You have access to the following tools. Reply with a JSON object like {"]
        for t in tools:
            name = t.get("function", {}).get("name", "")
            desc = t.get("function", {}).get("description", "")
            lines.append(f'- name: "{name}" — {desc}')
        lines.append("If you need a tool, output ONLY a JSON object: {\"tool\": \"<name>\", \"arguments\": {...}}")
        return "\n".join(lines)

    def _try_parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Best-effort parse of JSON tool calls from model output."""
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return []
            data = json.loads(match.group())
            if "tool" in data:
                return [
                    {
                        "id": "call_local_0",
                        "type": "function",
                        "function": {
                            "name": data["tool"],
                            "arguments": json.dumps(data.get("arguments", {})),
                        },
                    }
                ]
        except Exception:
            pass
        return []


def is_llama_cpp_available() -> bool:
    """Check if llama-cpp-python is installed."""
    try:
        import llama_cpp  # noqa: F401
        return True
    except ImportError:
        return False
