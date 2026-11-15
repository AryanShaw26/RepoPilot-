import json
import re
from typing import Any, Dict, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)


def extract_json_block(text: str) -> str:
    # Try finding markdown code block ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text.strip()


class LLMService:
    def __init__(self):
        self.settings = settings

    async def _call_provider(self, system: str, user: str) -> str:
        provider = self.settings.LLM_PROVIDER.lower()
        api_key = self.settings.LLM_API_KEY

        if not api_key:
            raise AppError(
                code="LLM_UNAVAILABLE",
                message="AI service is currently unconfigured (no LLM_API_KEY).",
                status_code=503,
            )

        if provider == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": self.settings.LLM_MODEL or "claude-3-5-sonnet-20241022",
                "max_tokens": self.settings.LLM_MAX_OUTPUT_TOKENS,
                "temperature": self.settings.LLM_TEMPERATURE,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise AppError(
                        code="LLM_UNAVAILABLE",
                        message=f"LLM API request failed with status {resp.status_code}.",
                        status_code=502,
                    )
                data = resp.json()
                content = data.get("content", [])
                if content and "text" in content[0]:
                    return content[0]["text"]
                return ""

        elif provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.settings.LLM_MODEL or "gpt-4o",
                "max_tokens": self.settings.LLM_MAX_OUTPUT_TOKENS,
                "temperature": self.settings.LLM_TEMPERATURE,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
            }
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise AppError(
                        code="LLM_UNAVAILABLE",
                        message=f"LLM API request failed with status {resp.status_code}.",
                        status_code=502,
                    )
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""

        else:
            raise AppError(
                code="LLM_UNAVAILABLE",
                message=f"Unsupported LLM provider: {provider}",
                status_code=503,
            )

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_model: Type[T],
    ) -> T:
        """
        Calls LLM and parses JSON against schema_model.
        Attempts one repair retry on JSONDecodeError.
        """
        raw_text = await self._call_provider(system_prompt, user_prompt)
        json_str = extract_json_block(raw_text)

        try:
            parsed_data = json.loads(json_str)
            return schema_model.model_validate(parsed_data)
        except Exception as first_err:
            logger.warning("LLM returned invalid structured output; retrying with a repair prompt.")

            # Repair prompt
            repair_user = (
                f"Your previous response was not valid JSON:\n\n{json_str}\n\n"
                f"Error: {str(first_err)}\n"
                f"Please fix and output ONLY valid JSON complying with the requested schema."
            )
            raw_retry = await self._call_provider(system_prompt, repair_user)
            retry_json_str = extract_json_block(raw_retry)
            try:
                parsed_data = json.loads(retry_json_str)
                return schema_model.model_validate(parsed_data)
            except Exception:
                logger.error("LLM structured output remained invalid after repair.")
                raise AppError(
                    code="LLM_UNAVAILABLE",
                    message="Failed to parse LLM structured response.",
                    status_code=502,
                )
