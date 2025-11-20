"""
Sistema de Logging Robusto - Nexus POS
Configuración centralizada con rotación de archivos y formato estructurado
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from typing import Optional
import json


class JSONFormatter(logging.Formatter):
    """
    Formateador de logs en formato JSON para facilitar análisis
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Agregar información de excepción si existe
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Agregar campos personalizados
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "tienda_id"):
            log_data["tienda_id"] = record.tienda_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "ip_address"):
            log_data["ip_address"] = record.ip_address
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """
    Formateador con colores para consola (desarrollo)
    """
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    enable_console: bool = True,
    enable_file: bool = True,
    enable_json: bool = False
) -> None:
    """
    Configura el sistema de logging global
    
    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directorio para almacenar logs (default: ./logs)
        enable_console: Habilitar output a consola
        enable_file: Habilitar output a archivos
        enable_json: Usar formato JSON en archivos
    """
    # Crear directorio de logs si no existe
    if log_dir is None:
        log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Limpiar handlers existentes
    root_logger.handlers.clear()
    
    # HANDLER 1: Consola (desarrollo)
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        console_format = ColoredFormatter(
            '%(levelname)-8s | %(asctime)s | %(name)-25s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        root_logger.addHandler(console_handler)
    
    # HANDLER 2: Archivo general con rotación por tamaño
    if enable_file:
        general_file = log_dir / "nexus_pos.log"
        general_handler = RotatingFileHandler(
            general_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        general_handler.setLevel(logging.INFO)
        
        if enable_json:
            general_handler.setFormatter(JSONFormatter())
        else:
            general_handler.setFormatter(logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
        root_logger.addHandler(general_handler)
    
    # HANDLER 3: Archivo de errores con rotación diaria
    if enable_file:
        error_file = log_dir / "errors.log"
        error_handler = TimedRotatingFileHandler(
            error_file,
            when='midnight',
            interval=1,
            backupCount=30,  # Retener 30 días
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        
        if enable_json:
            error_handler.setFormatter(JSONFormatter())
        else:
            error_handler.setFormatter(logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
        root_logger.addHandler(error_handler)
    
    # HANDLER 4: Archivo de auditoría (solo operaciones críticas)
    if enable_file:
        audit_file = log_dir / "audit.log"
        audit_handler = TimedRotatingFileHandler(
            audit_file,
            when='midnight',
            interval=1,
            backupCount=90,  # Retener 90 días para cumplimiento
            encoding='utf-8'
        )
        audit_handler.setLevel(logging.INFO)
        audit_handler.addFilter(lambda record: hasattr(record, 'audit'))
        
        audit_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(audit_handler)
    
    # Configurar niveles específicos por módulo
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    # Log inicial
    logger = logging.getLogger(__name__)
    logger.info(f"Sistema de logging inicializado - Nivel: {log_level}")


def get_audit_logger() -> logging.Logger:
    """
    Retorna un logger configurado específicamente para auditoría
    """
    logger = logging.getLogger("audit")
    return logger


def log_audit(
    action: str,
    user_id: Optional[str] = None,
    tienda_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None
) -> None:
    """
    Registra una acción de auditoría
    
    Args:
        action: Descripción de la acción (ej: "VENTA_CREADA", "PRODUCTO_MODIFICADO")
        user_id: ID del usuario que realizó la acción
        tienda_id: ID de la tienda afectada
        details: Detalles adicionales en formato dict
        ip_address: Dirección IP del cliente
    """
    logger = get_audit_logger()
    
    # Crear un LogRecord personalizado
    extra = {
        'audit': True,
        'action': action,
    }
    
    if user_id:
        extra['user_id'] = user_id
    if tienda_id:
        extra['tienda_id'] = tienda_id
    if ip_address:
        extra['ip_address'] = ip_address
    
    message = f"AUDIT: {action}"
    if details:
        message += f" | {json.dumps(details, ensure_ascii=False)}"
    
    logger.info(message, extra=extra)
