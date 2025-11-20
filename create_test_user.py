"""Script para crear usuario de prueba en la base de datos"""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from app.models import User

DATABASE_URL = "postgresql+asyncpg://nexuspos:nexuspos_secret@localhost:5432/nexus_pos"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_test_user():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Crear usuario admin
        hashed_password = pwd_context.hash("password123")
        user = User(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="admin@test.com",
            hashed_password=hashed_password,
            full_name="Admin Test",
            rol="admin",
            is_active=True,
            tienda_id=uuid.UUID("00000000-0000-0000-0000-000000000001")
        )
        
        session.add(user)
        await session.commit()
        print(f"✓ Usuario creado: {user.email}")
        print(f"  Password: password123")
        print(f"  ID: {user.id}")

if __name__ == "__main__":
    asyncio.run(create_test_user())
