"""
Manejo Global de Excepciones - Nexus POS
Handler centralizado para todas las excepciones de la aplicación
"""
import logging
from typing import Union, Dict, Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from pydantic import ValidationError


logger = logging.getLogger(__name__)


class NexusPOSException(Exception):
    """
    Excepción base personalizada para Nexus POS
    """
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Dict[str, Any] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class StockInsuficienteException(NexusPOSException):
    """Excepción específica para problemas de stock"""
    def __init__(self, producto: str, disponible: float, solicitado: float):
        super().__init__(
            message=f"Stock insuficiente para '{producto}'",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={
                "producto": producto,
                "stock_disponible": disponible,
                "cantidad_solicitada": solicitado
            }
        )


class ProductoNoEncontradoException(NexusPOSException):
    """Excepción para producto no encontrado"""
    def __init__(self, identificador: str):
        super().__init__(
            message=f"Producto no encontrado: {identificador}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"identificador": identificador}
        )


class VentaInvalidaException(NexusPOSException):
    """Excepción para ventas inválidas"""
    pass


async def nexus_exception_handler(
    request: Request,
    exc: NexusPOSException
) -> JSONResponse:
    """
    Handler para excepciones personalizadas de Nexus POS
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.warning(
        f"NexusPOS Exception: {exc.message}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "details": exc.details
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "message": exc.message,
                "code": exc.status_code,
                "details": exc.details
            },
            "request_id": request_id
        }
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException
) -> JSONResponse:
    """
    Handler mejorado para HTTPException de FastAPI
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.warning(
        f"HTTP Exception: {exc.detail}",
        extra={
            "request_id": request_id,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "message": exc.detail,
                "code": exc.status_code
            },
            "request_id": request_id
        }
    )


async def validation_exception_handler(
    request: Request,
    exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """
    Handler para errores de validación de Pydantic
    Retorna mensajes más amigables
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Extraer errores de validación
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(x) for x in error["loc"])
        message = error["msg"]
        errors.append({
            "field": field,
            "message": message,
            "type": error["type"]
        })
    
    logger.warning(
        f"Validation Error en {request.url.path}",
        extra={
            "request_id": request_id,
            "errors": errors
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "message": "Error de validación en los datos enviados",
                "code": 422,
                "validation_errors": errors
            },
            "request_id": request_id
        }
    )


async def sqlalchemy_exception_handler(
    request: Request,
    exc: SQLAlchemyError
) -> JSONResponse:
    """
    Handler para errores de SQLAlchemy
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Determinar tipo de error
    if isinstance(exc, IntegrityError):
        # Error de integridad (unique, foreign key, etc.)
        logger.error(
            f"Database Integrity Error: {str(exc)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        
        message = "Error de integridad de datos. Posiblemente un valor duplicado o referencia inválida."
        status_code = status.HTTP_409_CONFLICT
    else:
        # Otros errores de base de datos
        logger.error(
            f"Database Error: {str(exc)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        
        message = "Error al procesar la operación en base de datos"
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "message": message,
                "code": status_code
            },
            "request_id": request_id
        }
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handler genérico para excepciones no capturadas
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.critical(
        f"Unhandled Exception: {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "message": "Error interno del servidor. Por favor contacte al soporte.",
                "code": 500
            },
            "request_id": request_id
        }
    )
