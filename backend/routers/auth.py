from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.user import User
from services.auth import verify_password, create_access_token
from dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email (as username field) and password.
    Returns JWT access token.
    """
    result = await db.execute(
        select(User).where(User.email == form_data.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Cuenta desactivada. Contacta a tu administrador.",
        )

    token = create_access_token({
        "user_id": user.user_id,
        "role":    user.role,
        "name":    user.name,
    })

    return {
        "access_token": token,
        "token_type":   "bearer",
        "user_id":      user.user_id,
        "name":         user.name,
        "role":         user.role,
        "dealership_id": user.dealership_id,
    }


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    """Returns the current authenticated user's profile."""
    return {
        "user_id":      current_user.user_id,
        "name":         current_user.name,
        "email":        current_user.email,
        "username":     current_user.username,
        "role":         current_user.role,
        "dealership_id": current_user.dealership_id,
        "is_active":    current_user.is_active,
    }
