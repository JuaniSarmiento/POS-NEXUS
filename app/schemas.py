"""
Schemas Pydantic - Nexus POS
DTOs para validación de entrada/salida
"""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ==================== TIENDA SCHEMAS ====================

class TiendaBase(BaseModel):
    """Schema base de Tienda"""
    nombre: str = Field(..., min_length=1, max_length=255)
    rubro: str = Field(..., min_length=1, max_length=100)


class TiendaCreate(TiendaBase):
    """Schema para crear una Tienda"""
    pass


class TiendaUpdate(BaseModel):
    """Schema para actualizar una Tienda"""
    nombre: Optional[str] = Field(None, min_length=1, max_length=255)
    rubro: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None


class TiendaResponse(TiendaBase):
    """Schema de respuesta de Tienda"""
    id: UUID
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== USER SCHEMAS ====================

class UserBase(BaseModel):
    """Schema base de Usuario"""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    rol: str = Field(..., pattern="^(owner|cajero|admin)$")


class UserCreate(UserBase):
    """Schema para crear un Usuario"""
    password: str = Field(..., min_length=8)
    tienda_id: UUID


class UserUpdate(BaseModel):
    """Schema para actualizar un Usuario"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    password: Optional[str] = Field(None, min_length=8)
    rol: Optional[str] = Field(None, pattern="^(owner|cajero|admin)$")
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema de respuesta de Usuario"""
    id: UUID
    is_active: bool
    created_at: datetime
    tienda_id: UUID
    tienda: Optional[TiendaResponse] = None
    
    class Config:
        from_attributes = True


# ==================== AUTH SCHEMAS ====================

class Token(BaseModel):
    """Schema de respuesta de autenticación"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Datos decodificados del token JWT"""
    user_id: Optional[str] = None


class LoginRequest(BaseModel):
    """Schema de request para login"""
    email: EmailStr
    password: str
