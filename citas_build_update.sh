#!/bin/bash
# Actualización para build.sh de CitasBot
# AGREGAR estas líneas después de la instalación de psycopg2

echo "📦 Instalando dependencias para navegador headless..."

# Instalar dependencias del sistema para Playwright/Chromium
apt-get update
apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1

echo "🌐 Instalando navegador Chromium para Playwright..."
# Instalar navegador Chromium para Playwright
python -m playwright install chromium

echo "✅ Dependencias de navegador instaladas correctamente"
