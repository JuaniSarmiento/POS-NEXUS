"""
Schemas Pydantic para Productos - Nexus POS
Validación polimórfica según tipo de producto
"""
from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, ValidationError


# ==================== PRODUCTO SCHEMAS ====================

class ProductoBase(BaseModel):
    """Schema base de Producto"""
    nombre: str = Field(..., min_length=1, max_length=255)
    sku: str = Field(..., min_length=1, max_length=100)
    descripcion: Optional[str] = None
    precio_venta: float = Field(..., gt=0, description="Debe ser mayor a 0")
    precio_costo: float = Field(..., ge=0, description="Debe ser mayor o igual a 0")
    tipo: str = Field(..., pattern="^(general|ropa|pesable)$")
    atributos: Dict[str, Any] = Field(default_factory=dict)


class ProductoCreate(ProductoBase):
    """
    Schema para crear un Producto
    Incluye validadores personalizados según el tipo
    """
    stock_actual: float = Field(default=0.0, ge=0)
    
    @field_validator('atributos')
    @classmethod
    def validate_atributos_por_tipo(cls, v: Dict[str, Any], info) -> Dict[str, Any]:
        """
        Valida que los atributos JSONB cumplan con la estructura esperada
        según el tipo de producto
        """
        tipo = info.data.get('tipo')
        
        if tipo == 'ropa':
            # Validar estructura para ropa: debe tener variantes
            if 'variantes' not in v:
                raise ValueError(
                    "Productos tipo 'ropa' deben tener 'variantes' en atributos. "
                    "Ejemplo: {'variantes': [{'talle': 'M', 'color': 'Rojo', 'stock': 10}]}"
                )
            
            variantes = v.get('variantes')
            if not isinstance(variantes, list) or len(variantes) == 0:
                raise ValueError("'variantes' debe ser una lista no vacía")
            
            # Validar cada variante
            for idx, variante in enumerate(variantes):
                if not isinstance(variante, dict):
                    raise ValueError(f"Variante en posición {idx} debe ser un objeto")
                
                # Campos requeridos
                if 'talle' not in variante or 'color' not in variante or 'stock' not in variante:
                    raise ValueError(
                        f"Variante en posición {idx} debe tener: 'talle', 'color', 'stock'. "
                        f"Recibido: {list(variante.keys())}"
                    )
                
                # Validar stock numérico
                if not isinstance(variante['stock'], (int, float)) or variante['stock'] < 0:
                    raise ValueError(f"Stock en variante {idx} debe ser un número >= 0")
        
        elif tipo == 'pesable':
            # Validar estructura para pesables: debe tener unidad_medida
            if 'unidad_medida' not in v:
                raise ValueError(
                    "Productos tipo 'pesable' deben tener 'unidad_medida' en atributos. "
                    "Ejemplo: {'unidad_medida': 'kg'}"
                )
            
            unidad_medida = v.get('unidad_medida')
            if unidad_medida not in ['kg', 'g', 'lt', 'ml']:
                raise ValueError(
                    f"'unidad_medida' debe ser 'kg', 'g', 'lt' o 'ml'. Recibido: '{unidad_medida}'"
                )
        
        return v
    
    @field_validator('precio_costo')
    @classmethod
    def precio_costo_menor_que_venta(cls, v: float, info) -> float:
        """Valida que el precio de costo sea menor al de venta (advertencia lógica)"""
        precio_venta = info.data.get('precio_venta')
        if precio_venta and v > precio_venta:
            # No bloqueamos, pero esto podría ser un warning en logs
            pass
        return v


class ProductoUpdate(BaseModel):
    """Schema para actualizar un Producto"""
    nombre: Optional[str] = Field(None, min_length=1, max_length=255)
    sku: Optional[str] = Field(None, min_length=1, max_length=100)
    descripcion: Optional[str] = None
    precio_venta: Optional[float] = Field(None, gt=0)
    precio_costo: Optional[float] = Field(None, ge=0)
    stock_actual: Optional[float] = Field(None, ge=0)
    tipo: Optional[str] = Field(None, pattern="^(general|ropa|pesable)$")
    atributos: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ProductoRead(ProductoBase):
    """Schema de respuesta de Producto"""
    id: UUID
    stock_actual: float
    is_active: bool
    created_at: datetime
    updated_at: datetime
    tienda_id: UUID
    
    class Config:
        from_attributes = True


class ProductoReadWithCalculatedStock(ProductoRead):
    """
    Schema extendido que incluye el stock calculado para productos tipo ropa
    """
    stock_calculado: Optional[float] = Field(
        default=None,
        description="Stock total calculado desde variantes (solo para tipo ropa)"
    )
