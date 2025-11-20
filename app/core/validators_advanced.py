"""
Validadores de Negocio Mejorados - Nexus POS
Validaciones críticas antes de operaciones importantes
"""
from typing import List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from fastapi import HTTPException, status

from app.models import Producto, Venta, DetalleVenta


class StockValidator:
    """Validador de stock para ventas"""
    
    @staticmethod
    async def validar_stock_disponible(
        session: AsyncSession,
        items: List[dict],
        tienda_id: UUID
    ) -> Tuple[bool, List[str]]:
        """
        Valida que hay stock suficiente para todos los items de una venta
        
        Returns:
            (es_valido, lista_de_errores)
        """
        errores = []
        
        for item in items:
            producto_id = item.get('producto_id')
            cantidad_solicitada = item.get('cantidad', 0)
            
            # Buscar producto
            stmt = select(Producto).where(
                Producto.id == producto_id,
                Producto.tienda_id == tienda_id
            )
            result = await session.execute(stmt)
            producto = result.scalar_one_or_none()
            
            if not producto:
                errores.append(f"Producto {producto_id} no encontrado")
                continue
            
            if not producto.is_active:
                errores.append(f"Producto '{producto.nombre}' está inactivo")
                continue
            
            # Validar stock
            if producto.tipo == 'ropa':
                # Para ropa, validar por variante
                variante_id = item.get('variante_id')
                if not variante_id:
                    errores.append(f"Producto '{producto.nombre}' requiere seleccionar variante (talle/color)")
                    continue
                
                variantes = producto.atributos.get('variantes', [])
                variante = next((v for v in variantes if v.get('id') == variante_id), None)
                
                if not variante:
                    errores.append(f"Variante {variante_id} no encontrada en producto '{producto.nombre}'")
                    continue
                
                stock_disponible = variante.get('stock', 0)
                if cantidad_solicitada > stock_disponible:
                    errores.append(
                        f"Stock insuficiente para '{producto.nombre}' variante {variante.get('talle')}/{variante.get('color')}. "
                        f"Disponible: {stock_disponible}, Solicitado: {cantidad_solicitada}"
                    )
            else:
                # Para productos generales y pesables
                if cantidad_solicitada > producto.stock_actual:
                    errores.append(
                        f"Stock insuficiente para '{producto.nombre}'. "
                        f"Disponible: {producto.stock_actual}, Solicitado: {cantidad_solicitada}"
                    )
        
        return (len(errores) == 0, errores)
    
    @staticmethod
    async def descontar_stock(
        session: AsyncSession,
        items: List[dict],
        tienda_id: UUID
    ):
        """
        Descuenta stock de productos después de una venta confirmada
        
        IMPORTANTE: Debe llamarse dentro de una transacción
        """
        for item in items:
            producto_id = item.get('producto_id')
            cantidad = item.get('cantidad', 0)
            
            stmt = select(Producto).where(
                Producto.id == producto_id,
                Producto.tienda_id == tienda_id
            )
            result = await session.execute(stmt)
            producto = result.scalar_one()
            
            if producto.tipo == 'ropa':
                # Descontar de variante específica
                variante_id = item.get('variante_id')
                variantes = producto.atributos.get('variantes', [])
                
                for variante in variantes:
                    if variante.get('id') == variante_id:
                        variante['stock'] = variante.get('stock', 0) - cantidad
                        break
                
                producto.atributos = dict(producto.atributos)  # Trigger SQLAlchemy update
            else:
                # Descontar de stock_actual
                producto.stock_actual -= cantidad
            
            session.add(producto)


class VentaValidator:
    """Validador de ventas"""
    
    @staticmethod
    def validar_totales(items: List[dict], total_declarado: float) -> Tuple[bool, str]:
        """
        Valida que el total de la venta coincida con la suma de items
        
        Returns:
            (es_valido, mensaje_error)
        """
        total_calculado = sum(
            item.get('cantidad', 0) * item.get('precio_unitario', 0)
            for item in items
        )
        
        # Permitir diferencia de 0.01 por redondeos
        diferencia = abs(total_calculado - total_declarado)
        
        if diferencia > 0.01:
            return (
                False,
                f"El total declarado (${total_declarado:.2f}) no coincide con la suma de items (${total_calculado:.2f})"
            )
        
        return (True, "")
    
    @staticmethod
    def validar_items_minimos(items: List[dict]) -> Tuple[bool, str]:
        """Valida que la venta tenga al menos un item"""
        if not items or len(items) == 0:
            return (False, "La venta debe tener al menos un item")
        
        return (True, "")
    
    @staticmethod
    def validar_precios_positivos(items: List[dict]) -> Tuple[bool, List[str]]:
        """Valida que todos los precios y cantidades sean positivos"""
        errores = []
        
        for idx, item in enumerate(items):
            cantidad = item.get('cantidad', 0)
            precio = item.get('precio_unitario', 0)
            
            if cantidad <= 0:
                errores.append(f"Item {idx + 1}: La cantidad debe ser mayor a 0")
            
            if precio < 0:
                errores.append(f"Item {idx + 1}: El precio no puede ser negativo")
        
        return (len(errores) == 0, errores)


async def validar_venta_completa(
    session: AsyncSession,
    items: List[dict],
    total: float,
    tienda_id: UUID
) -> None:
    """
    Ejecuta todas las validaciones de negocio para una venta
    
    Raises:
        HTTPException si alguna validación falla
    """
    # 1. Validar items mínimos
    valido, error = VentaValidator.validar_items_minimos(items)
    if not valido:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    
    # 2. Validar precios positivos
    valido, errores = VentaValidator.validar_precios_positivos(items)
    if not valido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Errores en precios/cantidades", "errors": errores}
        )
    
    # 3. Validar totales
    valido, error = VentaValidator.validar_totales(items, total)
    if not valido:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    
    # 4. Validar stock disponible
    valido, errores = await StockValidator.validar_stock_disponible(session, items, tienda_id)
    if not valido:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Stock insuficiente", "errors": errores}
        )
