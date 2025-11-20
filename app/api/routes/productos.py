"""
Rutas de Productos - Nexus POS
CRUD completo con filtrado Multi-Tenant y polimorfismo
"""
from typing import Annotated, Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, col, and_, or_, func
from app.core.db import get_session
from app.core.cache import invalidate_cache
import logging
from app.models import Producto, Tienda
from app.schemas_models.productos import (
    ProductoCreate,
    ProductoUpdate,
    ProductoRead,
    ProductoReadWithCalculatedStock
)
from app.api.deps import CurrentTienda


router = APIRouter(prefix="/productos", tags=["Productos"])
logger = logging.getLogger(__name__)


def calcular_stock_ropa(producto: Producto) -> float:
    """
    Calcula el stock total de un producto tipo ropa
    sumando el stock de todas sus variantes
    """
    if producto.tipo != 'ropa':
        return producto.stock_actual
    
    variantes = producto.atributos.get('variantes', [])
    stock_total = sum(variante.get('stock', 0) for variante in variantes)
    return float(stock_total)


@router.post("/", response_model=ProductoRead, status_code=status.HTTP_201_CREATED)
async def crear_producto(
    producto_data: ProductoCreate,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> Producto:
    """
    Crea un nuevo producto para la tienda actual
    
    - Asigna automáticamente el tienda_id de la tienda actual
    - Para productos tipo 'ropa', calcula el stock_actual desde las variantes
    - Valida que el SKU no esté duplicado en la tienda
    """
    # Validar SKU único dentro de la tienda
    statement = select(Producto).where(
        Producto.tienda_id == current_tienda.id,
        Producto.sku == producto_data.sku
    )
    result = await session.execute(statement)
    existing_producto = result.scalar_one_or_none()
    
    if existing_producto is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un producto con SKU '{producto_data.sku}' en esta tienda"
        )
    
    # Crear producto
    producto_dict = producto_data.model_dump()
    producto_dict['tienda_id'] = current_tienda.id
    
    # Calcular stock automáticamente para productos tipo ropa
    if producto_data.tipo == 'ropa':
        variantes = producto_data.atributos.get('variantes', [])
        stock_total = sum(variante.get('stock', 0) for variante in variantes)
        producto_dict['stock_actual'] = float(stock_total)
    
    nuevo_producto = Producto(**producto_dict)
    
    session.add(nuevo_producto)
    await session.commit()
    await session.refresh(nuevo_producto)
    
    # Invalidar caché
    invalidate_cache(f"productos:{current_tienda.id}")
    logger.info(f"Producto creado: {nuevo_producto.id} - {nuevo_producto.nombre}")
    
    return nuevo_producto


@router.get("/buscar")
async def buscar_productos_avanzado(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    q: Optional[str] = Query(None, description="Búsqueda por nombre o SKU"),
    tipo: Optional[str] = Query(None, description="Filtrar por tipo"),
    precio_min: Optional[float] = Query(None, ge=0),
    precio_max: Optional[float] = Query(None, ge=0),
    stock_min: Optional[float] = Query(None, ge=0),
    solo_activos: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
) -> dict:
    """
    Búsqueda avanzada de productos con múltiples filtros
    
    Filtros disponibles:
    - q: Búsqueda por nombre o SKU (case-insensitive)
    - tipo: Filtrar por tipo de producto
    - precio_min/max: Rango de precios
    - stock_min: Stock mínimo
    - solo_activos: Solo productos activos
    
    Retorna: items, total, paginación
    """
    conditions = [Producto.tienda_id == current_tienda.id]
    
    if solo_activos:
        conditions.append(Producto.is_active == True)
    
    if q:
        search_pattern = f"%{q.lower()}%"
        conditions.append(
            or_(
                col(Producto.nombre).ilike(search_pattern),
                col(Producto.sku).ilike(search_pattern),
                col(Producto.descripcion).ilike(search_pattern)
            )
        )
    
    if tipo:
        conditions.append(Producto.tipo == tipo)
    
    if precio_min is not None:
        conditions.append(Producto.precio_venta >= precio_min)
    
    if precio_max is not None:
        conditions.append(Producto.precio_venta <= precio_max)
    
    if stock_min is not None:
        conditions.append(Producto.stock_actual >= stock_min)
    
    stmt = select(Producto).where(and_(*conditions)).offset(skip).limit(limit)
    result = await session.execute(stmt)
    productos = result.scalars().all()
    
    # Contar total para paginación
    count_stmt = select(func.count(Producto.id)).where(and_(*conditions))
    count_result = await session.execute(count_stmt)
    total = count_result.scalar()
    if total is None:
        total = 0
    
    # Procesar productos con stock calculado
    productos_response = []
    for producto in productos:
        producto_dict = ProductoReadWithCalculatedStock.model_validate(producto).model_dump()
        if producto.tipo == 'ropa':
            producto_dict['stock_calculado'] = calcular_stock_ropa(producto)
        productos_response.append(producto_dict)
    
    return {
        "items": productos_response,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + limit) < total
    }


@router.get("/", response_model=List[ProductoReadWithCalculatedStock])
async def listar_productos(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None, description="Buscar por SKU o nombre"),
    tipo: Optional[str] = Query(None, pattern="^(general|ropa|pesable)$"),
    is_active: Optional[bool] = None
) -> List[ProductoReadWithCalculatedStock]:
    """
    Lista productos de la tienda actual con filtros opcionales
    
    Filtros:
    - search: Busca por SKU o nombre (case-insensitive)
    - tipo: Filtra por tipo de producto
    - is_active: Filtra por productos activos/inactivos
    """
    # Base query con filtro Multi-Tenant
    statement = select(Producto).where(Producto.tienda_id == current_tienda.id)
    
    # Aplicar filtros opcionales
    if search:
        search_pattern = f"%{search}%"
        statement = statement.where(
            (col(Producto.sku).ilike(search_pattern)) |
            (col(Producto.nombre).ilike(search_pattern))
        )
    
    if tipo:
        statement = statement.where(Producto.tipo == tipo)
    
    if is_active is not None:
        statement = statement.where(Producto.is_active == is_active)
    
    # Paginación
    statement = statement.offset(skip).limit(limit)
    
    result = await session.execute(statement)
    productos = result.scalars().all()
    
    # Agregar stock calculado para productos tipo ropa
    productos_response = []
    for producto in productos:
        producto_dict = ProductoReadWithCalculatedStock.model_validate(producto).model_dump()
        
        if producto.tipo == 'ropa':
            producto_dict['stock_calculado'] = calcular_stock_ropa(producto)
        
        productos_response.append(ProductoReadWithCalculatedStock(**producto_dict))
    
    return productos_response


@router.get("/{producto_id}", response_model=ProductoReadWithCalculatedStock)
async def obtener_producto(
    producto_id: UUID,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> ProductoReadWithCalculatedStock:
    """
    Obtiene un producto específico por ID
    Valida que pertenezca a la tienda actual (Multi-Tenant)
    """
    statement = select(Producto).where(
        Producto.id == producto_id,
        Producto.tienda_id == current_tienda.id
    )
    result = await session.execute(statement)
    producto = result.scalar_one_or_none()
    
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )
    
    producto_dict = ProductoReadWithCalculatedStock.model_validate(producto).model_dump()
    
    if producto.tipo == 'ropa':
        producto_dict['stock_calculado'] = calcular_stock_ropa(producto)
    
    return ProductoReadWithCalculatedStock(**producto_dict)


@router.patch("/{producto_id}", response_model=ProductoRead)
async def actualizar_producto(
    producto_id: UUID,
    producto_update: ProductoUpdate,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> Producto:
    """
    Actualiza un producto existente
    
    - Solo actualiza los campos enviados (PATCH parcial)
    - Para productos tipo ropa, recalcula el stock si se actualizan las variantes
    - Valida pertenencia a la tienda actual
    """
    # Buscar producto
    statement = select(Producto).where(
        Producto.id == producto_id,
        Producto.tienda_id == current_tienda.id
    )
    result = await session.execute(statement)
    producto = result.scalar_one_or_none()
    
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )
    
    # Validar SKU único si se está actualizando
    if producto_update.sku and producto_update.sku != producto.sku:
        statement = select(Producto).where(
            Producto.tienda_id == current_tienda.id,
            Producto.sku == producto_update.sku
        )
        sku_check_result = await session.execute(statement)
        existing_producto = sku_check_result.scalar_one_or_none()
        
        if existing_producto is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un producto con SKU '{producto_update.sku}' en esta tienda"
            )
    
    # Actualizar campos
    update_data = producto_update.model_dump(exclude_unset=True)
    
    # Recalcular stock para productos tipo ropa si se actualizan atributos
    if 'atributos' in update_data and producto.tipo == 'ropa':
        variantes = update_data['atributos'].get('variantes', [])
        stock_total = sum(variante.get('stock', 0) for variante in variantes)
        update_data['stock_actual'] = float(stock_total)
    
    for key, value in update_data.items():
        setattr(producto, key, value)
    
    session.add(producto)
    await session.commit()
    await session.refresh(producto)
    
    return producto


@router.delete("/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_producto(
    producto_id: UUID,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> None:
    """
    Elimina un producto (soft delete: marca como inactivo)
    Validaciones Multi-Tenant aplicadas
    """
    statement = select(Producto).where(
        Producto.id == producto_id,
        Producto.tienda_id == current_tienda.id
    )
    result = await session.execute(statement)
    producto = result.scalar_one_or_none()
    
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado"
        )
    
    # Soft delete
    producto.is_active = False
    session.add(producto)
    await session.commit()


@router.get("/sku/{sku}", response_model=ProductoReadWithCalculatedStock)
async def buscar_por_sku(
    sku: str,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> ProductoReadWithCalculatedStock:
    """
    Busca un producto por SKU dentro de la tienda actual
    Útil para sistemas de punto de venta con escáner de códigos
    """
    statement = select(Producto).where(
        Producto.sku == sku,
        Producto.tienda_id == current_tienda.id,
        Producto.is_active == True
    )
    result = await session.execute(statement)
    producto = result.scalar_one_or_none()
    
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró un producto con SKU '{sku}'"
        )
    
    producto_dict = ProductoReadWithCalculatedStock.model_validate(producto).model_dump()
    
    if producto.tipo == 'ropa':
        producto_dict['stock_calculado'] = calcular_stock_ropa(producto)
    
    return ProductoReadWithCalculatedStock(**producto_dict)
