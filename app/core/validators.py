"""
Validadores de Negocio - Nexus POS
Validaciones complejas reutilizables para lógica de negocio
"""
from typing import List, Optional, Tuple
from decimal import Decimal
from app.models import Producto, Venta
from app.core.exceptions import (
    StockInsuficienteException,
    ProductoNoEncontradoException,
    VentaInvalidaException
)


class ProductoValidator:
    """
    Validador para operaciones relacionadas con productos
    """
    
    @staticmethod
    def validar_stock_disponible(
        producto: Producto,
        cantidad_solicitada: float
    ) -> None:
        """
        Valida que haya stock suficiente para una operación
        
        Args:
            producto: Producto a validar
            cantidad_solicitada: Cantidad que se desea operar
            
        Raises:
            StockInsuficienteException: Si no hay stock suficiente
        """
        if producto.stock_actual < cantidad_solicitada:
            raise StockInsuficienteException(
                producto=producto.nombre,
                disponible=producto.stock_actual,
                solicitado=cantidad_solicitada
            )
    
    @staticmethod
    def validar_cantidad_tipo_producto(
        producto: Producto,
        cantidad: float
    ) -> None:
        """
        Valida que la cantidad sea apropiada para el tipo de producto
        
        Args:
            producto: Producto a validar
            cantidad: Cantidad a validar
            
        Raises:
            VentaInvalidaException: Si la cantidad no es válida para el tipo
        """
        # Productos no pesables deben tener cantidades enteras
        if producto.tipo != 'pesable' and cantidad != int(cantidad):
            raise VentaInvalidaException(
                message=f"El producto '{producto.nombre}' no permite cantidades decimales",
                details={
                    "producto_id": str(producto.id),
                    "tipo": producto.tipo,
                    "cantidad_invalida": cantidad
                }
            )
        
        # Cantidad debe ser positiva
        if cantidad <= 0:
            raise VentaInvalidaException(
                message=f"La cantidad debe ser mayor a 0",
                details={"cantidad": cantidad}
            )
        
        # Validar límite máximo razonable (evitar errores de input)
        if cantidad > 10000:
            raise VentaInvalidaException(
                message=f"La cantidad parece demasiado alta. Verifique el valor ingresado",
                details={"cantidad": cantidad}
            )
    
    @staticmethod
    def validar_producto_activo(producto: Producto) -> None:
        """
        Valida que un producto esté activo para operaciones
        
        Args:
            producto: Producto a validar
            
        Raises:
            VentaInvalidaException: Si el producto está inactivo
        """
        if not producto.is_active:
            raise VentaInvalidaException(
                message=f"El producto '{producto.nombre}' (SKU: {producto.sku}) está inactivo",
                details={
                    "producto_id": str(producto.id),
                    "sku": producto.sku
                }
            )
    
    @staticmethod
    def validar_precio_consistente(
        precio_esperado: float,
        precio_actual: float,
        tolerancia: float = 0.01
    ) -> None:
        """
        Valida que el precio no haya cambiado significativamente
        (protección contra race conditions o modificaciones concurrentes)
        
        Args:
            precio_esperado: Precio que el cliente vio
            precio_actual: Precio actual en la base de datos
            tolerancia: Margen de tolerancia (default 1%)
            
        Raises:
            VentaInvalidaException: Si el precio cambió más de la tolerancia
        """
        diferencia = abs(precio_actual - precio_esperado)
        diferencia_porcentual = (diferencia / precio_actual) * 100
        
        if diferencia_porcentual > tolerancia:
            raise VentaInvalidaException(
                message=f"El precio del producto ha cambiado. Por favor actualice el carrito",
                details={
                    "precio_anterior": precio_esperado,
                    "precio_actual": precio_actual,
                    "diferencia": diferencia
                }
            )
    
    @staticmethod
    def calcular_stock_variantes(producto: Producto) -> float:
        """
        Calcula el stock total de un producto tipo ropa con variantes
        
        Args:
            producto: Producto tipo ropa
            
        Returns:
            Stock total calculado sumando variantes
        """
        if producto.tipo != 'ropa':
            return producto.stock_actual
        
        variantes = producto.atributos.get('variantes', [])
        stock_total = sum(
            float(variante.get('stock', 0))
            for variante in variantes
            if isinstance(variante, dict)
        )
        
        return stock_total
    
    @staticmethod
    def validar_sku_unico(sku: str, tienda_id: str, productos_existentes: List[Producto]) -> None:
        """
        Valida que un SKU sea único dentro de una tienda
        
        Args:
            sku: SKU a validar
            tienda_id: ID de la tienda
            productos_existentes: Lista de productos existentes
            
        Raises:
            VentaInvalidaException: Si el SKU ya existe
        """
        for producto in productos_existentes:
            if producto.sku == sku:
                raise VentaInvalidaException(
                    message=f"Ya existe un producto con SKU '{sku}' en esta tienda",
                    details={
                        "sku": sku,
                        "producto_existente_id": str(producto.id)
                    }
                )


class VentaValidator:
    """
    Validador para operaciones de ventas
    """
    
    @staticmethod
    def validar_total_venta(
        total_calculado: float,
        total_recibido: Optional[float] = None
    ) -> None:
        """
        Valida que el total de la venta sea correcto
        
        Args:
            total_calculado: Total calculado en el servidor
            total_recibido: Total enviado desde el cliente (opcional)
            
        Raises:
            VentaInvalidaException: Si los totales no coinciden
        """
        # Validar total mínimo
        if total_calculado <= 0:
            raise VentaInvalidaException(
                message="El total de la venta debe ser mayor a 0",
                details={"total": total_calculado}
            )
        
        # Si el cliente envía un total, validar que coincida
        if total_recibido is not None:
            diferencia = abs(total_calculado - total_recibido)
            if diferencia > 0.01:  # Margen de error para redondeos
                raise VentaInvalidaException(
                    message="El total de la venta no coincide con el calculado",
                    details={
                        "total_calculado": total_calculado,
                        "total_recibido": total_recibido,
                        "diferencia": diferencia
                    }
                )
    
    @staticmethod
    def validar_items_venta(items_count: int) -> None:
        """
        Valida que la venta tenga items
        
        Args:
            items_count: Cantidad de items en la venta
            
        Raises:
            VentaInvalidaException: Si no hay items
        """
        if items_count == 0:
            raise VentaInvalidaException(
                message="La venta debe contener al menos un producto"
            )
        
        # Validar límite razonable de items (evitar ataques DoS)
        if items_count > 1000:
            raise VentaInvalidaException(
                message="La venta contiene demasiados items. Contacte soporte para ventas grandes",
                details={"items_count": items_count}
            )
    
    @staticmethod
    def validar_metodo_pago(metodo_pago: str) -> None:
        """
        Valida que el método de pago sea válido
        
        Args:
            metodo_pago: Método de pago a validar
            
        Raises:
            VentaInvalidaException: Si el método de pago no es válido
        """
        metodos_validos = ['efectivo', 'tarjeta_debito', 'tarjeta_credito', 'transferencia', 'mercadopago', 'qr']
        
        if metodo_pago not in metodos_validos:
            raise VentaInvalidaException(
                message=f"Método de pago '{metodo_pago}' no válido",
                details={
                    "metodo_recibido": metodo_pago,
                    "metodos_validos": metodos_validos
                }
            )
    
    @staticmethod
    def puede_anular_venta(venta: Venta) -> Tuple[bool, Optional[str]]:
        """
        Verifica si una venta puede ser anulada
        
        Args:
            venta: Venta a verificar
            
        Returns:
            Tupla (puede_anular, razon_si_no)
        """
        if venta.status_pago == 'anulado':
            return False, "La venta ya está anulada"
        
        # No permitir anular ventas pagadas con Mercado Pago sin proceso de reembolso
        if venta.status_pago == 'pagado' and venta.metodo_pago == 'mercadopago':
            return False, "Las ventas pagadas con MercadoPago requieren proceso de reembolso"
        
        # TODO: Agregar validación de tiempo límite (ej: no anular ventas de más de 24hs)
        
        return True, None
    
    @staticmethod
    def validar_descuento(
        subtotal: float,
        descuento: Optional[float] = None,
        descuento_porcentaje: Optional[float] = None
    ) -> float:
        """
        Valida y calcula el descuento aplicable
        
        Args:
            subtotal: Subtotal de la venta antes de descuento
            descuento: Descuento fijo en pesos
            descuento_porcentaje: Descuento en porcentaje
            
        Returns:
            Monto del descuento a aplicar
            
        Raises:
            VentaInvalidaException: Si el descuento no es válido
        """
        if descuento is not None and descuento_porcentaje is not None:
            raise VentaInvalidaException(
                message="No se puede aplicar descuento fijo y porcentaje simultáneamente"
            )
        
        if descuento is not None:
            if descuento < 0:
                raise VentaInvalidaException(message="El descuento no puede ser negativo")
            if descuento > subtotal:
                raise VentaInvalidaException(
                    message="El descuento no puede ser mayor al subtotal",
                    details={"descuento": descuento, "subtotal": subtotal}
                )
            return descuento
        
        if descuento_porcentaje is not None:
            if descuento_porcentaje < 0 or descuento_porcentaje > 100:
                raise VentaInvalidaException(
                    message="El porcentaje de descuento debe estar entre 0 y 100"
                )
            return subtotal * (descuento_porcentaje / 100)
        
        return 0.0
