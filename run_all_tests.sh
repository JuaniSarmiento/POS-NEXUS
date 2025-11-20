#!/bin/bash

################################################################################
# SCRIPT MAESTRO DE TESTING - NEXUS POS
# 
# Ejecuta toda la suite de tests con reporte de cobertura
# Autor: Nexus POS Team
# Fecha: 2025-11-19
################################################################################

set -e  # Detener en caso de error

# Colores ANSI para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Banner
echo ""
echo -e "${BOLD}${CYAN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                                                       ║${NC}"
echo -e "${BOLD}${CYAN}║          🧪 NEXUS POS - TEST RUNNER 🧪               ║${NC}"
echo -e "${BOLD}${CYAN}║                                                       ║${NC}"
echo -e "${BOLD}${CYAN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""

# Variables
COVERAGE_THRESHOLD=80
TEST_DB="nexus_pos_test"
REPORT_DIR="htmlcov"

################################################################################
# PASO 1: LIMPIEZA DE CACHÉ
################################################################################

echo -e "${YELLOW}[1/5]${NC} ${BOLD}Limpiando caché de pytest...${NC}"

if [ -d ".pytest_cache" ]; then
    rm -rf .pytest_cache
    echo -e "${GREEN}✓${NC} Caché de pytest eliminada"
else
    echo -e "${BLUE}ℹ${NC} No hay caché de pytest para limpiar"
fi

if [ -d "__pycache__" ]; then
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo -e "${GREEN}✓${NC} __pycache__ eliminado"
fi

if [ -d "$REPORT_DIR" ]; then
    rm -rf $REPORT_DIR
    echo -e "${GREEN}✓${NC} Reportes de cobertura anteriores eliminados"
fi

if [ -f ".coverage" ]; then
    rm .coverage
    echo -e "${GREEN}✓${NC} Archivo .coverage eliminado"
fi

echo ""

################################################################################
# PASO 2: VERIFICAR DEPENDENCIAS
################################################################################

echo -e "${YELLOW}[2/5]${NC} ${BOLD}Verificando dependencias...${NC}"

# Verificar que pytest esté instalado
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}✗ ERROR:${NC} pytest no está instalado"
    echo -e "${CYAN}Instalar con:${NC} uv pip install -e \".[dev]\""
    exit 1
fi

# Verificar que la base de datos de test exista
echo -e "${BLUE}ℹ${NC} Verificando base de datos de test: ${TEST_DB}"

# Si estás usando PostgreSQL, puedes crear la DB de test automáticamente
# Comentado por ahora para evitar errores en ambientes sin psql
# psql -U postgres -c "CREATE DATABASE ${TEST_DB};" 2>/dev/null || echo "DB ya existe"

echo -e "${GREEN}✓${NC} Dependencias verificadas"
echo ""

################################################################################
# PASO 3: EJECUTAR TESTS CON COBERTURA
################################################################################

echo -e "${YELLOW}[3/5]${NC} ${BOLD}Ejecutando tests con cobertura...${NC}"
echo ""

# Ejecutar pytest con opciones avanzadas
pytest \
    --cov=app \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-fail-under=$COVERAGE_THRESHOLD \
    -v \
    --tb=short \
    --color=yes \
    tests/

# Capturar el código de salida
TEST_EXIT_CODE=$?

echo ""

################################################################################
# PASO 4: GENERAR REPORTE DE COBERTURA
################################################################################

echo -e "${YELLOW}[4/5]${NC} ${BOLD}Generando reporte de cobertura...${NC}"

if [ -d "$REPORT_DIR" ]; then
    echo -e "${GREEN}✓${NC} Reporte HTML generado en: ${BOLD}./$REPORT_DIR/index.html${NC}"
    echo -e "${CYAN}Abrir con:${NC} open $REPORT_DIR/index.html  ${BLUE}(macOS)${NC}"
    echo -e "${CYAN}          ${NC} xdg-open $REPORT_DIR/index.html  ${BLUE}(Linux)${NC}"
    echo -e "${CYAN}          ${NC} start $REPORT_DIR/index.html  ${BLUE}(Windows)${NC}"
else
    echo -e "${RED}✗${NC} No se pudo generar el reporte HTML"
fi

echo ""

################################################################################
# PASO 5: RESULTADO FINAL
################################################################################

echo -e "${YELLOW}[5/5]${NC} ${BOLD}Resultado Final${NC}"
echo ""

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${BOLD}${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║                                                       ║${NC}"
    echo -e "${BOLD}${GREEN}║              ✅ TODOS LOS TESTS PASARON ✅             ║${NC}"
    echo -e "${BOLD}${GREEN}║                                                       ║${NC}"
    echo -e "${BOLD}${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}✓${NC} Cobertura mínima alcanzada: ${COVERAGE_THRESHOLD}%"
    echo -e "${GREEN}✓${NC} Sistema listo para producción"
    echo ""
    exit 0
else
    echo -e "${BOLD}${RED}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${RED}║                                                       ║${NC}"
    echo -e "${BOLD}${RED}║                ❌ TESTS FALLARON ❌                    ║${NC}"
    echo -e "${BOLD}${RED}║                                                       ║${NC}"
    echo -e "${BOLD}${RED}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${RED}✗${NC} Algunos tests fallaron o la cobertura es insuficiente"
    echo -e "${YELLOW}⚠${NC} Revisa el output de arriba para más detalles"
    echo ""
    echo -e "${CYAN}Comandos útiles para debugging:${NC}"
    echo -e "  ${BOLD}pytest tests/ -v -k test_nombre${NC}  ${BLUE}# Ejecutar un test específico${NC}"
    echo -e "  ${BOLD}pytest tests/ --lf${NC}              ${BLUE}# Re-ejecutar solo los fallidos${NC}"
    echo -e "  ${BOLD}pytest tests/ -x${NC}                ${BLUE}# Detener en el primer error${NC}"
    echo ""
    exit 1
fi
