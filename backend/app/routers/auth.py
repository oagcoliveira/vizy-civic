from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth import BillTrack, PoliticianFollow, User
from app.services.auth_notifications import send_auth_alert

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

ALGORITHM = "HS256"


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({**data, "exp": expire}, settings.secret_key, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/register", status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=data.email,
        name=data.name,
        password_hash=_hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    send_auth_alert(
        event_type="signup",
        user_id=user.id,
        user_email=user.email,
        user_name=user.name,
    )
    return {"id": user.id, "email": user.email}


@router.post("/token", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not _verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    user.last_login_at = datetime.utcnow()
    db.commit()
    token = create_access_token({"sub": str(user.id)})
    send_auth_alert(
        event_type="login",
        user_id=user.id,
        user_email=user.email,
        user_name=user.name,
    )
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "name": current_user.name}


@router.get("/me/follows")
def my_follows(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the list of politician IDs followed by the current user."""
    rows = db.execute(text("""
        SELECT pf.politician_id, p.short_name, p.state, pa.acronym AS party, p.photo_url
        FROM auth.politician_follows pf
        JOIN core.politicians p ON p.id = pf.politician_id
        LEFT JOIN core.parties pa ON pa.id = p.party_id
        WHERE pf.user_id = :uid
        ORDER BY p.short_name
    """), {"uid": current_user.id}).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/me/tracks")
def my_tracks(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the list of bill IDs tracked by the current user."""
    rows = db.execute(text("""
        SELECT bt.bill_id, b.type, b.number, b.year, b.short_title, b.status
        FROM auth.bill_tracks bt
        JOIN core.bills b ON b.id = bt.bill_id
        WHERE bt.user_id = :uid
        ORDER BY b.year DESC, b.number DESC
    """), {"uid": current_user.id}).fetchall()
    return [dict(r._mapping) for r in rows]
