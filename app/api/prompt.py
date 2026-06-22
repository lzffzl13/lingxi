"""Prompt management API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.prompt import get_prompt_manager, get_ab_test_manager, get_evaluator

router = APIRouter(prefix="/prompt", tags=["prompt"])


# Request/Response models
class PromptVersionRequest(BaseModel):
    name: str
    template: str
    description: str = ""
    tags: list[str] = []
    set_active: bool = True


class ABTestRequest(BaseModel):
    name: str
    variants: list[dict]
    description: str = ""


class EvaluationRequest(BaseModel):
    prompt_version_id: str
    test_case_ids: Optional[list[str]] = None
    category: Optional[str] = None


# Prompt Version endpoints
@router.post("/versions")
async def create_version(request: PromptVersionRequest):
    """Create a new prompt version."""
    manager = get_prompt_manager()
    version = manager.add_version(
        name=request.name,
        template=request.template,
        description=request.description,
        tags=request.tags,
        set_active=request.set_active,
    )
    return {
        "id": version.id,
        "name": version.name,
        "version": version.version,
        "hash": version.hash,
    }


@router.get("/versions/{name}")
async def get_versions(name: str):
    """Get all versions of a prompt."""
    manager = get_prompt_manager()
    versions = manager.get_all_versions(name)
    return {
        "name": name,
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "description": v.description,
                "created_at": v.created_at,
                "hash": v.hash,
                "metrics": v.metrics,
            }
            for v in versions
        ],
    }


@router.get("/active/{name}")
async def get_active_version(name: str):
    """Get the active version of a prompt."""
    manager = get_prompt_manager()
    version = manager.get_active(name)
    if not version:
        raise HTTPException(status_code=404, detail=f"No active version for {name}")
    return {
        "id": version.id,
        "name": version.name,
        "template": version.template,
        "version": version.version,
    }


@router.post("/active/{name}/{version_id}")
async def set_active_version(name: str, version_id: str):
    """Set a specific version as active."""
    manager = get_prompt_manager()
    success = manager.set_active(name, version_id)
    if not success:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"message": "Active version updated"}


@router.post("/rollback/{name}")
async def rollback_version(name: str, steps: int = 1):
    """Rollback to a previous version."""
    manager = get_prompt_manager()
    version = manager.rollback(name, steps)
    if not version:
        raise HTTPException(status_code=400, detail="Cannot rollback")
    return {
        "id": version.id,
        "version": version.version,
        "message": f"Rolled back to version {version.version}",
    }


# A/B Testing endpoints
@router.post("/tests")
async def create_test(request: ABTestRequest):
    """Create a new A/B test."""
    manager = get_ab_test_manager()
    test = manager.create_test(
        name=request.name,
        variants=request.variants,
        description=request.description,
    )
    return {
        "id": test.id,
        "name": test.name,
        "variants": [{"id": v.id, "name": v.name} for v in test.variants],
    }


@router.get("/tests")
async def list_tests():
    """List all A/B tests."""
    manager = get_ab_test_manager()
    tests = manager.get_active_tests()
    return {
        "tests": [
            {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "variants": len(t.variants),
            }
            for t in tests
        ],
    }


@router.get("/tests/{test_id}")
async def get_test_results(test_id: str):
    """Get A/B test results."""
    manager = get_ab_test_manager()
    results = manager.get_results(test_id)
    if not results:
        raise HTTPException(status_code=404, detail="Test not found")
    return results


@router.post("/tests/{test_id}/pause")
async def pause_test(test_id: str):
    """Pause an A/B test."""
    manager = get_ab_test_manager()
    success = manager.pause_test(test_id)
    if not success:
        raise HTTPException(status_code=404, detail="Test not found")
    return {"message": "Test paused"}


@router.post("/tests/{test_id}/resume")
async def resume_test(test_id: str):
    """Resume an A/B test."""
    manager = get_ab_test_manager()
    success = manager.resume_test(test_id)
    if not success:
        raise HTTPException(status_code=404, detail="Test not found")
    return {"message": "Test resumed"}


# Statistics endpoints
@router.get("/stats")
async def get_stats():
    """Get prompt engineering statistics."""
    prompt_mgr = get_prompt_manager()
    ab_mgr = get_ab_test_manager()
    evaluator = get_evaluator()

    return {
        "prompts": prompt_mgr.get_stats(),
        "ab_tests": ab_mgr.get_stats(),
        "evaluations": evaluator.get_stats(),
    }
