from fastapi import APIRouter
from app.api.routes.root import router as root_router
from app.api.routes.ping import router as ping_router
from app.api.routes.admin import router as admin_router

router = APIRouter()

router.include_router(root_router, tags=["root"])
router.include_router(ping_router, tags=["ping"])
router.include_router(admin_router, prefix="/admin", tags=["admin"])
