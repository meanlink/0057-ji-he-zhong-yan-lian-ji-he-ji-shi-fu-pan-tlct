from fastapi import APIRouter
from roster_routes import router as router_0
from clock_routes import router as router_1
from tail_routes import router as router_2
from followup_routes import router as router_3
from muster_seed import seed
from tail_worker import run as run_job

router = APIRouter(prefix="/api")
router.include_router(router_0)
router.include_router(router_1)
router.include_router(router_2)
router.include_router(router_3)
