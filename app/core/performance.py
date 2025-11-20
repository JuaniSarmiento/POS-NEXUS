"""
Middleware de Performance Monitoring - Nexus POS
Monitorea queries lentas y performance de endpoints
"""
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware que monitorea el performance de requests
    y alerta sobre queries/endpoints lentos
    """
    
    def __init__(self, app, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold  # segundos
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Procesar request
        response = await call_next(request)
        
        # Calcular duración
        duration = time.time() - start_time
        
        # Alertar si es lento
        if duration > self.slow_request_threshold:
            logger.warning(
                f"SLOW REQUEST: {request.method} {request.url.path} "
                f"took {duration:.2f}s (threshold: {self.slow_request_threshold}s)",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_seconds": duration,
                    "query_params": dict(request.query_params),
                    "client_host": request.client.host if request.client else None
                }
            )
        
        # Agregar métrica al header
        response.headers["X-Performance-Ms"] = str(int(duration * 1000))
        
        return response
