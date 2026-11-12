from fastapi import APIRouter

from app.core.db import SessionDep
from app.core.errors import error_response_docs
from app.modules.tailoring import service
from app.modules.tailoring.schemas import TailoringPreview, TailoringRequest

router = APIRouter(prefix="/tailoring", tags=["tailoring"])


# POST, not GET: the offer requirements are a JSON body; nothing is saved
@router.post("/preview", responses=error_response_docs(422))
async def preview(payload: TailoringRequest, session: SessionDep) -> TailoringPreview:
    result = await service.preview(session, payload)
    return TailoringPreview.from_domain(result)
