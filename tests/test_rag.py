from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pymupdf
from docx import Document as WordDocument
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.ai.rag import RagService, RetrievedChunk, chunk_sections, extract_text
from app.core.config import get_settings
from app.models import Base, Document, User


class FakeEmbedder:
    def embed(self, texts, task_type="RETRIEVAL_DOCUMENT"):
        return [[float(len(text)), 1.0] for text in texts]


class FakeVectorStore:
    def __init__(self):
        self.documents = {}
        self.active = set()

    def add_document(self, document_id, chunks, vectors, filename, version):
        self.documents[document_id] = (chunks, filename, version)
        self.active.add(document_id)

    def deactivate_document(self, document_id):
        self.active.discard(document_id)

    def delete_document(self, document_id):
        self.documents.pop(document_id, None)
        self.active.discard(document_id)

    def search(self, vector, limit):
        if not self.active:
            return []
        document_id = max(self.active)
        chunks, filename, version = self.documents[document_id]
        return [RetrievedChunk(chunks[0].text, filename, chunks[0].section, 0.1, document_id, version)][:limit]


def test_extracts_supported_formats_and_chunks_with_overlap() -> None:
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Fictional policy page one")
    pdf_bytes = pdf.tobytes()
    pdf.close()
    paragraphs = WordDocument()
    paragraphs.add_heading("Returns", level=1)
    paragraphs.add_paragraph("Orders can be cancelled before preparation begins.")
    docx_buffer = BytesIO()
    paragraphs.save(docx_buffer)

    assert extract_text("policy.pdf", pdf_bytes)[0][1] == "page 1"
    assert "Returns" in extract_text("policy.docx", docx_buffer.getvalue())[0][0]
    assert extract_text("policy.txt", b"First line\nSecond line")[1][1] == "line 2"
    chunks = chunk_sections([("word " * 400, "page 1")])
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 800 for chunk in chunks)
    assert chunks[0].text[-30:].split()[0] in chunks[1].text


def test_upload_versions_deactivate_old_document_and_citations_are_structured() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    user = User(email="admin@example.test", full_name="Admin", password_hash="x", role="ADMIN")
    session.add(user)
    session.commit()
    store = FakeVectorStore()
    rag = RagService(session, embedder=FakeEmbedder(), vector_store=store)

    first = rag.upload(user.id, "../allergen-policy.txt", b"Cross-contact cannot be ruled out.", "text/plain")
    second = rag.upload(user.id, "allergen-policy.txt", b"Ask staff about declared allergens.", "text/plain")
    answer, citations, outcome = rag.answer("What is the allergen policy?")

    assert first.filename == "allergen-policy.txt"
    assert first.version == 1 and not first.is_active
    assert second.version == 2 and second.is_active
    assert store.active == {second.id}
    assert answer
    assert citations == [{"filename": "allergen-policy.txt", "section": "line 1"}]
    assert (outcome == "AI_UNAVAILABLE") if not get_settings().gemini_api_key else (outcome is None)
    session.close()
    engine.dispose()


def test_missing_active_evidence_says_cannot_verify() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    rag = RagService(session, embedder=FakeEmbedder(), vector_store=FakeVectorStore())

    answer, citations, outcome = rag.answer("What does the policy say?")

    assert "can't verify" in answer
    assert citations == []
    assert outcome is None


def test_database_active_version_filters_stale_vector_metadata() -> None:
    class StaleVectorStore(FakeVectorStore):
        def deactivate_document(self, document_id):
            pass

        def search(self, vector, limit):
            results = []
            for document_id in sorted(self.documents):
                chunks, filename, version = self.documents[document_id]
                results.append(RetrievedChunk(chunks[0].text, filename, chunks[0].section, 0.1, document_id, version))
            return results[:limit]

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    user = User(email="admin@example.test", full_name="Admin", password_hash="x", role="ADMIN")
    session.add(user)
    session.commit()
    store = StaleVectorStore()
    rag = RagService(session, embedder=FakeEmbedder(), vector_store=store)
    first = rag.upload(user.id, "policy.txt", b"old policy text", "text/plain")
    second = rag.upload(user.id, "policy.txt", b"new policy text", "text/plain")

    results = rag.retrieve("policy")

    assert first.id != second.id
    assert [chunk.document_id for chunk in results] == [second.id]
    session.close()
    engine.dispose()


def test_policy_answer_uses_citations_from_retrieved_evidence(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    store = FakeVectorStore()
    rag = RagService(session, embedder=FakeEmbedder(), vector_store=store)
    user = User(email="admin@example.test", full_name="Admin", password_hash="x", role="ADMIN")
    session.add(user)
    session.commit()
    rag.upload(user.id, "allergen-policy.txt", b"Cross-contact cannot be ruled out.", "text/plain")

    class FakeModels:
        def generate_content(self, **kwargs):
            assert "untrusted_document_text" in kwargs["contents"]
            return SimpleNamespace(text="Cross-contact cannot be ruled out. [allergen-policy.txt, line 1]")

    class FakeClient:
        models = FakeModels()

        def __init__(self, api_key, http_options):
            assert api_key == "fake-key"
            assert http_options.timeout == 10_000

    monkeypatch.setattr("app.ai.rag.get_settings", lambda: SimpleNamespace(gemini_api_key="fake-key", gemini_model="test-model"))
    monkeypatch.setattr("app.ai.rag.genai.Client", FakeClient)

    answer, citations, outcome = rag.answer("What is the allergen policy?")

    assert "allergen-policy.txt" in answer
    assert citations == [{"filename": "allergen-policy.txt", "section": "line 1"}]
    assert outcome is None
    session.close()
    engine.dispose()
