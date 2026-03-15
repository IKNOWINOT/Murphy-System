"""
OpenAI Integration — Murphy System World Model Connector.

Uses OpenAI API v1.
Required credentials: OPENAI_API_KEY
Setup: https://platform.openai.com/api-keys
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class OpenAIConnector(BaseIntegrationConnector):
    """OpenAI API connector."""

    INTEGRATION_NAME = "OpenAI"
    BASE_URL = "https://api.openai.com/v1"
    CREDENTIAL_KEYS = ["OPENAI_API_KEY", "OPENAI_ORG_ID", "OPENAI_BASE_URL"]
    REQUIRED_CREDENTIALS = ["OPENAI_API_KEY"]
    FREE_TIER = False
    SETUP_URL = "https://platform.openai.com/api-keys"
    DOCUMENTATION_URL = "https://platform.openai.com/docs/api-reference"

    def __init__(self, credentials: Optional[Dict[str, str]] = None, **kwargs) -> None:
        super().__init__(credentials, **kwargs)
        # Allow custom base URL (e.g. for Azure OpenAI or LiteLLM proxy)
        custom_base = self._credentials.get("OPENAI_BASE_URL", "")
        if custom_base:
            self.BASE_URL = custom_base.rstrip("/")

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Authorization": f"Bearer {self._credentials.get('OPENAI_API_KEY', '')}",
            "Content-Type": "application/json",
        }
        org = self._credentials.get("OPENAI_ORG_ID", "")
        if org:
            headers["OpenAI-Organization"] = org
        return headers

    # -- Models --

    def list_models(self) -> Dict[str, Any]:
        return self._get("/models")

    def get_model(self, model_id: str) -> Dict[str, Any]:
        return self._get(f"/models/{model_id}")

    # -- Chat Completions --

    def chat_completion(self, messages: List[Dict[str, str]], model: str = "gpt-4o",
                        max_tokens: Optional[int] = None, temperature: float = 0.7,
                        stream: bool = False, **kwargs) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)
        return self._post("/chat/completions", json=payload)

    def complete(self, prompt: str, model: str = "gpt-3.5-turbo-instruct",
                 max_tokens: int = 256) -> Dict[str, Any]:
        return self._post("/completions", json={
            "model": model, "prompt": prompt, "max_tokens": max_tokens})

    # -- Embeddings --

    def create_embedding(self, input_text: str,
                         model: str = "text-embedding-3-small") -> Dict[str, Any]:
        return self._post("/embeddings", json={"model": model, "input": input_text})

    def batch_embeddings(self, texts: List[str],
                         model: str = "text-embedding-3-small") -> Dict[str, Any]:
        return self._post("/embeddings", json={"model": model, "input": texts})

    # -- Images --

    def generate_image(self, prompt: str, model: str = "dall-e-3",
                       size: str = "1024x1024", quality: str = "standard",
                       n: int = 1) -> Dict[str, Any]:
        return self._post("/images/generations", json={
            "model": model, "prompt": prompt, "size": size, "quality": quality, "n": n})

    def edit_image(self, prompt: str, image_url: str, mask_url: Optional[str] = None,
                   n: int = 1, size: str = "1024x1024") -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "prompt": prompt, "image": image_url, "n": n, "size": size}
        if mask_url:
            payload["mask"] = mask_url
        return self._post("/images/edits", json=payload)

    # -- Audio --

    def transcribe(self, audio_url: str, model: str = "whisper-1",
                   language: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"model": model, "file": audio_url}
        if language:
            payload["language"] = language
        return self._post("/audio/transcriptions", json=payload)

    def text_to_speech(self, text: str, model: str = "tts-1",
                       voice: str = "alloy") -> Dict[str, Any]:
        return self._post("/audio/speech", json={"model": model, "input": text, "voice": voice})

    # -- Moderation --

    def moderate(self, input_text: str) -> Dict[str, Any]:
        return self._post("/moderations", json={"input": input_text})

    # -- Fine-tuning --

    def list_fine_tuning_jobs(self) -> Dict[str, Any]:
        return self._get("/fine_tuning/jobs")

    def create_fine_tuning_job(self, training_file: str, model: str = "gpt-3.5-turbo") -> Dict[str, Any]:
        return self._post("/fine_tuning/jobs", json={
            "training_file": training_file, "model": model})

    # -- Assistants (v2) --

    def list_assistants(self) -> Dict[str, Any]:
        return self._get("/assistants", headers={"OpenAI-Beta": "assistants=v2"})

    def create_assistant(self, name: str, instructions: str,
                         model: str = "gpt-4o", tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        return self._post("/assistants", json={
            "name": name, "instructions": instructions,
            "model": model, "tools": tools or []},
            headers={"OpenAI-Beta": "assistants=v2"})

    # -- Health --

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return self.not_configured_response("health_check")
        result = self.list_models()
        result["integration"] = self.INTEGRATION_NAME
        return result
