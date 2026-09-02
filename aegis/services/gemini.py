"""
Gemini integration service for AI reasoning over compiled incident evidence.
"""

import asyncio
import logging
from typing import Dict, Any

from google import genai
from google.genai import errors as genai_errors
from pydantic import BaseModel

from aegis.config import settings

logger = logging.getLogger(__name__)

# HTTP status codes from Gemini that are safe to retry.
_RETRYABLE_CODES = {503, 429}
_MAX_RETRIES = 3
_RETRY_DELAYS = [2.0, 4.0]  # seconds before attempt 2, then attempt 3


class GeminiRCAResult(BaseModel):
    suspected_root_cause: str
    evidence_summary: str
    recommended_mitigation: str
    confidence_score: float


class GeminiReasoningService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured")

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL

    async def analyze_evidence(
        self, evidence_packet: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze the compiled incident evidence using Gemini and return a
        structured RCA result.  Retries up to _MAX_RETRIES times on transient
        503 (UNAVAILABLE) or 429 (RESOURCE_EXHAUSTED) errors.
        """

        prompt = f"""
You are an expert production incident response and root-cause-analysis engineer.

Analyze ONLY the incident evidence supplied below.

IMPORTANT RULES:
1. Do not invent facts, deployments, metrics, logs, services, versions,
   configuration values, or remediation steps.
2. Treat the supplied evidence as authoritative.
3. If evidence conflicts, explicitly mention the conflict instead of guessing.
4. The suspected root cause must be directly supported by the evidence.
5. The mitigation must be based on evidence and must not introduce
   unsupported configuration values.
6. Return a confidence score between 0.0 and 1.0.
7. Keep the response concise and operationally useful.

Incident evidence:
{evidence_packet}
"""

        last_error: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": GeminiRCAResult,
                        "temperature": 0.1,
                    },
                )

                if response.parsed is not None:
                    return response.parsed.model_dump()

                # Fallback if the SDK does not populate response.parsed.
                if not response.text:
                    raise ValueError("Gemini returned an empty response")

                result = GeminiRCAResult.model_validate_json(response.text)
                return result.model_dump()

            except genai_errors.ServerError as exc:
                if exc.code in _RETRYABLE_CODES and attempt < _MAX_RETRIES:
                    delay = _RETRY_DELAYS[attempt - 1]
                    logger.warning(
                        "Gemini returned %s (attempt %d/%d); retrying in %.0fs...",
                        exc.code,
                        attempt,
                        _MAX_RETRIES,
                        delay,
                    )
                    last_error = exc
                    await asyncio.sleep(delay)
                else:
                    # Non-retryable server error, or retries exhausted.
                    logger.error(
                        "Gemini ServerError %s on attempt %d/%d — giving up.",
                        exc.code,
                        attempt,
                        _MAX_RETRIES,
                    )
                    raise

        # Should only reach here if all retries were consumed.
        raise last_error  # type: ignore[misc]
