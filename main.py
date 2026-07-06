from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.auth.router import router as auth_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.dashboard.router import router as dashboard_router
from app.database.indexes import create_indexes
from app.database.mongodb import close_mongo_connection, connect_to_mongo
from app.emails.router import router as emails_router
from app.employees.router import router as employees_router
from app.logs.router import router as logs_router
from app.middleware.error_handler import register_exception_handlers
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.n8n.router import router as n8n_router
from app.profiles.router import router as profiles_router
from app.reports.router import router as reports_router
from app.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    await create_indexes()
    yield
    await close_mongo_connection()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(employees_router)
app.include_router(profiles_router)
app.include_router(emails_router)
app.include_router(dashboard_router)
app.include_router(logs_router)
app.include_router(n8n_router)
app.include_router(reports_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"success": True, "message": "Service is healthy"}
