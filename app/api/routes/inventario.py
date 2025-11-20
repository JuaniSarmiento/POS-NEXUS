"""
Gestión Avanzada de Inventario - Nexus POS
Movimientos de stock, alertas y transferencias
"""
import logging
from typing import Annotated, List, Optional
from datetime import datetime
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from pydantic import BaseModel, Field
from app.core.db import get_session
from app.models import Producto
from app.api.deps import CurrentTienda, CurrentUser
from app.core.logging_config import log_audit


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inventario", tags=["Inventario"])


# === SCHEMAS ===

class MovimientoStock(BaseModel):
    """Registro de movimiento de stock"""
    id: UUID = Field(default_factory=uuid4)
    producto_id: UUID
    cantidad: float
    tipo_movimiento: str  # entrada, salida, ajuste, transferencia
    motivo: Optional[str] = None
    usuario_id: UUID
    fecha: datetime = Field(default_factory=datetime.utcnow)
    stock_anterior: float
    stock_nuevo: float
    

class AjusteStockRequest(BaseModel):
    """Request para ajuste manual de stock"""
    producto_id: UUID
    cantidad_nueva: float = Field(ge=0, description="Nueva cantidad de stock")
    motivo: str = Field(min_length=3, max_length=500)


class ProductoBajoStock(BaseModel):
    """Producto con stock bajo"""
    id: UUID
    sku: str
    nombre: str
    stock_actual: float
    stock_minimo: float = 10.0  # TODO: Agregar campo a modelo
    debe_reabastecer: bool = True


class TransferenciaStockRequest(BaseModel):
    """Request para transferencia entre tiendas"""
    producto_id: UUID
    tienda_destino_id: UUID
    cantidad: float = Field(gt=0)
    notas: Optional[str] = None


# === ENDPOINTS ===

@router.post("/ajustar-stock")
async def ajustar_stock_manual(
    ajuste: AjusteStockRequest,
    current_tienda: CurrentTienda,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)]
):
    """
    Ajusta manualmente el stock de un producto
    
    Casos de uso:
    - Corrección de inventario
    - Pérdida/robo de mercadería
    - Producto dañado
    - Inventario físico
    
    IMPORTANTE: Genera registro de auditoría
    """
    # Buscar producto
    stmt = select(Producto).where(
        and_(
            Producto.id == ajuste.producto_id,
            Producto.tienda_id == current_tienda.id
        )
    )
    result = await session.execute(stmt)
    producto = result.scalar_one_or_none()
    
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )
    
    # Guardar stock anterior
    stock_anterior = producto.stock_actual
    diferencia = ajuste.cantidad_nueva - stock_anterior
    
    # Actualizar stock
    producto.stock_actual = ajuste.cantidad_nueva
    session.add(producto)
    await session.commit()
    
    # LOG DE AUDITORÍA
    log_audit(
        action="AJUSTE_STOCK_MANUAL",
        user_id=str(current_user.id),
        tienda_id=str(current_tienda.id),
        details={
            "producto_id": str(producto.id),
            "producto_nombre": producto.nombre,
            "sku": producto.sku,
            "stock_anterior": stock_anterior,
            "stock_nuevo": ajuste.cantidad_nueva,
            "diferencia": diferencia,
            "motivo": ajuste.motivo
        }
    )
    
    logger.info(
        f"Stock ajustado manualmente: {producto.nombre} (SKU: {producto.sku}) "
        f"de {stock_anterior} a {ajuste.cantidad_nueva}"
    )
    
    return {
        "success": True,
        "producto_id": producto.id,
        "stock_anterior": stock_anterior,
        "stock_nuevo": producto.stock_actual,
        "diferencia": diferencia,
        "mensaje": f"Stock actualizado correctamente. Diferencia: {diferencia:+.2f}"
    }


@router.get("/alertas-stock-bajo", response_model=List[ProductoBajoStock])
async def obtener_alertas_stock_bajo(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    umbral: float = 10.0
) -> List[ProductoBajoStock]:
    """
    Obtiene lista de productos con stock bajo
    
    Útil para:
    - Dashboard de alertas
    - Planificación de compras
    - Prevenir quiebres de stock
    """
    stmt = select(Producto).where(
        and_(
            Producto.tienda_id == current_tienda.id,
            Producto.stock_actual <= umbral,
            Producto.is_active == True
        )
    ).order_by(Producto.stock_actual)
    
    result = await session.execute(stmt)
    productos = result.scalars().all()
    
    return [
        ProductoBajoStock(
            id=p.id,
            sku=p.sku,
            nombre=p.nombre,
            stock_actual=p.stock_actual,
            stock_minimo=umbral,
            debe_reabastecer=p.stock_actual < (umbral / 2)
        )
        for p in productos
    ]


@router.get("/sin-stock")
async def obtener_productos_sin_stock(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
):
    """
    Retorna productos completamente sin stock
    
    Urgente para reabastecimiento
    """
    stmt = select(Producto).where(
        and_(
            Producto.tienda_id == current_tienda.id,
            Producto.stock_actual == 0,
            Producto.is_active == True
        )
    )
    
    result = await session.execute(stmt)
    productos = result.scalars().all()
    
    return {
        "total": len(productos),
        "productos": [
            {
                "id": p.id,
                "sku": p.sku,
                "nombre": p.nombre,
                "ultima_venta": None  # TODO: Agregar query de última venta
            }
            for p in productos
        ]
    }


@router.get("/estadisticas")
async def obtener_estadisticas_inventario(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
):
    """
    Estadísticas generales del inventario
    
    Incluye:
    - Total de productos activos
    - Valor total de inventario
    - Productos sin stock
    - Productos con stock bajo
    """
    # Total de productos activos
    stmt_total = select(func.count(Producto.id)).where(
        and_(
            Producto.tienda_id == current_tienda.id,
            Producto.is_active == True
        )
    )
    result_total = await session.execute(stmt_total)
    total_productos = result_total.scalar()
    
    # Productos sin stock
    stmt_sin_stock = select(func.count(Producto.id)).where(
        and_(
            Producto.tienda_id == current_tienda.id,
            Producto.stock_actual == 0,
            Producto.is_active == True
        )
    )
    result_sin_stock = await session.execute(stmt_sin_stock)
    productos_sin_stock = result_sin_stock.scalar()
    
    # Productos con stock bajo (< 10)
    stmt_bajo_stock = select(func.count(Producto.id)).where(
        and_(
            Producto.tienda_id == current_tienda.id,
            Producto.stock_actual > 0,
            Producto.stock_actual < 10,
            Producto.is_active == True
        )
    )
    result_bajo_stock = await session.execute(stmt_bajo_stock)
    productos_bajo_stock = result_bajo_stock.scalar()
    
    # Valor total de inventario (a precio de costo)
    stmt_valor = select(
        func.sum(Producto.stock_actual * Producto.precio_costo)
    ).where(
        and_(
            Producto.tienda_id == current_tienda.id,
            Producto.is_active == True
        )
    )
    result_valor = await session.execute(stmt_valor)
    valor_inventario = result_valor.scalar() or 0
    
    # Valor total a precio de venta
    stmt_valor_venta = select(
        func.sum(Producto.stock_actual * Producto.precio_venta)
    ).where(
        and_(
            Producto.tienda_id == current_tienda.id,
            Producto.is_active == True
        )
    )
    result_valor_venta = await session.execute(stmt_valor_venta)
    valor_venta = result_valor_venta.scalar() or 0
    
    return {
        "total_productos": total_productos,
        "productos_sin_stock": productos_sin_stock,
        "productos_bajo_stock": productos_bajo_stock,
        "porcentaje_sin_stock": round((productos_sin_stock / total_productos * 100) if total_productos > 0 else 0, 2),
        "valor_inventario_costo": round(float(valor_inventario), 2),
        "valor_inventario_venta": round(float(valor_venta), 2),
        "utilidad_potencial": round(float(valor_venta - valor_inventario), 2)
    }
