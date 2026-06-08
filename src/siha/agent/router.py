"""Intent Router — lightweight classifier that decides how to handle user input.

Uses a small local model (or rule-based fallback) to classify intent before
invoking the full agent loop. This lets small models work reliably by
separating "decision" from "execution".
"""

import json
import re
from typing import Optional
from siha.llm.factory import create_llm_client
from siha.config import settings


class IntentRouter:
    """Classifies user input into execution strategies."""

    INTENTS = ["chat", "tool_call", "code_generation", "analysis"]

    def __init__(self):
        # Use the smallest available local model for routing.
        # If local provider isn't configured, fall back to the main provider.
        try:
            self.client = create_llm_client(
                model=settings.local_model_file,
                provider="local",
            )
        except Exception:
            # Fallback: use whatever provider is configured
            self.client = create_llm_client()

    def classify(self, user_prompt: str) -> str:
        """Classify user intent. Returns one of INTENTS."""
        prompt = (
            "You are an intent classifier. Given a user message, classify it into exactly one category.\n"
            "Categories:\n"
            "- chat: greeting, chitchat, simple question that doesn't require action\n"
            "- tool_call: request to DO something (create file, run code, search web, read file, etc.)\n"
            "- code_generation: write code, build a website, create a script\n"
            "- analysis: analyze code, review file, debug error\n\n"
            "Respond with ONLY the category name, nothing else.\n\n"
            f"User message: {user_prompt}\n"
            "Intent:"
        )

        try:
            response = self.client.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=20,
            )
            text = response.choices[0].message.content.strip().lower()
            # Extract just the category word
            for intent in self.INTENTS:
                if intent in text:
                    return intent
            return "chat"  # safest fallback
        except Exception:
            # If router fails, use rule-based fallback
            return self._rule_based_classify(user_prompt)

    @staticmethod
    def _rule_based_classify(user_prompt: str) -> str:
        """Simple keyword-based fallback when the router model fails."""
        prompt_lower = user_prompt.lower()

        # Tool-action keywords
        tool_keywords = [
            "create", "make", "build", "write", "generate", "run", "execute",
            "search", "find", "look up", "read", "open", "list", "delete",
            "move", "copy", "rename", "install", "fix", "debug", "test",
        ]
        if any(kw in prompt_lower for kw in tool_keywords):
            return "tool_call"

        # Code generation keywords
        code_keywords = [
            "html", "css", "javascript", "python", "script", "website",
            "page", "component", "function", "class", "app",
        ]
        if any(kw in prompt_lower for kw in code_keywords):
            return "code_generation"

        # Analysis keywords
        analysis_keywords = [
            "analyze", "review", "explain", "what does", "how does",
            "debug", "trace", "error", "bug", "why is",
        ]
        if any(kw in prompt_lower for kw in analysis_keywords):
            return "analysis"

        return "chat"
