"""
agents/base_agent.py
---------------------
Shared machinery for every Scoutly agent:
  - injects memory context into the prompt
  - forces strict JSON-only output
  - parses + validates the response against a pydantic schema
  - retries once on malformed JSON (LLMs occasionally wrap JSON in prose
    or code fences despite instructions — handle it rather than crash)
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from llm_client import LLMClient
from memory import ScoutlyMemory


class AgentError(RuntimeError):
    """Raised when an agent cannot produce valid structured output after retries."""


class BaseAgent:
    """
    Not used directly — each agent in agents/intake_agent.py,
    research_agent.py, and recommendation_agent.py subclasses this and only
    overrides the three class attributes below. Everything about how an
    agent actually talks to the model lives here, once, instead of being
    copy-pasted into every agent file.
    """

    role_name: str = "BaseAgent"
    system_prompt: str = ""
    output_schema: type[BaseModel] | None = None

    def __init__(self, client: LLMClient):
        self.client = client

    def build_user_message(self, memory: ScoutlyMemory, turn_input: dict) -> str:
        """
        Assembles the one message sent to the model for this turn: the
        customer's memory so far, then whatever new input this specific
        agent needs (see each agent's *_input dict in orchestrator.py).
        """
        return (
            "MEMORY CONTEXT (JSON):\n"
            f"{memory.as_context_string()}\n\n"
            "NEW INPUT FOR THIS TURN (JSON):\n"
            f"{json.dumps(turn_input, indent=2)}\n\n"
            "Return ONLY the JSON object specified in your instructions. "
            "No prose, no markdown fences, no commentary."
        )

    @staticmethod
    def _extract_json(raw: str) -> dict:
        """
        Pulls the JSON object out of the model's raw text response. Models
        are told to return JSON and nothing else, but sometimes add a
        ```json code fence or a stray sentence anyway — this handles both
        cases before falling back to json.loads on the whole string.
        """
        text = raw.strip()
        # Strip ```json ... ``` fences if the model added them anyway.
        fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1)
        else:
            brace_match = re.search(r"\{.*\}", text, re.DOTALL)
            if brace_match:
                text = brace_match.group(0)
        return json.loads(text)

    def run(self, memory: ScoutlyMemory, turn_input: dict) -> dict:
        """
        The main entry point every agent uses: build the prompt, call the
        model, and try to parse + validate its response against
        output_schema. If that fails (bad JSON, or JSON that doesn't match
        the required fields), it tells the model what went wrong and tries
        once more before giving up and raising AgentError. Two attempts
        total, not unlimited retries, so a persistently broken model call
        fails fast instead of hanging.
        """
        user_message = self.build_user_message(memory, turn_input)

        last_error: Exception | None = None
        for _attempt in range(2):
            raw = self.client.generate(self.system_prompt, user_message)
            try:
                parsed = self._extract_json(raw)
                if self.output_schema is not None:
                    validated = self.output_schema(**parsed)
                    return validated.model_dump()
                return parsed
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                user_message += (
                    "\n\nYour previous response was not valid JSON matching the "
                    "required schema. Return ONLY a single valid JSON object, "
                    "with no other text."
                )
        raise AgentError(f"{self.role_name} failed to produce valid JSON after retries: {last_error}")
