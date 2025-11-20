@echo off
REM ################################################################################
REM SCRIPT MAESTRO DE TESTING - NEXUS POS (Windows)
REM 
REM Ejecuta toda la suite de tests con reporte de cobertura
REM Autor: Nexus POS Team
REM Fecha: 2025-11-19
REM ################################################################################

SETLOCAL EnableDelayedExpansion

REM Colores y formato (solo en PowerShell)
set "BOLD=[1m"
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "CYAN=[96m"
set "NC=[0m"

REM Variables
set COVERAGE_THRESHOLD=80
set TEST_DB=nexus_pos_test
set REPORT_DIR=htmlcov

echo.
echo ===============================================================
echo.
echo              NEXUS POS - TEST RUNNER
echo.
echo ===============================================================
echo.

REM ################################################################################
REM PASO 1: LIMPIEZA DE CACHE
REM ################################################################################

echo [1/5] Limpiando cache de pytest...

if exist .pytest_cache (
    rmdir /s /q .pytest_cache
    echo [OK] Cache de pytest eliminada
) else (
    echo [INFO] No hay cache de pytest para limpiar
)

for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
echo [OK] __pycache__ eliminado

if exist %REPORT_DIR% (
    rmdir /s /q %REPORT_DIR%
    echo [OK] Reportes de cobertura anteriores eliminados
)

if exist .coverage (
    del .coverage
    echo [OK] Archivo .coverage eliminado
)

echo.

REM ################################################################################
REM PASO 2: VERIFICAR DEPENDENCIAS
REM ################################################################################

echo [2/5] Verificando dependencias...

where pytest >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] pytest no esta instalado
    echo Instalar con: uv pip install -e ".[dev]"
    exit /b 1
)

echo [OK] Dependencias verificadas
echo.

REM ################################################################################
REM PASO 3: EJECUTAR TESTS CON COBERTURA
REM ################################################################################

echo [3/5] Ejecutando tests con cobertura...
echo.

pytest ^
    --cov=app ^
    --cov-report=term-missing ^
    --cov-report=html ^
    --cov-fail-under=%COVERAGE_THRESHOLD% ^
    -v ^
    --tb=short ^
    --color=yes ^
    tests/

set TEST_EXIT_CODE=%ERRORLEVEL%

echo.

REM ################################################################################
REM PASO 4: GENERAR REPORTE DE COBERTURA
REM ################################################################################

echo [4/5] Generando reporte de cobertura...

if exist %REPORT_DIR% (
    echo [OK] Reporte HTML generado en: ./%REPORT_DIR%/index.html
    echo Abrir con: start %REPORT_DIR%/index.html
) else (
    echo [ERROR] No se pudo generar el reporte HTML
)

echo.

REM ################################################################################
REM PASO 5: RESULTADO FINAL
REM ################################################################################

echo [5/5] Resultado Final
echo.

if %TEST_EXIT_CODE% EQU 0 (
    echo ===============================================================
    echo.
    echo              TODOS LOS TESTS PASARON
    echo.
    echo ===============================================================
    echo.
    echo [OK] Cobertura minima alcanzada: %COVERAGE_THRESHOLD%%%
    echo [OK] Sistema listo para produccion
    echo.
    exit /b 0
) else (
    echo ===============================================================
    echo.
    echo                  TESTS FALLARON
    echo.
    echo ===============================================================
    echo.
    echo [ERROR] Algunos tests fallaron o la cobertura es insuficiente
    echo [WARN] Revisa el output de arriba para mas detalles
    echo.
    echo Comandos utiles para debugging:
    echo   pytest tests/ -v -k test_nombre   # Ejecutar un test especifico
    echo   pytest tests/ --lf                # Re-ejecutar solo los fallidos
    echo   pytest tests/ -x                  # Detener en el primer error
    echo.
    exit /b 1
)
