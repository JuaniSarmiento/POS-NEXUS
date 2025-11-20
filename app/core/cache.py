"""
Sistema de Caché para Nexus POS
Implementa caché en memoria con TTL para optimizar consultas frecuentes
"""
from datetime import datetime, timedelta
from typing import Any, Optional, Callable
import functools
import json
import hashlib
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Gestor de caché en memoria con TTL"""
    
    def __init__(self):
        self._cache: dict[str, dict] = {}
        
    def get(self, key: str) -> Optional[Any]:
        """Obtiene un valor del caché si no expiró"""
        if key not in self._cache:
            return None
            
        entry = self._cache[key]
        if datetime.utcnow() > entry['expires_at']:
            # Expiró, eliminar
            del self._cache[key]
            logger.debug(f"Cache miss (expired): {key}")
            return None
            
        logger.debug(f"Cache hit: {key}")
        return entry['value']
        
    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """Guarda un valor en caché con TTL"""
        self._cache[key] = {
            'value': value,
            'expires_at': datetime.utcnow() + timedelta(seconds=ttl_seconds),
            'created_at': datetime.utcnow()
        }
        logger.debug(f"Cache set: {key} (TTL: {ttl_seconds}s)")
        
    def delete(self, key: str):
        """Elimina una entrada del caché"""
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache deleted: {key}")
            
    def clear(self):
        """Limpia todo el caché"""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared: {count} entries removed")
        
    def invalidate_pattern(self, pattern: str):
        """Invalida todas las claves que coincidan con un patrón"""
        keys_to_delete = [key for key in self._cache.keys() if pattern in key]
        for key in keys_to_delete:
            del self._cache[key]
        logger.info(f"Cache invalidated: {len(keys_to_delete)} entries with pattern '{pattern}'")


# Instancia global del caché
cache_manager = CacheManager()


def generate_cache_key(*args, **kwargs) -> str:
    """Genera una clave de caché única basada en argumentos"""
    key_data = {
        'args': [str(arg) for arg in args],
        'kwargs': {k: str(v) for k, v in sorted(kwargs.items())}
    }
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(ttl_seconds: int = 300, key_prefix: str = ""):
    """
    Decorador para cachear resultados de funciones async
    
    Args:
        ttl_seconds: Tiempo de vida del caché en segundos
        key_prefix: Prefijo para la clave de caché
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generar clave de caché
            cache_key = f"{key_prefix}:{func.__name__}:{generate_cache_key(*args, **kwargs)}"
            
            # Intentar obtener del caché
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value
                
            # Si no está en caché, ejecutar función
            result = await func(*args, **kwargs)
            
            # Guardar en caché
            cache_manager.set(cache_key, result, ttl_seconds)
            
            return result
        return wrapper
    return decorator


def invalidate_cache(pattern: str):
    """Helper para invalidar caché por patrón"""
    cache_manager.invalidate_pattern(pattern)
