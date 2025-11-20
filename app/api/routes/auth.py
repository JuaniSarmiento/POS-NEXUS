"""
Rutas de Autenticación - Nexus POS
Endpoints para login y gestión de tokens
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.core.db import get_session
from app.core.security import verify_password, create_access_token
from app.models import User
from app.schemas import Token, LoginRequest
from app.api.deps import CurrentUser, CurrentTienda


router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> Token:
    """
    Endpoint de Login - OAuth2 Password Flow
    
    Validaciones:
    1. Usuario existe por email
    2. Password es correcto
    3. Usuario está activo
    
    Returns:
        Token JWT con el user_id en el payload (sub)
    """
    # Buscar usuario por email
    statement = select(User).where(User.email == login_data.email)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()
    
    # Validar existencia y password
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Validar que esté activo
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    
    # Crear token JWT
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return Token(access_token=access_token, token_type="bearer")


@router.post("/login/form", response_model=Token)
async def login_form(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)]
) -> Token:
    """
    Login alternativo compatible con OAuth2PasswordRequestForm
    Útil para Swagger UI y herramientas OAuth2 estándar
    """
    # Buscar usuario por email (username en el form)
    statement = select(User).where(User.email == form_data.username)
    result = await session.execute(statement)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me")
async def get_current_user_info(
    current_user: CurrentUser,
    current_tienda: CurrentTienda
) -> dict:
    """
    Endpoint para obtener información del usuario autenticado
    Incluye datos de la tienda (Multi-Tenant)
    
    Demuestra el uso de las dependencias Multi-Tenant
    """
    return {
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "rol": current_user.rol,
            "is_active": current_user.is_active
        },
        "tienda": {
            "id": str(current_tienda.id),
            "nombre": current_tienda.nombre,
            "rubro": current_tienda.rubro,
            "is_active": current_tienda.is_active
        }
    }
