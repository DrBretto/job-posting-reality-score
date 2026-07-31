"""Thin, self-contained Bedrock wrapper (pattern reused from job-searcher's bedrock_client).

Kept dependency-light and free of any project-config import so it drops into a Lambda zip. Dry-run
by default so nothing bills unless explicitly enabled. InvokeModel-only (no agents/tools).
"""

from __future__ import annotations

import json
import logging
import os
import time

logger = logging.getLogger(__name__)


class BedrockError(RuntimeError):
    """Base class for Bedrock runtime errors."""


class BedrockClient:
    def __init__(
        self,
        *,
        dry_run: bool | None = None,
        region: str | None = None,
        cheap_model: str | None = None,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
    ):
        self.dry_run = dry_run if dry_run is not None else _env_bool("JPRS_LLM_DRY_RUN", True)
        self.region = region or os.environ.get("JPRS_LLM_REGION", "us-east-1")
        self.cheap_model = cheap_model or os.environ.get(
            "JPRS_LLM_CHEAP_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"
        )
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._client = None
        if not self.dry_run:
            import boto3  # imported lazily so the dry-run path needs no AWS deps

            self._client = boto3.client("bedrock-runtime", region_name=self.region)

    def run_small(self, prompt: str, *, stub: str = "", max_tokens: int = 512) -> str:
        """Invoke the cheap model. In dry-run returns the provided stub (no network, no cost)."""
        if self.dry_run:
            return stub
        return self._invoke(self.cheap_model, prompt, max_tokens)

    def _invoke(self, model_id: str, prompt: str, max_tokens: int) -> str:  # pragma: no cover - network
        from botocore.exceptions import ClientError

        for attempt in range(1, self.retry_attempts + 1):
            try:
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                })
                resp = self._client.invoke_model(
                    modelId=model_id, contentType="application/json",
                    accept="application/json", body=body,
                )
                result = json.loads(resp["body"].read())
                return result["content"][0]["text"]
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code == "ThrottlingException" and attempt < self.retry_attempts:
                    time.sleep(self.retry_delay * attempt)
                    continue
                raise BedrockError(f"bedrock invoke failed ({code}): {e}") from e
        return ""


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")
