from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.user import User
from models.dealership import Dealership
from services.auth import hash_password, generate_password
from services.email_service import send_credentials_email
from dependencies.auth import get_current_user

router = APIRouter(prefix="/registrar", tags=["registrar"])


class RegisterUserBody(BaseModel):
    name:          str
    email:         str
    phone:         Optional[str] = None
    dealership_id: int
    role:          str  # "vendor" or "manager"


class DeactivateUserBody(BaseModel):
    user_id: int


class ReactivateUserBody(BaseModel):
    user_id: int


@router.get("/dealerships")
async def get_dealerships(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dealership).order_by(Dealership.name.asc()))
    return [{"dealership_id": d.dealership_id, "name": d.name} for d in result.scalars().all()]


@router.get("/users")
async def get_users(db: AsyncSession = Depends(get_db)):
    """Returns all vendor and manager users for deactivate/reactivate search."""
    result = await db.execute(
        select(User)
        .where(User.role.in_(["vendor", "manager"]))
        .order_by(User.name.asc())
    )
    users = result.scalars().all()
    return [
        {
            "user_id":   u.user_id,
            "name":      u.name,
            "email":     u.email,
            "role":      u.role,
            "is_active": u.is_active,
            "dealership_id": u.dealership_id,
        }
        for u in users
    ]


@router.post("/usuario")
async def register_user(
    body: RegisterUserBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registers a new user. Permission rules:
    - master can register any role
    - owner can register manager
    - manager can register vendor
    """
    allowed = {
        "master":  ["owner", "manager", "vendor"],
        "owner":   ["manager"],
        "manager": ["vendor"],
    }
    if current_user.role not in allowed or body.role not in allowed.get(current_user.role, []):
        raise HTTPException(status_code=403, detail="No tienes permiso para registrar este tipo de usuario.")

    # Check email unique
    existing = await db.execute(select(User).where(User.email == body.email).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo.")

    # Validate dealership
    dealership = await db.execute(select(Dealership).where(Dealership.dealership_id == body.dealership_id))
    if not dealership.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Sucursal no encontrada.")

    # Generate credentials
    username = body.email.split("@")[0]
    password = generate_password(6)

    user = User(
        name            = body.name.strip(),
        email           = body.email.strip().lower(),
        username        = username,
        hashed_password = hash_password(password),
        role            = body.role,
        phone           = body.phone,
        dealership_id   = body.dealership_id,
        is_active       = True,
        created_by      = current_user.user_id,
    )
    db.add(user)
    await db.flush()
    await db.commit()

    # Send credentials email
    try:
        await send_credentials_email(
            to_email = body.email,
            name     = body.name,
            username = username,
            password = password,
        )
    except Exception:
        pass  # Email failure should not block registration

    return {
        "success":  True,
        "message":  f"Usuario {user.name} registrado. Credenciales enviadas a {body.email}.",
        "user_id":  user.user_id,
        "username": username,
    }


@router.post("/desactivar")
async def deactivate_user(
    body: DeactivateUserBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.user_id == body.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if user.role in ["master", "owner"] and current_user.role != "master":
        raise HTTPException(status_code=403, detail="No tienes permiso para desactivar este usuario.")
    user.is_active = False
    await db.commit()
    return {"success": True, "message": f"Usuario {user.name} desactivado."}


@router.post("/reactivar")
async def reactivate_user(
    body: ReactivateUserBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.user_id == body.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    user.is_active = True
    await db.commit()
    return {"success": True, "message": f"Usuario {user.name} reactivado."}
