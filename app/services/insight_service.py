"""
Servicio de Insights - Nexus POS
Motor de análisis y generación de alertas inteligentes
"""
import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlmodel import col
from app.models import Insight, Producto, Venta


logger = logging.getLogger(__name__)


class InsightService:
    """
    Servicio para generar insights automáticos basados en datos de la tienda
    
    Tipos de insights implementados:
    - STOCK_BAJO: Alertas de productos con poco stock
    - VENTAS_DIARIAS: Resumen de ventas del día
    - PRODUCTO_SIN_STOCK: Productos agotados
    - VENTAS_SEMANALES: Resumen semanal
    """
    
    # Configuración de umbrales
    STOCK_UMBRAL_BAJO = 10
    STOCK_UMBRAL_CRITICO = 3
    
    async def generate_stock_alerts(
        self,
        tienda_id: UUID,
        session: AsyncSession,
        umbral: Optional[int] = None
    ) -> List[Insight]:
        """
        Genera alertas de stock bajo para productos de la tienda
        
        Args:
            tienda_id: ID de la tienda
            session: Sesión de base de datos
            umbral: Umbral personalizado (por defecto usa STOCK_UMBRAL_BAJO)
        
        Returns:
            Lista de insights creados
        
        Lógica anti-duplicación:
        - Verifica si ya existe una alerta activa para el mismo producto
        - Solo crea si no hay alerta previa
        """
        umbral_stock = umbral or self.STOCK_UMBRAL_BAJO
        insights_creados = []
        
        logger.info(f"Generando alertas de stock para tienda {tienda_id}")
        
        # Buscar productos con stock bajo
        statement = select(Producto).where(
            and_(
                Producto.tienda_id == tienda_id,
                Producto.stock_actual <= umbral_stock,
                Producto.is_active == True
            )
        )
        
        result = await session.execute(statement)
        productos_bajo_stock = result.scalars().all()
        
        logger.info(f"Encontrados {len(productos_bajo_stock)} productos con stock bajo")
        
        for producto in productos_bajo_stock:
            # Verificar si ya existe una alerta activa para este producto
            existing_alert = await self._check_existing_insight(
                session=session,
                tienda_id=tienda_id,
                tipo="STOCK_BAJO",
                producto_id=producto.id
            )
            
            if existing_alert:
                logger.debug(f"Alerta de stock ya existe para producto {producto.nombre}")
                continue
            
            # Determinar nivel de urgencia
            if producto.stock_actual <= self.STOCK_UMBRAL_CRITICO:
                urgencia = "CRITICA"
                emoji = "🚨"
            elif producto.stock_actual <= umbral_stock / 2:
                urgencia = "ALTA"
                emoji = "⚠️"
            else:
                urgencia = "MEDIA"
                emoji = "📊"
            
            # Crear insight
            mensaje = (
                f"{emoji} Te quedan pocas unidades de '{producto.nombre}' (SKU: {producto.sku}). "
                f"Stock actual: {int(producto.stock_actual)} unidades. ¡Reponé pronto!"
            )
            
            nuevo_insight = Insight(
                tienda_id=tienda_id,
                tipo="STOCK_BAJO",
                mensaje=mensaje,
                nivel_urgencia=urgencia,
                extra_data={
                    "producto_id": str(producto.id),
                    "producto_nombre": producto.nombre,
                    "producto_sku": producto.sku,
                    "stock_actual": producto.stock_actual,
                    "umbral": umbral_stock
                }
            )
            
            session.add(nuevo_insight)
            insights_creados.append(nuevo_insight)
            
            logger.info(f"Creada alerta de stock para {producto.nombre} (Urgencia: {urgencia})")
        
        if insights_creados:
            await session.commit()
        
        return insights_creados
    
    async def generate_sales_summary(
        self,
        tienda_id: UUID,
        session: AsyncSession,
        horas: int = 24
    ) -> Optional[Insight]:
        """
        Genera un resumen de ventas de las últimas N horas
        
        Args:
            tienda_id: ID de la tienda
            session: Sesión de base de datos
            horas: Ventana de tiempo en horas (por defecto 24)
        
        Returns:
            Insight creado o None si no hay ventas
        """
        logger.info(f"Generando resumen de ventas de últimas {horas}h para tienda {tienda_id}")
        
        # Calcular fecha límite
        fecha_desde = datetime.utcnow() - timedelta(hours=horas)
        
        # Consulta agregada: total vendido y cantidad de ventas
        statement = select(
            func.sum(Venta.total).label('total_vendido'),
            func.count(Venta.id).label('cantidad_ventas')
        ).where(
            and_(
                Venta.tienda_id == tienda_id,
                Venta.fecha >= fecha_desde,
                Venta.status_pago == 'pagado'  # Solo ventas confirmadas
            )
        )
        
        result = await session.execute(statement)
        row = result.first()
        
        total_vendido = row.total_vendido or 0
        cantidad_ventas = row.cantidad_ventas or 0
        
        logger.info(f"Total vendido: ${total_vendido}, Cantidad: {cantidad_ventas}")
        
        # Si no hay ventas, no crear insight
        if cantidad_ventas == 0:
            logger.info("No hay ventas en el período")
            return None
        
        # Verificar si ya existe un resumen activo reciente (últimas 6 horas)
        existing_summary = await self._check_existing_insight(
            session=session,
            tienda_id=tienda_id,
            tipo="VENTAS_DIARIAS",
            hours_back=6
        )
        
        if existing_summary:
            logger.debug("Ya existe un resumen de ventas reciente")
            return None
        
        # Determinar nivel de urgencia y mensaje según el monto
        if total_vendido >= 50000:
            urgencia = "BAJA"
            emoji = "🎉"
            mensaje_extra = "¡Día espectacular!"
        elif total_vendido >= 20000:
            urgencia = "BAJA"
            emoji = "😊"
            mensaje_extra = "¡Excelente día!"
        elif total_vendido >= 5000:
            urgencia = "BAJA"
            emoji = "👍"
            mensaje_extra = "Buen día de ventas."
        else:
            urgencia = "BAJA"
            emoji = "📈"
            mensaje_extra = "Ventas registradas."
        
        # Formatear mensaje
        periodo = "Hoy" if horas == 24 else f"Últimas {horas}h"
        mensaje = (
            f"{emoji} {mensaje_extra} {periodo} facturaste ${total_vendido:,.2f} "
            f"en {cantidad_ventas} {'venta' if cantidad_ventas == 1 else 'ventas'}."
        )
        
        # Crear insight
        nuevo_insight = Insight(
            tienda_id=tienda_id,
            tipo="VENTAS_DIARIAS",
            mensaje=mensaje,
            nivel_urgencia=urgencia,
            extra_data={
                "total_vendido": float(total_vendido),
                "cantidad_ventas": cantidad_ventas,
                "periodo_horas": horas,
                "fecha_desde": fecha_desde.isoformat()
            }
        )
        
        session.add(nuevo_insight)
        await session.commit()
        
        logger.info(f"Creado resumen de ventas: ${total_vendido}")
        
        return nuevo_insight
    
    async def generate_out_of_stock_alerts(
        self,
        tienda_id: UUID,
        session: AsyncSession
    ) -> List[Insight]:
        """
        Genera alertas para productos sin stock (stock_actual = 0)
        
        Nivel de urgencia: ALTA (más urgente que stock bajo)
        """
        logger.info(f"Generando alertas de productos sin stock para tienda {tienda_id}")
        
        insights_creados = []
        
        # Buscar productos sin stock
        statement = select(Producto).where(
            and_(
                Producto.tienda_id == tienda_id,
                Producto.stock_actual == 0,
                Producto.is_active == True
            )
        )
        
        result = await session.execute(statement)
        productos_sin_stock = result.scalars().all()
        
        logger.info(f"Encontrados {len(productos_sin_stock)} productos sin stock")
        
        for producto in productos_sin_stock:
            # Verificar alerta existente
            existing_alert = await self._check_existing_insight(
                session=session,
                tienda_id=tienda_id,
                tipo="PRODUCTO_SIN_STOCK",
                producto_id=producto.id
            )
            
            if existing_alert:
                continue
            
            mensaje = (
                f"🔴 ¡'{producto.nombre}' (SKU: {producto.sku}) está AGOTADO! "
                f"Stock: 0 unidades. Reponé urgente para no perder ventas."
            )
            
            nuevo_insight = Insight(
                tienda_id=tienda_id,
                tipo="PRODUCTO_SIN_STOCK",
                mensaje=mensaje,
                nivel_urgencia="ALTA",
                extra_data={
                    "producto_id": str(producto.id),
                    "producto_nombre": producto.nombre,
                    "producto_sku": producto.sku
                }
            )
            
            session.add(nuevo_insight)
            insights_creados.append(nuevo_insight)
        
        if insights_creados:
            await session.commit()
        
        return insights_creados
    
    async def generate_all_insights(
        self,
        tienda_id: UUID,
        session: AsyncSession
    ) -> dict:
        """
        Genera todos los tipos de insights disponibles
        
        Returns:
            Diccionario con contadores de insights generados por tipo
        """
        logger.info(f"Generando todos los insights para tienda {tienda_id}")
        
        # Generar alertas de stock
        stock_alerts = await self.generate_stock_alerts(tienda_id, session)
        
        # Generar alertas de productos sin stock
        out_of_stock = await self.generate_out_of_stock_alerts(tienda_id, session)
        
        # Generar resumen de ventas
        sales_summary = await self.generate_sales_summary(tienda_id, session)
        
        resultado = {
            "stock_bajo": len(stock_alerts),
            "sin_stock": len(out_of_stock),
            "ventas_diarias": 1 if sales_summary else 0,
            "total": len(stock_alerts) + len(out_of_stock) + (1 if sales_summary else 0)
        }
        
        logger.info(f"Insights generados: {resultado}")
        
        return resultado
    
    async def _check_existing_insight(
        self,
        session: AsyncSession,
        tienda_id: UUID,
        tipo: str,
        producto_id: Optional[UUID] = None,
        hours_back: int = 24
    ) -> Optional[Insight]:
        """
        Verifica si existe un insight activo del mismo tipo
        
        Args:
            session: Sesión de base de datos
            tienda_id: ID de la tienda
            tipo: Tipo de insight
            producto_id: ID del producto (opcional, para alertas de stock)
            hours_back: Ventana de tiempo para considerar (horas)
        
        Returns:
            Insight existente o None
        """
        fecha_limite = datetime.utcnow() - timedelta(hours=hours_back)
        
        statement = select(Insight).where(
            and_(
                Insight.tienda_id == tienda_id,
                Insight.tipo == tipo,
                Insight.is_active == True,
                Insight.created_at >= fecha_limite
            )
        )
        
        # Si es alerta de producto específico, filtrar por extra_data
        if producto_id:
            # Filtrar por producto_id en el JSON extra_data
            statement = statement.where(
                col(Insight.extra_data)["producto_id"].astext == str(producto_id)
            )
        
        result = await session.execute(statement)
        return result.scalar_one_or_none()


# Instancia singleton del servicio
insight_service = InsightService()
