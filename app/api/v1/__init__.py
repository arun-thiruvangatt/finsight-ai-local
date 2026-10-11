"""Version 1 of the public API. A future /api/v2 package can be added next to this one and mounted
in app/main.py without touching v1 behaviour."""
from fastapi import APIRouter

from app.api.v1 import (accounts, ai, analytics, auth, budgets, categories, documents, goals, imports, insights,
                        notifications, transactions, users)

api_router = APIRouter()
for module in (auth, users, accounts, categories, transactions, imports, budgets, goals, analytics, insights,
               notifications, ai, documents):
    api_router.include_router(module.router)
