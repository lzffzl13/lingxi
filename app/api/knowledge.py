"""Knowledge base management API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_knowledge_manager
from app.db import database
from app.db.models import FAQ
from app.db.repositories import FAQRepository
from app.exceptions import FAQNotFoundError
from app.knowledge.manager import FAQ_DATABASE

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class FAQCreate(BaseModel):
    question: str
    answer: str
    category: Optional[str] = None
    keywords: Optional[list[str]] = None


class FAQUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    keywords: Optional[list[str]] = None


class FAQResponse(BaseModel):
    id: int
    question: str
    answer: str
    category: Optional[str]
    keywords: Optional[list[str]]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


def _to_faq_response(faq_id: int, faq: dict) -> FAQResponse:
    return FAQResponse(
        id=faq_id,
        question=faq["question"],
        answer=faq["answer"],
        category=faq.get("category"),
        keywords=faq.get("keywords"),
    )


async def _refresh_knowledge_index(knowledge_manager) -> None:
    refresh_index = getattr(knowledge_manager, "refresh_index", None)
    if refresh_index:
        await refresh_index()


@router.get("/faq", response_model=list[FAQResponse])
async def list_faqs(limit: int = 100, offset: int = 0):
    """List all FAQs."""
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    if database.async_session_factory:
        async with database.async_session_factory() as session:
            repo = FAQRepository(session)
            faqs = await repo.get_all(active_only=True, limit=limit, offset=offset)
            return [_to_faq_response(faq.id, faq.to_dict()) for faq in faqs]

    faqs = []
    for i, faq in enumerate(FAQ_DATABASE[offset : offset + limit]):
        faqs.append(_to_faq_response(offset + i, faq))
    return faqs


@router.get("/faq/{faq_id}", response_model=FAQResponse)
async def get_faq(faq_id: int):
    """Get FAQ by ID."""
    if database.async_session_factory:
        async with database.async_session_factory() as session:
            repo = FAQRepository(session)
            faq = await repo.get_by_id(faq_id)
            if not faq or not faq.is_active:
                raise FAQNotFoundError(faq_id)
            return _to_faq_response(faq.id, faq.to_dict())

    if faq_id < 0 or faq_id >= len(FAQ_DATABASE):
        raise FAQNotFoundError(faq_id)

    return _to_faq_response(faq_id, FAQ_DATABASE[faq_id])


@router.post("/faq", response_model=FAQResponse)
async def create_faq(faq: FAQCreate, knowledge_manager=Depends(get_knowledge_manager)):
    """Create a new FAQ."""
    if database.async_session_factory:
        async with database.async_session_factory() as session:
            repo = FAQRepository(session)
            created = await repo.create(
                FAQ(
                    question=faq.question,
                    answer=faq.answer,
                    category=faq.category,
                    keywords=faq.keywords or [],
                )
            )
            await session.commit()
            response = _to_faq_response(created.id, created.to_dict())
        await _refresh_knowledge_index(knowledge_manager)
        return response

    new_faq = {
        "question": faq.question,
        "answer": faq.answer,
        "category": faq.category,
        "keywords": faq.keywords or [],
    }
    FAQ_DATABASE.append(new_faq)
    await _refresh_knowledge_index(knowledge_manager)

    return _to_faq_response(len(FAQ_DATABASE) - 1, new_faq)


@router.put("/faq/{faq_id}", response_model=FAQResponse)
async def update_faq(faq_id: int, faq: FAQUpdate, knowledge_manager=Depends(get_knowledge_manager)):
    """Update an existing FAQ."""
    update_values = faq.model_dump(exclude_unset=True)
    if database.async_session_factory:
        async with database.async_session_factory() as session:
            repo = FAQRepository(session)
            existing = await repo.get_by_id(faq_id)
            if not existing or not existing.is_active:
                raise FAQNotFoundError(faq_id)
            if update_values:
                await repo.update(faq_id, **update_values)
                await session.commit()
                await session.refresh(existing)
            response = _to_faq_response(existing.id, existing.to_dict())
        await _refresh_knowledge_index(knowledge_manager)
        return response

    if faq_id < 0 or faq_id >= len(FAQ_DATABASE):
        raise FAQNotFoundError(faq_id)

    existing = FAQ_DATABASE[faq_id]
    existing.update(update_values)
    await _refresh_knowledge_index(knowledge_manager)

    return _to_faq_response(faq_id, existing)


@router.delete("/faq/{faq_id}")
async def delete_faq(faq_id: int, knowledge_manager=Depends(get_knowledge_manager)):
    """Delete a FAQ."""
    if database.async_session_factory:
        async with database.async_session_factory() as session:
            repo = FAQRepository(session)
            deleted = await repo.delete(faq_id)
            if not deleted:
                raise FAQNotFoundError(faq_id)
            await session.commit()
        await _refresh_knowledge_index(knowledge_manager)
        return {"message": f"FAQ {faq_id} deleted"}

    if faq_id < 0 or faq_id >= len(FAQ_DATABASE):
        raise FAQNotFoundError(faq_id)

    FAQ_DATABASE.pop(faq_id)
    await _refresh_knowledge_index(knowledge_manager)

    return {"message": f"FAQ {faq_id} deleted"}


@router.post("/search")
async def search_knowledge(request: SearchRequest, km=Depends(get_knowledge_manager)):
    """Search FAQs."""
    results = await km.search(request.query, request.top_k)
    return {"query": request.query, "results": results}
