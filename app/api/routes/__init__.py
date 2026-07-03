from fastapi import APIRouter
from app.api.routes.root import router as root_router
from app.api.routes.ping import router as ping_router
from app.api.routes.admin import router as admin_router
from app.api.routes.nodes import router as nodes_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.ledger import router as ledger_router
from app.api.routes.engineer import router as engineer_router

router = APIRouter()

router.include_router(root_router, tags=["root"])
router.include_router(ping_router, tags=["ping"])
router.include_router(admin_router, prefix="/admin", tags=["admin"])
router.include_router(nodes_router, prefix="/api/nodes", tags=["nodes"])
router.include_router(tasks_router, prefix="/api", tags=["tasks"])
router.include_router(ledger_router, prefix="/api/ledger", tags=["ledger"])
router.include_router(engineer_router, prefix="/api/engineer", tags=["engineer"])
