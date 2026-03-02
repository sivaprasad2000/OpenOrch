from fastapi import APIRouter

from app.api.v1.endpoints import auth, health
from app.api.v1.endpoints.authenticated import (
    llms,
    organizations,
    test_cases,
    test_groups,
    test_runs,
    users,
)
from app.api.v1.endpoints.internal import test_runs as internal_test_runs

api_router = APIRouter()

api_router.include_router(health.router, prefix="", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="", tags=["users"])
api_router.include_router(organizations.router, prefix="", tags=["organizations"])
api_router.include_router(llms.router, prefix="", tags=["llms"])
api_router.include_router(test_groups.router, prefix="", tags=["test-groups"])
api_router.include_router(test_cases.router, prefix="", tags=["test-cases"])
api_router.include_router(test_runs.router, prefix="", tags=["test-runs"])
api_router.include_router(internal_test_runs.router, prefix="/internal", tags=["internal"])
