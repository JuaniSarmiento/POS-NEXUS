"""
Modelos de Base de Datos - Nexus POS
SQLModel con soporte Multi-Tenant
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB


class Tienda(SQLModel, table=True):
    """
    Modelo de Tienda - Entidad principal Multi-Tenant
    Cada tienda representa un cliente independiente del sistema
    """
    __tablename__ = "tiendas"
    
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    nombre: str = Field(
        max_length=255,
        nullable=False,
        index=True
    )
    rubro: str = Field(
        default="general",
        max_length=50,
        nullable=False,
        description="Categoría del negocio: ropa, carniceria, ferreteria, etc."
    )
    is_active: bool = Field(
        default=True,
        nullable=False,
        index=True
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )
    
    # Relaciones
    users: List["User"] = Relationship(back_populates="tienda")
    productos: List["Producto"] = Relationship(back_populates="tienda")
    ventas: List["Venta"] = Relationship(back_populates="tienda")
    insights: List["Insight"] = Relationship(back_populates="tienda")


class User(SQLModel, table=True):
    """
    Modelo de Usuario - Con aislamiento Multi-Tenant
    Cada usuario pertenece a una tienda específica (tienda_id)
    """
    __tablename__ = "users"
    
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    email: str = Field(
        max_length=255,
        nullable=False,
        unique=True,
        index=True
    )
    hashed_password: str = Field(
        nullable=False,
        description="Password hasheado con bcrypt"
    )
    full_name: str = Field(
        max_length=255,
        nullable=False
    )
    rol: str = Field(
        max_length=50,
        nullable=False,
        description="Rol del usuario: owner, cajero, admin"
    )
    is_active: bool = Field(
        default=True,
        nullable=False,
        index=True
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )
    
    # Columna discriminadora Multi-Tenant (CRÍTICA)
    tienda_id: UUID = Field(
        foreign_key="tiendas.id",
        nullable=False,
        index=True,
        description="ID de la tienda a la que pertenece el usuario"
    )
    
    # Relaciones
    tienda: Optional[Tienda] = Relationship(back_populates="users")


class Producto(SQLModel, table=True):
    """
    Modelo de Producto - Polimórfico con JSONB
    Soporta diferentes tipos de productos con atributos personalizados
    """
    __tablename__ = "productos"
    
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    nombre: str = Field(
        max_length=255,
        nullable=False,
        index=True
    )
    sku: str = Field(
        max_length=100,
        nullable=False,
        index=True,
        description="Código único del producto (Stock Keeping Unit)"
    )
    descripcion: Optional[str] = Field(
        default=None,
        nullable=True
    )
    precio_venta: float = Field(
        nullable=False,
        description="Precio de venta al público"
    )
    precio_costo: float = Field(
        nullable=False,
        description="Precio de costo del producto"
    )
    stock_actual: float = Field(
        default=0.0,
        nullable=False,
        description="Stock disponible actual (puede ser decimal para productos pesables)"
    )
    tipo: str = Field(
        max_length=50,
        nullable=False,
        description="Tipo de producto: general, ropa, pesable"
    )
    atributos: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB),
        description="Atributos personalizados según el tipo de producto"
    )
    is_active: bool = Field(
        default=True,
        nullable=False,
        index=True
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    )
    
    # Columna discriminadora Multi-Tenant (CRÍTICA)
    tienda_id: UUID = Field(
        foreign_key="tiendas.id",
        nullable=False,
        index=True,
        description="ID de la tienda a la que pertenece el producto"
    )
    
    # Relaciones
    tienda: Optional[Tienda] = Relationship(back_populates="productos")
    detalles_venta: List["DetalleVenta"] = Relationship(back_populates="producto")


class Venta(SQLModel, table=True):
    """
    Modelo de Venta - Transacción de venta completa
    Cabecera de la venta con totales y método de pago
    """
    __tablename__ = "ventas"
    
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    fecha: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True, server_default=func.now())
    )
    total: float = Field(
        nullable=False,
        description="Total calculado de la venta"
    )
    metodo_pago: str = Field(
        max_length=50,
        nullable=False,
        description="Método de pago: efectivo, tarjeta_debito, tarjeta_credito, transferencia"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )
    
    # Campos de Pago y Facturación
    status_pago: str = Field(
        default="pendiente",
        max_length=50,
        nullable=False,
        index=True,
        description="Estado del pago: pendiente, pagado, anulado"
    )
    payment_id: Optional[str] = Field(
        default=None,
        max_length=255,
        nullable=True,
        index=True,
        description="ID de la transacción en Mercado Pago u otro proveedor"
    )
    afip_cae: Optional[str] = Field(
        default=None,
        max_length=50,
        nullable=True,
        description="Código de Autorización Electrónica de AFIP"
    )
    afip_cae_vto: Optional[datetime] = Field(
        default=None,
        nullable=True,
        description="Fecha de vencimiento del CAE"
    )
    
    # Columna discriminadora Multi-Tenant (CRÍTICA)
    tienda_id: UUID = Field(
        foreign_key="tiendas.id",
        nullable=False,
        index=True,
        description="ID de la tienda a la que pertenece la venta"
    )
    
    # Relaciones
    tienda: Optional[Tienda] = Relationship(back_populates="ventas")
    detalles: List["DetalleVenta"] = Relationship(back_populates="venta", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class DetalleVenta(SQLModel, table=True):
    """
    Modelo de Detalle de Venta - Items individuales de una venta
    Snapshot de precios al momento de la transacción
    """
    __tablename__ = "detalles_venta"
    
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    cantidad: float = Field(
        nullable=False,
        description="Cantidad vendida (puede ser decimal para productos pesables)"
    )
    precio_unitario: float = Field(
        nullable=False,
        description="Precio unitario al momento de la venta (snapshot)"
    )
    subtotal: float = Field(
        nullable=False,
        description="Subtotal calculado: cantidad * precio_unitario"
    )
    
    # Foreign Keys
    venta_id: UUID = Field(
        foreign_key="ventas.id",
        nullable=False,
        index=True
    )
    producto_id: UUID = Field(
        foreign_key="productos.id",
        nullable=False,
        index=True
    )
    
    # Relaciones
    venta: Optional[Venta] = Relationship(back_populates="detalles")
    producto: Optional[Producto] = Relationship(back_populates="detalles_venta")


class Insight(SQLModel, table=True):
    """
    Modelo de Insight - Alertas y recomendaciones inteligentes
    Generadas automáticamente por el motor de análisis
    """
    __tablename__ = "insights"
    
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    tipo: str = Field(
        max_length=100,
        nullable=False,
        index=True,
        description="Tipo de insight: STOCK_BAJO, VENTAS_DIARIAS, PRODUCTO_POPULAR, etc."
    )
    mensaje: str = Field(
        nullable=False,
        description="Mensaje descriptivo del insight para mostrar al usuario"
    )
    nivel_urgencia: str = Field(
        max_length=50,
        nullable=False,
        index=True,
        description="Nivel de urgencia: BAJA, MEDIA, ALTA, CRITICA"
    )
    is_active: bool = Field(
        default=True,
        nullable=False,
        index=True,
        description="Si el insight está activo o fue archivado"
    )
    extra_data: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB),
        description="Datos adicionales específicos del insight (producto_id, monto, etc.)"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True, server_default=func.now())
    )
    
    # Columna discriminadora Multi-Tenant (CRÍTICA)
    tienda_id: UUID = Field(
        foreign_key="tiendas.id",
        nullable=False,
        index=True,
        description="ID de la tienda a la que pertenece el insight"
    )
    
    # Relaciones
    tienda: Optional[Tienda] = Relationship(back_populates="insights")
