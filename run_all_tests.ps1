# ==============================================================================
# NEXUS POS - PowerShell Test Runner
# Script de ejecución de tests optimizado para Windows PowerShell 5.1+
# ==============================================================================

# Configuración de colores
$ErrorActionPreference = "Stop"

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Banner {
    Write-ColorOutput "`n╔═══════════════════════════════════════════════════════╗" "Cyan"
    Write-ColorOutput "║                                                       ║" "Cyan"
    Write-ColorOutput "║          🧪 NEXUS POS - TEST RUNNER 🧪               ║" "Cyan"
    Write-ColorOutput "║                                                       ║" "Cyan"
    Write-ColorOutput "╚═══════════════════════════════════════════════════════╝" "Cyan"
    Write-Host ""
}

# Variables de configuración
$COVERAGE_THRESHOLD = 80
$REPORT_DIR = "htmlcov"

# Banner inicial
Write-Banner

# ==============================================================================
# PASO 1: LIMPIEZA DE CACHÉ
# ==============================================================================

Write-ColorOutput "[1/5] Limpiando caché de pytest..." "Yellow"

if (Test-Path ".pytest_cache") {
    Remove-Item -Recurse -Force ".pytest_cache"
    Write-ColorOutput "✓ Caché de pytest eliminada" "Green"
} else {
    Write-ColorOutput "ℹ No hay caché de pytest para limpiar" "Blue"
}

Get-ChildItem -Path . -Recurse -Filter "__pycache__" -Directory | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-ColorOutput "✓ __pycache__ eliminado" "Green"

if (Test-Path $REPORT_DIR) {
    Remove-Item -Recurse -Force $REPORT_DIR
    Write-ColorOutput "✓ Reportes de cobertura anteriores eliminados" "Green"
}

if (Test-Path ".coverage") {
    Remove-Item ".coverage"
    Write-ColorOutput "✓ Archivo .coverage eliminado" "Green"
}

Write-Host ""

# ==============================================================================
# PASO 2: VERIFICAR DEPENDENCIAS
# ==============================================================================

Write-ColorOutput "[2/5] Verificando dependencias..." "Yellow"

try {
    $pytestVersion = & pytest --version 2>&1
    Write-ColorOutput "✓ pytest encontrado: $pytestVersion" "Green"
} catch {
    Write-ColorOutput "✗ ERROR: pytest no está instalado" "Red"
    Write-ColorOutput "Instalar con: uv pip install -e `".[dev]`"" "Cyan"
    exit 1
}

Write-Host ""

# ==============================================================================
# PASO 3: EJECUTAR TESTS CON COBERTURA
# ==============================================================================

Write-ColorOutput "[3/5] Ejecutando tests con cobertura..." "Yellow"
Write-Host ""

try {
    & pytest `
        --cov=app `
        --cov-report=term-missing `
        --cov-report=html `
        --cov-fail-under=$COVERAGE_THRESHOLD `
        -v `
        --tb=short `
        --color=yes `
        tests/
    
    $TEST_EXIT_CODE = $LASTEXITCODE
} catch {
    Write-ColorOutput "✗ Error al ejecutar tests: $_" "Red"
    exit 1
}

Write-Host ""

# ==============================================================================
# PASO 4: GENERAR REPORTE DE COBERTURA
# ==============================================================================

Write-ColorOutput "[4/5] Generando reporte de cobertura..." "Yellow"

if (Test-Path $REPORT_DIR) {
    Write-ColorOutput "✓ Reporte HTML generado en: ./$REPORT_DIR/index.html" "Green"
    Write-ColorOutput "Abrir con: start $REPORT_DIR/index.html" "Cyan"
} else {
    Write-ColorOutput "✗ No se pudo generar el reporte HTML" "Red"
}

Write-Host ""

# ==============================================================================
# PASO 5: RESULTADO FINAL
# ==============================================================================

Write-ColorOutput "[5/5] Resultado Final" "Yellow"
Write-Host ""

if ($TEST_EXIT_CODE -eq 0) {
    Write-ColorOutput "╔═══════════════════════════════════════════════════════╗" "Green"
    Write-ColorOutput "║                                                       ║" "Green"
    Write-ColorOutput "║              ✅ TODOS LOS TESTS PASARON ✅             ║" "Green"
    Write-ColorOutput "║                                                       ║" "Green"
    Write-ColorOutput "╚═══════════════════════════════════════════════════════╝" "Green"
    Write-Host ""
    Write-ColorOutput "✓ Cobertura mínima alcanzada: $COVERAGE_THRESHOLD%" "Green"
    Write-ColorOutput "✓ Sistema listo para producción" "Green"
    Write-Host ""
    
    # Abrir reporte automáticamente
    if (Test-Path "$REPORT_DIR/index.html") {
        $openReport = Read-Host "¿Deseas abrir el reporte de cobertura? (S/N)"
        if ($openReport -eq "S" -or $openReport -eq "s") {
            Start-Process "$REPORT_DIR/index.html"
        }
    }
    
    exit 0
} else {
    Write-ColorOutput "╔═══════════════════════════════════════════════════════╗" "Red"
    Write-ColorOutput "║                                                       ║" "Red"
    Write-ColorOutput "║                ❌ TESTS FALLARON ❌                    ║" "Red"
    Write-ColorOutput "║                                                       ║" "Red"
    Write-ColorOutput "╚═══════════════════════════════════════════════════════╝" "Red"
    Write-Host ""
    Write-ColorOutput "✗ Algunos tests fallaron o la cobertura es insuficiente" "Red"
    Write-ColorOutput "⚠ Revisa el output de arriba para más detalles" "Yellow"
    Write-Host ""
    Write-ColorOutput "Comandos útiles para debugging:" "Cyan"
    Write-ColorOutput "  pytest tests/ -v -k test_nombre  # Ejecutar un test específico" "White"
    Write-ColorOutput "  pytest tests/ --lf              # Re-ejecutar solo los fallidos" "White"
    Write-ColorOutput "  pytest tests/ -x                # Detener en el primer error" "White"
    Write-Host ""
    exit 1
}
