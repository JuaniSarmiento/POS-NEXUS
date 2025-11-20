"""
Rutas de Insights - Nexus POS
Dashboard de alertas y recomendaciones inteligentes
"""
import logging
from typing import Annotated, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlmodel import col
from app.core.db import get_session
from app.models import Insight
from app.services.insight_service import insight_service
from app.api.deps import CurrentTienda
from pydantic import BaseModel
from datetime import datetime


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/insights", tags=["Insights & Alertas"])


# ==================== SCHEMAS ====================

class InsightRead(BaseModel):
    """Schema de lectura para un Insight"""
    id: UUID
    tipo: str
    mensaje: str
    nivel_urgencia: str
    is_active: bool
    metadata: dict
    created_at: datetime
    
    class Config:
        from_attributes = True


class InsightRefreshResponse(BaseModel):
    """Respuesta del endpoint de refresh"""
    mensaje: str
    insights_generados: dict
    total: int


# ==================== ENDPOINTS ====================

@router.get("/", response_model=List[InsightRead])
async def listar_insights(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    activos_solo: bool = Query(True, description="Mostrar solo insights activos"),
    nivel_urgencia: str = Query(None, description="Filtrar por urgencia: BAJA, MEDIA, ALTA, CRITICA"),
    tipo: str = Query(None, description="Filtrar por tipo: STOCK_BAJO, VENTAS_DIARIAS, etc."),
    limit: int = Query(50, ge=1, le=200)
) -> List[InsightRead]:
    """
    Lista los insights de la tienda ordenados por urgencia y fecha
    
    Ordenamiento:
    1. Por urgencia (CRITICA > ALTA > MEDIA > BAJA)
    2. Por fecha de creación (más recientes primero)
    
    Filtros:
    - activos_solo: Mostrar solo activos (por defecto True)
    - nivel_urgencia: Filtrar por nivel específico
    - tipo: Filtrar por tipo específico
    """
    # Construir query base
    statement = select(Insight).where(Insight.tienda_id == current_tienda.id)
    
    # Filtro de activos
    if activos_solo:
        statement = statement.where(Insight.is_active == True)
    
    # Filtro por nivel de urgencia
    if nivel_urgencia:
        statement = statement.where(Insight.nivel_urgencia == nivel_urgencia.upper())
    
    # Filtro por tipo
    if tipo:
        statement = statement.where(Insight.tipo == tipo.upper())
    
    # Ordenamiento personalizado por urgencia
    urgencia_order = {
        'CRITICA': 1,
        'ALTA': 2,
        'MEDIA': 3,
        'BAJA': 4
    }
    
    # Ejecutar query
    statement = statement.limit(limit)
    result = await session.execute(statement)
    insights = result.scalars().all()
    
    # Ordenar en Python por urgencia y fecha
    insights_sorted = sorted(
        insights,
        key=lambda x: (urgencia_order.get(x.nivel_urgencia, 5), -x.created_at.timestamp())
    )
    
    logger.info(f"Listados {len(insights_sorted)} insights para tienda {current_tienda.id}")
    
    return [InsightRead.model_validate(insight) for insight in insights_sorted]


@router.post("/{insight_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def archivar_insight(
    insight_id: UUID,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> None:
    """
    Archiva un insight (marca como inactivo)
    
    Útil cuando el usuario ya vio la alerta o tomó acción
    
    Validaciones:
    - El insight debe pertenecer a la tienda actual
    - Multi-Tenant security
    """
    # Buscar el insight con validación Multi-Tenant
    statement = select(Insight).where(
        and_(
            Insight.id == insight_id,
            Insight.tienda_id == current_tienda.id
        )
    )
    
    result = await session.execute(statement)
    insight = result.scalar_one_or_none()
    
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight no encontrado"
        )
    
    # Marcar como inactivo
    insight.is_active = False
    session.add(insight)
    await session.commit()
    
    logger.info(f"Insight {insight_id} archivado por usuario de tienda {current_tienda.id}")


@router.post("/refresh", response_model=InsightRefreshResponse)
async def refrescar_insights(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    force: bool = Query(False, description="Forzar generación aunque ya existan alertas recientes")
) -> InsightRefreshResponse:
    """
    Endpoint para forzar la generación de insights manualmente
    
    Útil para:
    - Demos y pruebas
    - Refresh manual desde el dashboard
    - Testing de la lógica de insights
    
    Args:
        force: Si es True, genera insights aunque ya existan recientes
               (útil para testing, pero puede crear duplicados)
    
    Returns:
        Resumen de insights generados
    """
    logger.info(f"Refrescando insights manualmente para tienda {current_tienda.id}")
    
    try:
        # Si force=True, archivar insights antiguos para evitar duplicados
        if force:
            statement = select(Insight).where(
                and_(
                    Insight.tienda_id == current_tienda.id,
                    Insight.is_active == True
                )
            )
            result = await session.execute(statement)
            insights_antiguos = result.scalars().all()
            
            for insight in insights_antiguos:
                insight.is_active = False
                session.add(insight)
            
            await session.commit()
            logger.info(f"Archivados {len(insights_antiguos)} insights antiguos (force=True)")
        
        # Generar todos los insights
        resultado = await insight_service.generate_all_insights(
            tienda_id=current_tienda.id,
            session=session
        )
        
        return InsightRefreshResponse(
            mensaje="Insights actualizados exitosamente",
            insights_generados=resultado,
            total=resultado["total"]
        )
    
    except Exception as e:
        logger.error(f"Error al refrescar insights: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar insights: {str(e)}"
        )


@router.post("/background-refresh", status_code=status.HTTP_202_ACCEPTED)
async def refrescar_insights_background(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    background_tasks: BackgroundTasks
) -> dict:
    """
    Genera insights en segundo plano usando FastAPI BackgroundTasks
    
    Retorna inmediatamente 202 Accepted mientras procesa en background
    
    Ideal para no bloquear la respuesta del API cuando hay muchos datos
    """
    async def generar_insights_task():
        """Tarea en segundo plano"""
        logger.info(f"Iniciando generación de insights en background para tienda {current_tienda.id}")
        try:
            resultado = await insight_service.generate_all_insights(
                tienda_id=current_tienda.id,
                session=session
            )
            logger.info(f"Insights generados en background: {resultado}")
        except Exception as e:
            logger.error(f"Error en tarea de background: {str(e)}", exc_info=True)
    
    # Agregar tarea al background
    background_tasks.add_task(generar_insights_task)
    
    return {
        "mensaje": "Generación de insights iniciada en segundo plano",
        "status": "processing"
    }


@router.get("/stats")
async def estadisticas_insights(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> dict:
    """
    Obtiene estadísticas de insights de la tienda
    
    Returns:
        Contadores por tipo, urgencia y estado
    """
    from sqlalchemy import func
    
    # Query de contadores
    statement = select(
        Insight.tipo,
        Insight.nivel_urgencia,
        Insight.is_active,
        func.count(Insight.id).label('count')
    ).where(
        Insight.tienda_id == current_tienda.id
    ).group_by(
        Insight.tipo,
        Insight.nivel_urgencia,
        Insight.is_active
    )
    
    result = await session.execute(statement)
    rows = result.all()
    
    # Procesar resultados
    stats = {
        "por_tipo": {},
        "por_urgencia": {},
        "activos": 0,
        "archivados": 0,
        "total": 0
    }
    
    for row in rows:
        tipo, urgencia, activo, count = row
        
        # Por tipo
        stats["por_tipo"][tipo] = stats["por_tipo"].get(tipo, 0) + count
        
        # Por urgencia
        stats["por_urgencia"][urgencia] = stats["por_urgencia"].get(urgencia, 0) + count
        
        # Por estado
        if activo:
            stats["activos"] += count
        else:
            stats["archivados"] += count
        
        stats["total"] += count
    
    return stats


@router.delete("/clear-all", status_code=status.HTTP_204_NO_CONTENT)
async def limpiar_insights(
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    solo_archivados: bool = Query(False, description="Eliminar solo los archivados")
) -> None:
    """
    Limpia insights de la tienda
    
    Args:
        solo_archivados: Si es True, solo elimina los archivados
                        Si es False, elimina TODOS (usar con cuidado)
    
    ATENCIÓN: Esta operación es irreversible
    """
    statement = select(Insight).where(Insight.tienda_id == current_tienda.id)
    
    if solo_archivados:
        statement = statement.where(Insight.is_active == False)
    
    result = await session.execute(statement)
    insights = result.scalars().all()
    
    for insight in insights:
        await session.delete(insight)
    
    await session.commit()
    
    logger.warning(
        f"Eliminados {len(insights)} insights de tienda {current_tienda.id} "
        f"({'solo archivados' if solo_archivados else 'TODOS'})"
    )
