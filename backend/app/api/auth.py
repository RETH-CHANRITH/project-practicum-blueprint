from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.models import User, Profile
from app.schemas.schemas import (
    UserRegisterRequest,
    RegisterResponse,
    UserLoginRequest,
    LoginResponse,
    UserResponse
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(
    data: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """EP-02: Register a new candidate user"""
    # Check if email is already taken
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "CONFLICT",
                    "message": "Email is already registered in the system",
                    "details": []
                }
            }
        )

    # Create new user
    new_user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        role="user"
    )
    db.add(new_user)
    db.flush()

    # Automatically initialize a blank profile
    default_profile = Profile(
        user_id=new_user.id,
        full_name=data.email.split("@")[0].capitalize(),
        experience_level="entry",
        preferred_role="Candidate",
        preferred_location="Phnom Penh"
    )
    db.add(default_profile)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(subject=str(new_user.id))

    return {
        "user_id": new_user.id,
        "email": new_user.email,
        "role": new_user.role,
        "token": token
    }

@router.post("/login", response_model=LoginResponse)
def login(
    data: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """EP-03: Authenticate user and receive Bearer JWT token"""
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid email or password",
                    "details": []
                }
            }
        )

    token = create_access_token(subject=str(user.id))

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role
        }
    }
