from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.deps import get_current_user
from app.models import User
from app.schemas import TokenOut, UserLogin, UserOut, UserRegister
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["Auth"])


def _token(user: User) -> dict:
    return {"access_token": create_access_token(user.id, user.role), "user": user}


@router.post("/register", response_model=TokenOut, status_code=201, operation_id="register")
def register(body: UserRegister, db: Session = Depends(get_db)):
    """Create a customer account and return a login token."""
    user = user_service.register_user(db, body.name, body.email, body.password)
    return _token(user)


@router.post("/login", response_model=TokenOut, operation_id="login")
def login(body: UserLogin, db: Session = Depends(get_db)):
    """Log in with email and password. Send the token as `Authorization: Bearer <token>`."""
    return _token(user_service.authenticate(db, body.email, body.password))


@router.get("/me", response_model=UserOut, operation_id="get_current_user")
def me(user: User = Depends(get_current_user)):
    """The logged-in user's profile."""
    return user
