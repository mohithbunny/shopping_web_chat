"""Entry point. Run from the backend folder:  uvicorn app.main:app --reload"""
import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app import models  # noqa: F401  (registers tables)
from app.core.config import FRONTEND_DIR
from app.core.database import Base, engine, get_db
from app.routers import admin, auth, cart, orders, products
from app.services.errors import ServiceError
from app.services import product_service
from sqlalchemy.orm import Session
from app.services.llm_service import llm_invoke 

class ChatbotInput(BaseModel):
    message: str

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Haul Shop API",
    version="1.0.0",
    description="Shop backend. Every endpoint has a stable operation_id so it can be "
                "exposed to an LLM chatbot as a tool.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your real domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceError)
async def service_error_handler(_: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


for r in (auth.router, products.router, cart.router, orders.router, admin.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health", tags=["Meta"], operation_id="health")
def health():
    return {"status": "ok"}


from typing import Literal
from app.services.llm_service import llm_invoke

from app.routers.auth import get_current_user  # ADAPT to wherever yours lives


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatbotInput(BaseModel):
    message: str
    history: list[ChatMessage] = []

from fastapi.security import HTTPAuthorizationCredentials
from app.deps import bearer, get_current_user   # replaces the import from app.routers.auth


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    if not creds:
        return None          # guest
    try:
        return get_current_user(creds=creds, db=db)
    except HTTPException as e:
        print("HTTPException:", e.status_code, e.detail)
        return None          # bad or expired token: treat as guest

@app.post("/api/chatbot", tags=["Meta"], operation_id="chatbot")
def chatbot(inp: ChatbotInput, db: Session = Depends(get_db), user=Depends(get_optional_user)):
    print(f"user logged in: {user.email if user else 'guest'}")
    message = inp.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Enter a message.")

    try:
        result = llm_invoke(message, [h.model_dump() for h in inp.history], db, user)
        if result["output"]:
            return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        print("LLM error:", repr(e))
        raise HTTPException(status_code=502, detail="The chat assistant request failed.") from e

    raise HTTPException(status_code=502, detail="The chat assistant returned an empty reply.")

# Serve the HTML/CSS/JS frontend from the same server (mounted last).
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
