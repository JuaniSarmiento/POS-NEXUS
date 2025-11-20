"""
Dependencias de FastAPI - Nexus POS
Inyección de dependencias para autenticación y Multi-Tenancy
"""
from typing import Annotated
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.core.config import settings
from app.core.db import get_session
from app.models import User, Tienda
from app.schemas import TokenData


# OAuth2 scheme para extraer el token del header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)]
) -> User:
    """
    Dependencia que valida el JWT y retorna el usuario actual
    
    Validaciones:
    1. Token válido y no expirado
    2. Usuario existe en BD
    3. Usuario está activo
    
    Raises:
        HTTPException 401: Credenciales inválidas
        HTTPException 403: Usuario inactivo
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decodificar JWT
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
        
        token_data = TokenData(user_id=user_id)
    
    except JWTError:
        raise credentials_exception
    
    # Buscar usuario en BD con relación a Tienda
    statement = select(User).where(User.id == UUID(token_data.user_id))
    result = await session.execute(statement)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    
    return user


async def get_current_active_tienda(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)]
) -> Tienda:
    """
    Dependencia crítica Multi-Tenant
    
    Validaciones:
    1. Usuario tiene tienda_id asignada
    2. La tienda existe en BD
    3. La tienda está activa
    
    Este es el punto de control principal para aislar datos por tenant
    
    Raises:
        HTTPException 403: Usuario sin tienda asignada
        HTTPException 404: Tienda no encontrada
        HTTPException 403: Tienda inactiva
    """
    if not current_user.tienda_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario no tiene una tienda asignada"
        )
    
    # Buscar la tienda
    statement = select(Tienda).where(Tienda.id == current_user.tienda_id)
    result = await session.execute(statement)
    tienda = result.scalar_one_or_none()
    
    if tienda is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tienda no encontrada"
        )
    
    if not tienda.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La tienda está inactiva. Contacte al administrador"
        )
    
    return tienda


# Aliases para uso simplificado con Annotated
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentTienda = Annotated[Tienda, Depends(get_current_active_tienda)]
