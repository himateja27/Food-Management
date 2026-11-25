from app.ai.agent import GeminiAgent
from app.ai.gemini import AssistantResult, GeminiChatEngine
from app.ai.rag import RagService
from app.models import ChatMessage
from sqlalchemy.orm import Session

POLICY_TERMS = (
    "policy",
    "allergen",
    "allergy",
    "ingredient",
    "refund",
    "cross-contact",
    "cross contact",
    "hours",
    "opening time",
    "closing time",
    "are you open",
    "contains",
)
LIVE_TERMS = ("menu", "available", "availability", "portion", "stock", "price", "cost", "order", "cancel", "dish", "dishes", "recommend", "do you have")


class ChatOrchestrator:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.general_engine = GeminiChatEngine()

    def generate(
        self,
        prompt: str,
        recent_messages: list[ChatMessage],
        *,
        user_id: int,
        session_id: int,
        message_id: int,
    ) -> AssistantResult:
        lowered = prompt.lower()
        asks_policy = any(term in lowered for term in POLICY_TERMS)
        asks_live = any(term in lowered for term in LIVE_TERMS)
        if asks_live:
            mode = "MIXED" if asks_policy else "AGENT"
            return GeminiAgent(self.session).respond(
                prompt,
                recent_messages,
                user_id=user_id,
                session_id=session_id,
                message_id=message_id,
                mode=mode,
            )
        if asks_policy:
            answer, citations, outcome_code = RagService(self.session).answer(prompt)
            return AssistantResult(text=answer, mode="RAG", citations=citations, outcome_code=outcome_code)
        return self.general_engine.generate(prompt, recent_messages)
