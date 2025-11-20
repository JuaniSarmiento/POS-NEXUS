"""
Sistema de Rate Limiting - Nexus POS
Protección contra abuso y ataques DoS
"""
import time
from typing import Dict, Tuple, Optional
from collections import defaultdict
from threading import Lock
from fastapi import Request, HTTPException, status


class RateLimiter:
    """
    Rate limiter simple basado en memoria
    En producción, usar Redis para distribuido
    """
    
    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = Lock()
    
    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, Optional[int]]:
        """
        Verifica si una request está permitida
        
        Args:
            key: Identificador único (IP, user_id, etc.)
            max_requests: Máximo de requests permitidas
            window_seconds: Ventana de tiempo en segundos
            
        Returns:
            Tupla (is_allowed, retry_after_seconds)
        """
        current_time = time.time()
        
        with self._lock:
            # Limpiar requests antiguas
            self._requests[key] = [
                timestamp for timestamp in self._requests[key]
                if current_time - timestamp < window_seconds
            ]
            
            # Verificar límite
            if len(self._requests[key]) >= max_requests:
                oldest_request = min(self._requests[key])
                retry_after = int(window_seconds - (current_time - oldest_request))
                return False, retry_after
            
            # Agregar request actual
            self._requests[key].append(current_time)
            return True, None
    
    def reset(self, key: str) -> None:
        """
        Resetea el contador para una key específica
        """
        with self._lock:
            if key in self._requests:
                del self._requests[key]


# Instancia global
rate_limiter = RateLimiter()


async def rate_limit_middleware(
    request: Request,
    max_requests: int = 100,
    window_seconds: int = 60
) -> None:
    """
    Middleware de rate limiting
    
    Args:
        request: Request de FastAPI
        max_requests: Máximo de requests por ventana
        window_seconds: Ventana de tiempo en segundos
        
    Raises:
        HTTPException: 429 si se excede el límite
    """
    # Obtener identificador único (IP del cliente)
    client_ip = request.client.host if request.client else "unknown"
    
    # Verificar rate limit
    is_allowed, retry_after = rate_limiter.is_allowed(
        key=client_ip,
        max_requests=max_requests,
        window_seconds=window_seconds
    )
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Demasiadas solicitudes. Intente nuevamente en {retry_after} segundos",
            headers={"Retry-After": str(retry_after)}
        )


async def rate_limit_strict(request: Request) -> None:
    """Rate limit estricto para endpoints sensibles (10 req/min)"""
    await rate_limit_middleware(request, max_requests=10, window_seconds=60)


async def rate_limit_moderate(request: Request) -> None:
    """Rate limit moderado para operaciones normales (100 req/min)"""
    await rate_limit_middleware(request, max_requests=100, window_seconds=60)


async def rate_limit_relaxed(request: Request) -> None:
    """Rate limit relajado para lecturas (300 req/min)"""
    await rate_limit_middleware(request, max_requests=300, window_seconds=60)
