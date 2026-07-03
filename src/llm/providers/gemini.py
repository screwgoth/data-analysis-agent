from google import genai
from google.genai import types


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-pro"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        text, _ = self.generate(prompt, system=system)
        return text

    def generate(
        self, prompt: str, *, system: str | None = None, model: str | None = None
    ) -> tuple[str, dict]:
        """Return (text, token_usage) where usage = {prompt, completion, total}.

        ``model`` overrides the configured model for this call (e.g. the light
        ``gemini-2.5-flash`` used by the Phase-2 suggest node).
        """
        config = types.GenerateContentConfig(
            system_instruction=system,
        ) if system else None
        response = self._client.models.generate_content(
            model=model or self._model,
            contents=prompt,
            config=config,
        )
        usage = {"prompt": 0, "completion": 0, "total": 0}
        meta = getattr(response, "usage_metadata", None)
        if meta is not None:
            usage = {
                "prompt": getattr(meta, "prompt_token_count", 0) or 0,
                "completion": getattr(meta, "candidates_token_count", 0) or 0,
                "total": getattr(meta, "total_token_count", 0) or 0,
            }
        return response.text or "", usage
