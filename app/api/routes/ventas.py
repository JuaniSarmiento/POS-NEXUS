"""
Rutas de Ventas - Nexus POS
Motor de ventas con transacciones atómicas y optimización para POS
"""
from typing import Annotated, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlmodel import col
from app.core.db import get_session
from app.models import Producto, Venta, DetalleVenta
from app.schemas_models.ventas import (
    ProductoScanRead,
    VentaCreate,
    VentaRead,
    VentaListRead,
    VentaResumen,
    DetalleVentaRead
)
from app.api.deps import CurrentTienda


router = APIRouter(prefix="/ventas", tags=["Ventas"])


@router.get("/scan/{codigo}", response_model=ProductoScanRead)
async def scan_producto(
    codigo: str,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> ProductoScanRead:
    """
    ENDPOINT DE ESCANEO RÁPIDO
    
    Optimizado para lectores de código de barras en el punto de venta.
    
    - Busca producto por SKU en la tienda actual
    - Retorna solo datos esenciales para el frontend
    - Valida que el producto esté activo
    - Incluye indicador de disponibilidad de stock
    
    Performance: Query optimizada con índices en SKU y tienda_id
    """
    statement = select(Producto).where(
        Producto.sku == codigo,
        Producto.tienda_id == current_tienda.id,
        Producto.is_active == True
    )
    
    result = await session.execute(statement)
    producto = result.scalar_one_or_none()
    
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto con código '{codigo}' no encontrado o inactivo"
        )
    
    # Construir respuesta optimizada
    return ProductoScanRead(
        id=producto.id,
        nombre=producto.nombre,
        sku=producto.sku,
        precio_venta=producto.precio_venta,
        stock_actual=producto.stock_actual,
        tipo=producto.tipo,
        tiene_stock=producto.stock_actual > 0
    )


@router.post("/checkout", response_model=VentaResumen, status_code=status.HTTP_201_CREATED)
async def procesar_venta(
    venta_data: VentaCreate,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> VentaResumen:
    """
    ENDPOINT DE CHECKOUT - TRANSACCIÓN CRÍTICA
    
    Procesa una venta completa con garantías ACID:
    
    1. Inicia transacción de BD
    2. Bloquea productos con SELECT FOR UPDATE (previene race conditions)
    3. Valida stock suficiente para cada item
    4. Descuenta stock de los productos
    5. Crea registros de venta y detalles con snapshot de precios
    6. Calcula total en el servidor (nunca confiar en frontend)
    7. Commit atómico o rollback completo
    
    Race Condition Protection: SELECT FOR UPDATE bloquea las filas hasta commit
    """
    try:
        # Variables para acumular datos
        total_venta = 0.0
        detalles_a_crear = []
        productos_a_actualizar = []
        
        # PASO 1: Validar y bloquear productos
        for item in venta_data.items:
            # SELECT FOR UPDATE: Bloquea la fila hasta el commit
            statement = select(Producto).where(
                Producto.id == item.producto_id,
                Producto.tienda_id == current_tienda.id
            ).with_for_update()
            
            result = await session.execute(statement)
            producto = result.scalar_one_or_none()
            
            # Validación 1: Producto existe y pertenece a la tienda
            if not producto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Producto con ID {item.producto_id} no encontrado en esta tienda"
                )
            
            # Validación 2: Producto activo
            if not producto.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El producto '{producto.nombre}' (SKU: {producto.sku}) está inactivo"
                )
            
            # Validación 3: Stock suficiente
            if producto.stock_actual < item.cantidad:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Stock insuficiente para '{producto.nombre}' (SKU: {producto.sku}). "
                        f"Disponible: {producto.stock_actual}, Solicitado: {item.cantidad}"
                    )
                )
            
            # Validación 4: Para productos tipo "pesable", permitir decimales
            if producto.tipo != 'pesable' and item.cantidad != int(item.cantidad):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El producto '{producto.nombre}' no permite cantidades decimales"
                )
            
            # PASO 2: Calcular subtotal y preparar descuento de stock
            subtotal = producto.precio_venta * item.cantidad
            total_venta += subtotal
            
            # Descontar stock (actualización diferida)
            producto.stock_actual -= item.cantidad
            productos_a_actualizar.append(producto)
            
            # Preparar detalle de venta con snapshot de precio
            detalles_a_crear.append({
                'producto_id': producto.id,
                'producto_nombre': producto.nombre,
                'producto_sku': producto.sku,
                'cantidad': item.cantidad,
                'precio_unitario': producto.precio_venta,  # Snapshot del precio actual
                'subtotal': subtotal
            })
        
        # PASO 3: Crear la venta (cabecera)
        nueva_venta = Venta(
            tienda_id=current_tienda.id,
            total=total_venta,
            metodo_pago=venta_data.metodo_pago
        )
        
        session.add(nueva_venta)
        await session.flush()  # Obtener el ID de la venta sin hacer commit
        
        # PASO 4: Crear los detalles de venta
        for detalle_data in detalles_a_crear:
            detalle = DetalleVenta(
                venta_id=nueva_venta.id,
                producto_id=detalle_data['producto_id'],
                cantidad=detalle_data['cantidad'],
                precio_unitario=detalle_data['precio_unitario'],
                subtotal=detalle_data['subtotal']
            )
            session.add(detalle)
        
        # PASO 5: Actualizar stock de productos
        for producto in productos_a_actualizar:
            session.add(producto)
        
        # PASO 6: COMMIT ATÓMICO
        await session.commit()
        
        # Retornar resumen de la venta
        return VentaResumen(
            venta_id=nueva_venta.id,
            fecha=nueva_venta.fecha,
            total=nueva_venta.total,
            metodo_pago=nueva_venta.metodo_pago,
            cantidad_items=len(detalles_a_crear),
            mensaje="Venta procesada exitosamente"
        )
    
    except HTTPException:
        # Re-lanzar excepciones HTTP (ya son manejadas)
        await session.rollback()
        raise
    
    except Exception as e:
        # Rollback en caso de cualquier error inesperado
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar la venta: {str(e)}"
        )


@router.get("/", response_model=List[VentaListRead])
async def listar_ventas(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    fecha_desde: Optional[str] = Query(None, description="Formato: YYYY-MM-DD"),
    fecha_hasta: Optional[str] = Query(None, description="Formato: YYYY-MM-DD")
) -> List[VentaListRead]:
    """
    Lista ventas de la tienda actual con filtros opcionales
    
    - Filtro Multi-Tenant automático
    - Paginación
    - Filtro por rango de fechas
    - Sin detalles para optimizar performance en listados
    """
    from datetime import datetime
    
    # Base query con filtro Multi-Tenant
    statement = select(Venta).where(Venta.tienda_id == current_tienda.id)
    
    # Filtros de fecha
    if fecha_desde:
        try:
            fecha_desde_dt = datetime.strptime(fecha_desde, "%Y-%m-%d")
            statement = statement.where(Venta.fecha >= fecha_desde_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de fecha_desde inválido. Use YYYY-MM-DD"
            )
    
    if fecha_hasta:
        try:
            fecha_hasta_dt = datetime.strptime(fecha_hasta, "%Y-%m-%d")
            statement = statement.where(Venta.fecha <= fecha_hasta_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de fecha_hasta inválido. Use YYYY-MM-DD"
            )
    
    # Ordenar por fecha descendente
    statement = statement.order_by(Venta.fecha.desc())
    
    # Paginación
    statement = statement.offset(skip).limit(limit)
    
    result = await session.execute(statement)
    ventas = result.scalars().all()
    
    # Construir respuesta con conteo de items
    ventas_response = []
    for venta in ventas:
        # Contar detalles sin cargarlos
        count_statement = select(DetalleVenta).where(DetalleVenta.venta_id == venta.id)
        count_result = await session.execute(count_statement)
        cantidad_items = len(count_result.scalars().all())
        
        ventas_response.append(VentaListRead(
            id=venta.id,
            fecha=venta.fecha,
            total=venta.total,
            metodo_pago=venta.metodo_pago,
            created_at=venta.created_at,
            cantidad_items=cantidad_items
        ))
    
    return ventas_response


@router.get("/{venta_id}", response_model=VentaRead)
async def obtener_venta(
    venta_id: UUID,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> VentaRead:
    """
    Obtiene una venta específica con todos sus detalles
    Incluye información expandida de los productos
    """
    # Buscar venta con validación Multi-Tenant
    statement = select(Venta).where(
        Venta.id == venta_id,
        Venta.tienda_id == current_tienda.id
    )
    result = await session.execute(statement)
    venta = result.scalar_one_or_none()
    
    if not venta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada"
        )
    
    # Cargar detalles con información de productos
    statement_detalles = select(DetalleVenta, Producto).where(
        DetalleVenta.venta_id == venta_id
    ).join(Producto, DetalleVenta.producto_id == Producto.id)
    
    result_detalles = await session.execute(statement_detalles)
    detalles_raw = result_detalles.all()
    
    # Construir detalles expandidos
    detalles = [
        DetalleVentaRead(
            id=detalle.id,
            producto_id=detalle.producto_id,
            producto_nombre=producto.nombre,
            producto_sku=producto.sku,
            cantidad=detalle.cantidad,
            precio_unitario=detalle.precio_unitario,
            subtotal=detalle.subtotal
        )
        for detalle, producto in detalles_raw
    ]
    
    return VentaRead(
        id=venta.id,
        fecha=venta.fecha,
        total=venta.total,
        metodo_pago=venta.metodo_pago,
        tienda_id=venta.tienda_id,
        detalles=detalles,
        created_at=venta.created_at
    )
