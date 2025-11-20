# =========================================
# Script de Migración Automatizado - Nexus POS
# Aplica el campo 'rubro' a la tabla 'tiendas' en Supabase
# =========================================

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  NEXUS POS - Migración a Supabase" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que estamos en el directorio correcto
if (-Not (Test-Path "alembic.ini")) {
    Write-Host "[ERROR] No se encuentra alembic.ini" -ForegroundColor Red
    Write-Host "Por favor ejecuta este script desde el directorio raíz del proyecto." -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/5] Verificando archivo .env..." -ForegroundColor Yellow
if (-Not (Test-Path ".env")) {
    Write-Host "[ERROR] No se encuentra el archivo .env" -ForegroundColor Red
    Write-Host "Copia .env.example a .env y configura las credenciales de Supabase." -ForegroundColor Yellow
    exit 1
}

# Verificar credenciales
$envContent = Get-Content ".env" -Raw
if ($envContent -match "localhost" -or $envContent -match "your_secure_password") {
    Write-Host "[ADVERTENCIA] Parece que .env no está configurado para Supabase." -ForegroundColor Yellow
    Write-Host "Verifica que contenga las credenciales correctas:" -ForegroundColor Yellow
    Write-Host "  POSTGRES_SERVER=aws-1-us-east-2.pooler.supabase.com" -ForegroundColor Gray
    Write-Host "  POSTGRES_USER=postgres.kdqfohbtxlmykjubxqok" -ForegroundColor Gray
    Write-Host ""
    $continue = Read-Host "¿Deseas continuar de todas formas? (s/n)"
    if ($continue -ne "s") {
        Write-Host "Operación cancelada." -ForegroundColor Red
        exit 1
    }
}

Write-Host "[OK] Archivo .env encontrado" -ForegroundColor Green
Write-Host ""

Write-Host "[2/5] Verificando instalación de Alembic..." -ForegroundColor Yellow
try {
    $alembicVersion = & alembic --version 2>&1
    Write-Host "[OK] Alembic instalado: $alembicVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Alembic no está instalado" -ForegroundColor Red
    Write-Host "Instalando Alembic..." -ForegroundColor Yellow
    pip install alembic
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Falló la instalación de Alembic" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Alembic instalado correctamente" -ForegroundColor Green
}
Write-Host ""

Write-Host "[3/5] Generando migración automática..." -ForegroundColor Yellow
Write-Host "Este paso detectará el campo 'rubro' agregado al modelo Tienda" -ForegroundColor Gray

$migrationName = "add_rubro_field_to_tienda"
& alembic revision --autogenerate -m $migrationName

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Falló la generación de la migración" -ForegroundColor Red
    Write-Host "Verifica que la base de datos sea accesible y que los modelos estén correctos." -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK] Migración generada exitosamente" -ForegroundColor Green
Write-Host ""

# Encontrar el archivo de migración más reciente
$latestMigration = Get-ChildItem "alembic\versions\*.py" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($latestMigration) {
    Write-Host "Archivo de migración: $($latestMigration.Name)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Vista previa de la migración:" -ForegroundColor Cyan
    Write-Host "-----------------------------" -ForegroundColor Gray
    Get-Content $latestMigration.FullName | Select-Object -First 30
    Write-Host "-----------------------------" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "[4/5] ¿Deseas revisar la migración antes de aplicarla?" -ForegroundColor Yellow
$review = Read-Host "Escribe 's' para revisar, o presiona Enter para continuar"

if ($review -eq "s") {
    Write-Host "Abriendo archivo de migración..." -ForegroundColor Gray
    Start-Process notepad $latestMigration.FullName
    Write-Host ""
    Read-Host "Presiona Enter cuando hayas terminado de revisar"
}

Write-Host ""
Write-Host "[5/5] Aplicando migración a Supabase..." -ForegroundColor Yellow
Write-Host "IMPORTANTE: Este paso modificará la base de datos en producción." -ForegroundColor Red
Write-Host ""
$confirm = Read-Host "¿Estás seguro de que deseas continuar? (escribe 'SI' en mayúsculas)"

if ($confirm -ne "SI") {
    Write-Host "Operación cancelada por el usuario." -ForegroundColor Yellow
    Write-Host "Puedes aplicar la migración manualmente con:" -ForegroundColor Gray
    Write-Host "  alembic upgrade head" -ForegroundColor Cyan
    exit 0
}

Write-Host ""
Write-Host "Aplicando migración..." -ForegroundColor Yellow
& alembic upgrade head

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Falló la aplicación de la migración" -ForegroundColor Red
    Write-Host "Verifica los logs arriba para más detalles." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Posibles soluciones:" -ForegroundColor Yellow
    Write-Host "  1. Verificar credenciales en .env" -ForegroundColor Gray
    Write-Host "  2. Verificar que Supabase esté accesible" -ForegroundColor Gray
    Write-Host "  3. Ejecutar: alembic current" -ForegroundColor Gray
    exit 1
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "  ✓ MIGRACIÓN APLICADA EXITOSAMENTE" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Próximos pasos:" -ForegroundColor Cyan
Write-Host "  1. Verificar en Supabase SQL Editor:" -ForegroundColor Gray
Write-Host "     SELECT * FROM information_schema.columns WHERE table_name = 'tiendas';" -ForegroundColor White
Write-Host ""
Write-Host "  2. Probar creando una tienda:" -ForegroundColor Gray
Write-Host "     INSERT INTO tiendas (id, nombre, rubro, is_active)" -ForegroundColor White
Write-Host "     VALUES (gen_random_uuid(), 'Test', 'ropa', true);" -ForegroundColor White
Write-Host ""
Write-Host "  3. Verificar en el Dashboard de Supabase" -ForegroundColor Gray
Write-Host ""

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Estado actual de la base de datos:" -ForegroundColor Cyan
& alembic current
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "¡Deployment completado! 🚀" -ForegroundColor Green
