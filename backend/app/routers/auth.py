import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserLogin, UserOut, UserRoleUpdate, Token
from app.services.auth import verify_password, get_password_hash, create_access_token, get_current_user, require_roles

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    # Check if university_id or email exists
    if db.query(User).filter(User.university_id == user_in.university_id).first():
        raise HTTPException(status_code=400, detail="University ID already registered")
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email address already registered")

    user_id = f"usr-{uuid.uuid4().hex[:10]}"
    db_user = User(
        id=user_id,
        university_id=user_in.university_id,
        full_name=user_in.full_name,
        email=user_in.email,
        phone=user_in.phone,
        role=UserRole.STUDENT,
        telegram_chat_id=user_in.telegram_chat_id,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    token = create_access_token(data={"sub": db_user.id, "role": db_user.role.value})
    return Token(access_token=token, token_type="bearer", user=UserOut.model_validate(db_user))

@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    # Search by university ID or email
    user = db.query(User).filter(
        (User.university_id == login_data.university_id_or_email) | 
        (User.email == login_data.university_id_or_email)
    ).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect University ID/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is deactivated")

    token = create_access_token(data={"sub": user.id, "role": user.role.value})
    return Token(access_token=token, token_type="bearer", user=UserOut.model_validate(user))

@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)

@router.get("/users", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return db.query(User).order_by(User.full_name.asc()).all()

@router.patch("/users/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: str,
    role_update: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot change your own role")

    if target_user.role == UserRole.ADMIN and role_update.role != UserRole.ADMIN and target_user.is_active:
        active_admin_count = db.query(User).filter(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
        ).count()
        if active_admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last active administrator")

    previous_role = target_user.role
    target_user.role = role_update.role
    db.add(AuditLog(
        id=f"aud-{uuid.uuid4().hex[:8]}",
        actor_id=current_user.id,
        action="UPDATE_USER_ROLE",
        target_entity="users",
        target_id=target_user.id,
        details=f"Changed role from {previous_role.value} to {role_update.role.value}",
    ))
    db.commit()
    db.refresh(target_user)
    return UserOut.model_validate(target_user)
