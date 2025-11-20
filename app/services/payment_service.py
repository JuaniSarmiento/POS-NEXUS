"""
Servicio de Pagos - Nexus POS
Integración con Mercado Pago para procesamiento de pagos
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID
import mercadopago
from app.core.config import settings


logger = logging.getLogger(__name__)


class PaymentService:
    """
    Servicio para integración con Mercado Pago
    Gestiona creación de preferencias, QR y links de pago
    """
    
    def __init__(self):
        """Inicializa el SDK de Mercado Pago"""
        if not settings.MERCADOPAGO_ACCESS_TOKEN:
            logger.warning("MERCADOPAGO_ACCESS_TOKEN no configurado. Los pagos no funcionarán.")
            self.sdk = None
        else:
            self.sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
    
    def create_preference(
        self,
        venta_id: UUID,
        total: float,
        items: list[Dict[str, Any]],
        external_reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crea una preferencia de pago en Mercado Pago
        
        Args:
            venta_id: ID de la venta en nuestro sistema
            total: Monto total de la venta
            items: Lista de items con formato MercadoPago
            external_reference: Referencia externa opcional
        
        Returns:
            Dict con preference_id, init_point (URL) y qr_code_url
        
        Raises:
            Exception: Si hay error en la API de MercadoPago
        """
        if not self.sdk:
            raise Exception("Mercado Pago no está configurado. Configure MERCADOPAGO_ACCESS_TOKEN")
        
        try:
            # Preparar datos de la preferencia
            preference_data = {
                "items": items,
                "external_reference": external_reference or str(venta_id),
                "notification_url": f"{settings.API_V1_STR}/payments/webhook",  # Webhook para notificaciones
                "back_urls": {
                    "success": "https://tutienda.com/success",  # TODO: Configurar URLs reales
                    "failure": "https://tutienda.com/failure",
                    "pending": "https://tutienda.com/pending"
                },
                "auto_return": "approved",
                "statement_descriptor": "NEXUS POS",  # Descripción en resumen de tarjeta
                "metadata": {
                    "venta_id": str(venta_id)
                }
            }
            
            # Crear preferencia en MercadoPago
            logger.info(f"Creando preferencia de pago para venta {venta_id}")
            preference_response = self.sdk.preference().create(preference_data)
            
            # Validar respuesta
            if preference_response["status"] != 201:
                error_message = preference_response.get("response", {}).get("message", "Error desconocido")
                logger.error(f"Error al crear preferencia: {error_message}")
                raise Exception(f"Error de MercadoPago: {error_message}")
            
            response_data = preference_response["response"]
            
            logger.info(f"Preferencia creada exitosamente: {response_data['id']}")
            
            return {
                "preference_id": response_data["id"],
                "init_point": response_data["init_point"],  # URL para redirigir al usuario
                "sandbox_init_point": response_data.get("sandbox_init_point"),  # Para testing
                "qr_code_url": response_data.get("qr_code", {}).get("url"),  # URL del QR (si está disponible)
                "external_reference": response_data.get("external_reference")
            }
        
        except Exception as e:
            logger.error(f"Error al crear preferencia de pago: {str(e)}", exc_info=True)
            raise Exception(f"Error al procesar el pago: {str(e)}")
    
    def get_payment_info(self, payment_id: str) -> Dict[str, Any]:
        """
        Obtiene información de un pago desde Mercado Pago
        
        Args:
            payment_id: ID del pago en MercadoPago
        
        Returns:
            Información completa del pago
        """
        if not self.sdk:
            raise Exception("Mercado Pago no está configurado")
        
        try:
            logger.info(f"Consultando información de pago: {payment_id}")
            payment_info = self.sdk.payment().get(payment_id)
            
            if payment_info["status"] != 200:
                raise Exception("Error al consultar el pago")
            
            return payment_info["response"]
        
        except Exception as e:
            logger.error(f"Error al obtener información de pago {payment_id}: {str(e)}")
            raise
    
    def validate_webhook_signature(self, request_data: Dict[str, Any], x_signature: str) -> bool:
        """
        Valida la firma del webhook de Mercado Pago (opcional pero recomendado)
        
        Args:
            request_data: Datos del request del webhook
            x_signature: Header X-Signature enviado por MercadoPago
        
        Returns:
            True si la firma es válida
        
        TODO: Implementar validación real de firma con MERCADOPAGO_WEBHOOK_SECRET
        """
        if not settings.MERCADOPAGO_WEBHOOK_SECRET:
            logger.warning("MERCADOPAGO_WEBHOOK_SECRET no configurado. Saltando validación de firma.")
            return True
        
        # TODO: Implementar validación de firma según documentación de MercadoPago
        # https://www.mercadopago.com.ar/developers/es/docs/your-integrations/notifications/webhooks
        
        return True


# Instancia singleton del servicio
payment_service = PaymentService()
