"""
Rutas de Pagos - Nexus POS
Integración con Mercado Pago y gestión de webhooks
"""
import logging
from typing import Annotated, Dict, Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.core.db import get_session
from app.models import Venta, DetalleVenta
from app.services.payment_service import payment_service
from app.services.afip_service import afip_service
from app.api.deps import CurrentTienda
from datetime import datetime


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["Pagos"])


@router.post("/generate/{venta_id}")
async def generar_pago(
    venta_id: UUID,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> Dict[str, Any]:
    """
    Genera un link de pago o QR de Mercado Pago para una venta
    
    Flujo:
    1. Valida que la venta exista y pertenezca a la tienda
    2. Obtiene los detalles de la venta
    3. Crea una preferencia en Mercado Pago
    4. Retorna el link de pago y QR para mostrar al cliente
    
    Returns:
        preference_id: ID de la preferencia en MercadoPago
        init_point: URL para redirigir al cliente
        qr_code_url: URL del código QR (si está disponible)
    """
    try:
        # Validar que la venta existe y pertenece a la tienda
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
        
        # Validar que no esté ya pagada
        if venta.status_pago == "pagado":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Esta venta ya fue pagada"
            )
        
        if venta.status_pago == "anulado":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Esta venta fue anulada"
            )
        
        # Obtener detalles de la venta para MercadoPago
        statement_detalles = select(DetalleVenta).where(
            DetalleVenta.venta_id == venta_id
        )
        result_detalles = await session.execute(statement_detalles)
        detalles = result_detalles.scalars().all()
        
        # Preparar items en formato MercadoPago
        items_mp = []
        for detalle in detalles:
            items_mp.append({
                "title": f"Producto ID: {detalle.producto_id}",  # TODO: Cargar nombre real del producto
                "quantity": int(detalle.cantidad),
                "unit_price": float(detalle.precio_unitario),
                "currency_id": "ARS"
            })
        
        # Crear preferencia en MercadoPago
        logger.info(f"Generando preferencia de pago para venta {venta_id}")
        
        preference_data = payment_service.create_preference(
            venta_id=venta_id,
            total=venta.total,
            items=items_mp,
            external_reference=str(venta_id)
        )
        
        # Guardar preference_id en la venta (opcional)
        # venta.payment_id = preference_data["preference_id"]
        # session.add(venta)
        # await session.commit()
        
        return {
            "venta_id": str(venta_id),
            "preference_id": preference_data["preference_id"],
            "init_point": preference_data["init_point"],
            "sandbox_init_point": preference_data.get("sandbox_init_point"),
            "qr_code_url": preference_data.get("qr_code_url"),
            "total": venta.total,
            "mensaje": "Link de pago generado exitosamente"
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error al generar pago para venta {venta_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar el pago: {str(e)}"
        )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def webhook_mercadopago(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    x_signature: Optional[str] = Header(None),
    x_request_id: Optional[str] = Header(None)
) -> Dict[str, str]:
    """
    Webhook para recibir notificaciones de Mercado Pago
    
    IMPORTANTE: Este endpoint debe responder 200 OK rápidamente
    para evitar reintentos infinitos de MercadoPago
    
    Tipos de notificación:
    - payment: Pago procesado
    - merchant_order: Orden actualizada
    
    Flujo:
    1. Recibe notificación de MercadoPago
    2. Valida firma (opcional pero recomendado)
    3. Consulta el estado del pago
    4. Actualiza la venta en base de datos
    5. Emite factura AFIP si corresponde
    6. Responde 200 OK inmediatamente
    
    Documentación:
    https://www.mercadopago.com.ar/developers/es/docs/your-integrations/notifications/webhooks
    """
    try:
        # Obtener datos del webhook
        webhook_data = await request.json()
        
        logger.info(f"Webhook recibido de MercadoPago: {webhook_data}")
        logger.info(f"X-Signature: {x_signature}")
        logger.info(f"X-Request-ID: {x_request_id}")
        
        # Validar firma (si está configurado)
        if x_signature and not payment_service.validate_webhook_signature(webhook_data, x_signature):
            logger.warning("Firma del webhook inválida")
            # Aún así respondemos 200 para no bloquear MercadoPago
            return {"status": "received", "warning": "invalid_signature"}
        
        # Extraer información del webhook
        notification_type = webhook_data.get("type")
        
        if notification_type == "payment":
            # Webhook de pago
            payment_id = webhook_data.get("data", {}).get("id")
            
            if not payment_id:
                logger.warning("Webhook sin payment_id")
                return {"status": "received", "warning": "no_payment_id"}
            
            # Consultar información completa del pago
            logger.info(f"Consultando información de pago: {payment_id}")
            payment_info = payment_service.get_payment_info(str(payment_id))
            
            # Extraer datos relevantes
            status_pago_mp = payment_info.get("status")
            external_reference = payment_info.get("external_reference")
            
            logger.info(f"Estado del pago: {status_pago_mp}")
            logger.info(f"Referencia externa (venta_id): {external_reference}")
            
            # Solo procesar si está aprobado
            if status_pago_mp == "approved" and external_reference:
                try:
                    venta_id = UUID(external_reference)
                    
                    # Buscar la venta
                    statement = select(Venta).where(Venta.id == venta_id)
                    result = await session.execute(statement)
                    venta = result.scalar_one_or_none()
                    
                    if venta:
                        # Actualizar estado de pago
                        venta.status_pago = "pagado"
                        venta.payment_id = str(payment_id)
                        
                        session.add(venta)
                        await session.commit()
                        
                        logger.info(f"Venta {venta_id} marcada como pagada")
                        
                        # TODO: Emitir factura AFIP automáticamente (opcional)
                        try:
                            factura_data = afip_service.emitir_factura(
                                venta_id=venta_id,
                                cuit_cliente=None,  # TODO: Obtener del cliente
                                monto=venta.total
                            )
                            
                            if factura_data.get("cae"):
                                venta.afip_cae = factura_data["cae"]
                                venta.afip_cae_vto = datetime.strptime(factura_data["vto"], "%Y-%m-%d")
                                session.add(venta)
                                await session.commit()
                                
                                logger.info(f"Factura AFIP emitida: CAE {factura_data['cae']}")
                        
                        except Exception as afip_error:
                            logger.error(f"Error al emitir factura AFIP: {str(afip_error)}")
                            # No bloqueamos el webhook por error de facturación
                    
                    else:
                        logger.warning(f"Venta {venta_id} no encontrada")
                
                except ValueError:
                    logger.error(f"External reference inválido: {external_reference}")
        
        elif notification_type == "merchant_order":
            logger.info("Notificación de merchant_order recibida (no procesada)")
        
        # SIEMPRE responder 200 OK para que MercadoPago no reintente
        return {"status": "received", "message": "Webhook procesado"}
    
    except Exception as e:
        logger.error(f"Error procesando webhook: {str(e)}", exc_info=True)
        
        # Incluso con error, responder 200 para evitar reintentos
        return {"status": "error", "message": str(e)}


@router.get("/status/{venta_id}")
async def consultar_estado_pago(
    venta_id: UUID,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)]
) -> Dict[str, Any]:
    """
    Consulta el estado de pago de una venta
    
    Útil para polling desde el frontend mientras espera la confirmación
    """
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
    
    return {
        "venta_id": str(venta_id),
        "status_pago": venta.status_pago,
        "payment_id": venta.payment_id,
        "total": venta.total,
        "afip_cae": venta.afip_cae,
        "afip_cae_vto": venta.afip_cae_vto.isoformat() if venta.afip_cae_vto else None
    }


@router.post("/facturar/{venta_id}")
async def emitir_factura_manual(
    venta_id: UUID,
    current_tienda: CurrentTienda,
    session: Annotated[AsyncSession, Depends(get_session)],
    cuit_cliente: Optional[str] = None
) -> Dict[str, Any]:
    """
    Emite una factura AFIP manualmente para una venta
    
    Útil cuando se necesita facturar después del pago
    o para ventas en efectivo
    """
    try:
        # Buscar venta
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
        
        # Validar que no tenga factura
        if venta.afip_cae:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Esta venta ya tiene factura (CAE: {venta.afip_cae})"
            )
        
        # Emitir factura
        logger.info(f"Emitiendo factura manual para venta {venta_id}")
        
        factura_data = afip_service.emitir_factura(
            venta_id=venta_id,
            cuit_cliente=cuit_cliente,
            monto=venta.total,
            tipo_comprobante="FACTURA_B" if not cuit_cliente else "FACTURA_A"
        )
        
        # Guardar CAE
        venta.afip_cae = factura_data["cae"]
        venta.afip_cae_vto = datetime.strptime(factura_data["vto"], "%Y-%m-%d")
        
        session.add(venta)
        await session.commit()
        
        logger.info(f"Factura emitida: CAE {factura_data['cae']}")
        
        return {
            "venta_id": str(venta_id),
            "cae": factura_data["cae"],
            "vto": factura_data["vto"],
            "numero_comprobante": factura_data.get("numero_comprobante"),
            "tipo_comprobante": factura_data.get("tipo_comprobante"),
            "mock": factura_data.get("mock", False),
            "mensaje": factura_data.get("mensaje", "Factura emitida exitosamente")
        }
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error al emitir factura: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al emitir la factura: {str(e)}"
        )
