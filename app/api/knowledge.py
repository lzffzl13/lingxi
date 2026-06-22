"""Knowledge base management API endpoints."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import KnowledgeManagerDep
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


@router.get("/faq", response_model=list[FAQResponse])
async def list_faqs():
    """List all FAQs."""
    faqs = []
    for i, faq in enumerate(FAQ_DATABASE):
        faqs.append(FAQResponse(
            id=i,
            question=faq["question"],
            answer=faq["answer"],
            category=faq.get("category"),
            keywords=faq.get("keywords"),
        ))
    return faqs


@router.get("/faq/{faq_id}", response_model=FAQResponse)
async def get_faq(faq_id: int):
    """Get FAQ by ID."""
    if faq_id < 0 or faq_id >= len(FAQ_DATABASE):
        raise FAQNotFoundError(faq_id)

    faq = FAQ_DATABASE[faq_id]
    return FAQResponse(
        id=faq_id,
        question=faq["question"],
        answer=faq["answer"],
        category=faq.get("category"),
        keywords=faq.get("keywords"),
    )


@router.post("/faq", response_model=FAQResponse)
async def create_faq(faq: FAQCreate):
    """Create a new FAQ."""
    new_faq = {
        "question": faq.question,
        "answer": faq.answer,
        "category": faq.category,
        "keywords": faq.keywords or [],
    }
    FAQ_DATABASE.append(new_faq)

    return FAQResponse(
        id=len(FAQ_DATABASE) - 1,
        question=new_faq["question"],
        answer=new_faq["answer"],
        category=new_faq["category"],
        keywords=new_faq["keywords"],
    )


@router.put("/faq/{faq_id}", response_model=FAQResponse)
async def update_faq(faq_id: int, faq: FAQUpdate):
    """Update an existing FAQ."""
    if faq_id < 0 or faq_id >= len(FAQ_DATABASE):
        raise FAQNotFoundError(faq_id)

    existing = FAQ_DATABASE[faq_id]
    if faq.question is not None:
        existing["question"] = faq.question
    if faq.answer is not None:
        existing["answer"] = faq.answer
    if faq.category is not None:
        existing["category"] = faq.category
    if faq.keywords is not None:
        existing["keywords"] = faq.keywords

    return FAQResponse(
        id=faq_id,
        question=existing["question"],
        answer=existing["answer"],
        category=existing.get("category"),
        keywords=existing.get("keywords"),
    )


@router.delete("/faq/{faq_id}")
async def delete_faq(faq_id: int):
    """Delete a FAQ."""
    if faq_id < 0 or faq_id >= len(FAQ_DATABASE):
        raise FAQNotFoundError(faq_id)

    FAQ_DATABASE.pop(faq_id)

    return {"message": f"FAQ {faq_id} deleted"}


@router.post("/search")
async def search_knowledge(request: SearchRequest, km: KnowledgeManagerDep):
    """Search FAQs."""
    results = await km.search(request.query, request.top_k)
    return {"query": request.query, "results": results}
