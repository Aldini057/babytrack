from fastapi import APIRouter
from app.api.v1.endpoints_settings import router as settings_router
from app.api.v1.endpoints_checklist import router as checklist_router
from app.api.v1.endpoints_journal import router as journal_router
from app.api.v1.endpoints_medical import router as medical_router
from app.api.v1.endpoints_media import moments_router, vault_router
from app.api.v1.endpoints_auth import auth_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(settings_router, prefix="/settings", tags=["Settings"])
api_router.include_router(checklist_router, prefix="/checklist", tags=["Checklist"])
api_router.include_router(journal_router, prefix="/journal", tags=["Journal"])
api_router.include_router(medical_router, prefix="/medical", tags=["Medical"])
api_router.include_router(moments_router, prefix="/moments", tags=["Moments"])
api_router.include_router(vault_router, prefix="/vault", tags=["Vault"])
