from fastapi import APIRouter

from app.api.deps import router as deps_router
from app.api.route_demo import router as route_demo_router

api_router = APIRouter()
api_router.include_router(deps_router)
api_router.include_router(route_demo_router)
