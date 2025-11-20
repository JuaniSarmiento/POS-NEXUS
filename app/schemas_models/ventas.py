"""
Schemas Pydantic para Ventas - Nexus POS
DTOs para el proceso de venta y checkout
"""
from datetime import datetime
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# ==================== VENTA INPUT SCHEMAS ====================

class ItemVentaInput(BaseModel):
    """
    Schema de entrada para un item de venta
    Usado en el proceso de checkout
    """
    producto_id: UUID
    cantidad: float = Field(..., gt=0, description="Cantidad a vender (puede ser decimal para pesables)")
    
    @field_validator('cantidad')
    @classmethod
    def validar_cantidad_positiva(cls, v: float) -> float:
        """Valida que la cantidad sea positiva"""
        if v <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        return v


class VentaCreate(BaseModel):
    """
    Schema para crear una venta completa
    Incluye lista de items y método de pago
    """
    items: List[ItemVentaInput] = Field(..., min_length=1, description="Lista de productos a vender")
    metodo_pago: str = Field(
        ..., 
        pattern="^(efectivo|tarjeta_debito|tarjeta_credito|transferencia)$",
        description="Método de pago utilizado"
    )
    
    @field_validator('items')
    @classmethod
    def validar_items_no_vacio(cls, v: List[ItemVentaInput]) -> List[ItemVentaInput]:
        """Valida que haya al menos un item en la venta"""
        if not v or len(v) == 0:
            raise ValueError("La venta debe contener al menos un producto")
        return v


# ==================== VENTA OUTPUT SCHEMAS ====================

class DetalleVentaRead(BaseModel):
    """
    Schema de lectura para un detalle de venta
    Incluye información del producto
    """
    id: UUID
    producto_id: UUID
    producto_nombre: str = Field(description="Nombre del producto al momento de la venta")
    producto_sku: str = Field(description="SKU del producto")
    cantidad: float
    precio_unitario: float
    subtotal: float
    
    class Config:
        from_attributes = True


class VentaRead(BaseModel):
    """
    Schema de lectura para una venta completa
    Incluye detalles expandidos
    """
    id: UUID
    fecha: datetime
    total: float
    metodo_pago: str
    tienda_id: UUID
    detalles: List[DetalleVentaRead] = Field(default_factory=list)
    created_at: datetime
    
    class Config:
        from_attributes = True


class VentaListRead(BaseModel):
    """
    Schema simplificado para listado de ventas
    Sin detalles para optimizar performance
    """
    id: UUID
    fecha: datetime
    total: float
    metodo_pago: str
    created_at: datetime
    cantidad_items: int = Field(description="Cantidad de items en la venta")
    
    class Config:
        from_attributes = True


# ==================== SCAN SCHEMAS (Optimización POS) ====================

class ProductoScanRead(BaseModel):
    """
    Schema minimalista para el endpoint de escaneo
    Solo datos esenciales para velocidad máxima
    """
    id: UUID
    nombre: str
    sku: str
    precio_venta: float
    stock_actual: float
    tipo: str
    tiene_stock: bool = Field(description="Indicador rápido de disponibilidad")
    
    class Config:
        from_attributes = True


# ==================== RESUMEN DE VENTA ====================

class VentaResumen(BaseModel):
    """
    Schema para mostrar resumen de venta después del checkout
    Información condensada para ticket/comprobante
    """
    venta_id: UUID
    fecha: datetime
    total: float
    metodo_pago: str
    cantidad_items: int
    mensaje: str = "Venta procesada exitosamente"
