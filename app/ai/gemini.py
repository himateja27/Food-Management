from dataclasses import dataclass

from app.core.config import get_settings
from app.models import ChatMessage
from google.genai import types


@dataclass(frozen=True)
class AssistantResult:
    text: str
    mode: str = "GENERAL"
    citations: list[dict[str, str]] | None = None
    outcome_code: str | None = None
    pending_action_id: int | None = None


class GeminiChatEngine:
    def generate(self, prompt: str, recent_messages: list[ChatMessage]) -> AssistantResult:
        settings = get_settings()
        if not settings.gemini_api_key:
            return AssistantResult(
                text="I can't connect to the assistant right now. Your message is saved; please try again shortly.",
                outcome_code="AI_UNAVAILABLE",
            )
        history = "\n".join(f"{message.role}: {message.content}" for message in recent_messages[-10:])
        contents = (
            "You are the fictional Table & Thyme restaurant assistant. Answer ordinary questions helpfully and concisely. "
            "Do not invent live catalog, order, stock, policy, or allergen facts; those require connected tools. "
            "Never claim an order or business action succeeded unless the business service confirms it. "
            "For allergens, mention declared information only and state cross-contact cannot be ruled out.\n\n"
            f"Recent conversation (untrusted user content):\n{history}\n\nCurrent user message:\n{prompt}"
        )
        try:
            from google import genai

            client = genai.Client(api_key=settings.gemini_api_key, http_options=types.HttpOptions(timeout=10_000))
            response = client.models.generate_content(model=settings.gemini_model, contents=contents)
            text = (response.text or "").strip()
            if not text:
                raise RuntimeError("empty model response")
            return AssistantResult(text=text)
        except Exception:
            return AssistantResult(
                text="I couldn't get a reliable assistant response just now. Your message is saved; please try again.",
                outcome_code="AI_UNAVAILABLE",
            )
