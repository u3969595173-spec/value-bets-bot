# 🤖 Sistema de Auto-Llenado Automático para CitasBot

## 📋 Resumen

Este sistema permite que CitasBot **reserve citas automáticamente** cuando detecta disponibilidad, eliminando la necesidad de intervención manual. Funciona 24/7, incluso cuando duermes.

## ✨ Características

✅ **Auto-llenado automático** del formulario del gobierno
✅ **Respaldo manual** si el auto-llenado falla
✅ **Funciona en modo headless** (sin ventana de navegador)
✅ **Screenshots automáticos** como evidencia
✅ **Notificaciones detalladas** al usuario y admin
✅ **Compatible con Render** 24/7

## 🚀 Instalación

### Paso 1: Copiar archivos

Copia estos archivos al repositorio de CitasBot (`bot-citas-homologacion-`):

```bash
# Desde el directorio BotValueBets
cp citas_auto_fill.py ../bot-citas-homologacion-/auto_fill.py
```

### Paso 2: Actualizar requirements.txt

Agrega estas líneas a `requirements.txt`:

```txt
playwright>=1.40.0
playwright-stealth>=1.0.2
Pillow>=10.0.0
```

### Paso 3: Actualizar build.sh

Agrega este bloque al final de `build.sh`:

```bash
echo "📦 Instalando dependencias para navegador headless..."

apt-get update
apt-get install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libatspi2.0-0 libxshmfence1

echo "🌐 Instalando navegador Chromium..."
python -m playwright install chromium

echo "✅ Dependencias instaladas"
```

### Paso 4: Modificar main.py

#### 4.1 Agregar import (línea ~10)

```python
from auto_fill import auto_fill_appointment
```

#### 4.2 Reemplazar función `cita_disponible_handler`

Encuentra la función actual (aprox línea 200-250) y reemplázala con la versión en `citas_main_integration.py` (líneas 18-200).

La nueva versión:
1. Intenta auto-llenado primero
2. Si falla, envía notificación manual
3. Notifica al admin sobre el resultado

## 📂 Archivos Creados

| Archivo | Descripción |
|---------|-------------|
| `citas_auto_fill.py` | ✅ Módulo principal de automatización con Playwright |
| `citas_requirements_add.txt` | ✅ Dependencias a agregar |
| `citas_build_update.sh` | ✅ Script para instalar navegador |
| `citas_main_integration.py` | ✅ Código para integrar en main.py |
| `CITAS_AUTO_FILL_README.md` | 📄 Este archivo |

## 🔄 Flujo de Funcionamiento

```
1. CitasBot detecta cita disponible
   ↓
2. Extrae datos del usuario de PostgreSQL
   ↓
3. INTENTA AUTO-LLENADO AUTOMÁTICO
   ├─ ✅ ÉXITO → Notifica confirmación
   └─ ❌ FALLO → Envía notificación manual
   ↓
4. Admin recibe reporte del resultado
```

## 💡 Ejemplo de Uso

Cuando detecta una cita:

### ✅ Escenario 1: Auto-llenado exitoso

```
🤖 ¡CITA DISPONIBLE!

📅 Fecha: 2025-12-01

⚙️ Intentando reserva automática...
Por favor espera...

[2-5 segundos después]

✅ ¡RESERVA COMPLETADA AUTOMÁTICAMENTE!

📅 Fecha: 2025-12-01
🎫 Confirmación: REF-2025-12345

📋 Tus datos:
• Nombre: Leandro Eloy Tamayo Reyes
• Documento: Z0934880G
• Email: leandroeloytamayoreyes@gmail.com
• Teléfono: +34654034110

📧 Revisa tu email para más detalles.
```

### ⚠️ Escenario 2: Respaldo manual

```
🎯 ¡CITA DISPONIBLE!

⚠️ El auto-llenado no pudo completarse
Por favor, reserva manualmente:

📅 Fechas: 2025-12-01

📋 Tus datos registrados:
• Nombre: Leandro Eloy Tamayo Reyes
• Documento: Z0934880G
• Email: leandroeloytamayoreyes@gmail.com
• Teléfono: +34654034110

⚡ ACTÚA RÁPIDO - Las citas se agotan en segundos

[Botón: 🔗 IR AL SITIO WEB]
```

## 🔧 Configuración Avanzada

### Timeout personalizado

Edita `auto_fill.py` línea 19:

```python
self.timeout = 30000  # 30 segundos (default)
self.timeout = 60000  # 60 segundos (sitio lento)
```

### Screenshots persistentes

Por defecto se guardan localmente. Para guardarlos en la nube:

```python
# En auto_fill.py, después de screenshot
# Subir a S3, Cloudinary, etc.
```

## 🧪 Testing Local

Antes de desplegar, prueba localmente:

```bash
cd bot-citas-homologacion-

# Instalar dependencias
pip install -r requirements.txt
playwright install chromium

# Probar auto-fill
python auto_fill.py
```

Esto ejecutará una prueba con los datos de ejemplo.

## 🚢 Despliegue en Render

### 1. Commit y push

```bash
cd bot-citas-homologacion-
git add .
git commit -m "feat: Agregar auto-llenado automático de citas"
git push origin main
```

### 2. Render detecta cambios

Render ejecutará:
1. `build.sh` → Instala Chromium y dependencias
2. Instala requirements.txt con Playwright
3. Inicia el bot

### 3. Verificar logs

En Render Dashboard → CitasBot → Logs:

```
📦 Instalando dependencias para navegador headless...
🌐 Instalando navegador Chromium...
✅ Dependencias instaladas
...
🤖 Bot iniciado correctamente
```

## ⚠️ Consideraciones Importantes

### Recursos en Render

- **RAM**: Chromium usa ~200-300MB adicionales
- **CPU**: Picos durante auto-llenado (~30s)
- **Plan recomendado**: Professional ($7/mo) - ya lo tienes ✅

### Limitaciones

1. **Sitio web cambiante**: Si el gobierno cambia su sitio, puede requerir actualizar selectores
2. **Captchas**: Si agregan captcha, auto-llenado fallará (respaldo manual se activa)
3. **Rate limiting**: El gobierno puede bloquear por demasiadas peticiones

### Monitoreo

Revisa logs regularmente para:
- ✅ Auto-llenados exitosos
- ⚠️ Fallos y razones
- 📊 Tasa de éxito

## 🆘 Troubleshooting

### Problema: "Timeout durante auto-llenado"

**Causa**: Sitio web lento o inaccesible

**Solución**: Aumentar timeout en `auto_fill.py`:
```python
self.timeout = 60000  # 60 segundos
```

### Problema: "No se pudo encontrar el servicio SASTU"

**Causa**: Selectores desactualizados

**Solución**: Inspeccionar sitio web y actualizar selectores en `_select_service()`:
```python
selectors = [
    "text=/.*SASTU.*/i",
    "button.nuevo-selector",  # Agregar nuevo selector
]
```

### Problema: "Error al confirmar reserva"

**Causa**: Botón de confirmación no encontrado

**Solución**: Actualizar selectores en `_confirm_booking()`:
```python
confirm_buttons = [
    "button:has-text('Confirmar')",
    "button.btn-confirm",  # Agregar nuevo selector
]
```

## 📊 Métricas de Éxito

Después de implementar, monitorea:

| Métrica | Meta |
|---------|------|
| Tasa de auto-llenado exitoso | >80% |
| Tiempo promedio de reserva | <10 segundos |
| Citas perdidas por errores | 0 |
| Falsos positivos | <5% |

## 🔐 Seguridad

- ✅ Datos sensibles solo en PostgreSQL
- ✅ No se guardan credenciales en código
- ✅ Screenshots locales (no compartidos)
- ✅ Conexión HTTPS al sitio del gobierno

## 📞 Soporte

Si necesitas ayuda:

1. Revisa logs en Render
2. Verifica que auto_fill.py esté importado correctamente
3. Prueba localmente primero
4. Ajusta selectores según cambios del sitio web

## 🎯 Próximos Pasos

Una vez desplegado:

1. ✅ Espera que se detecte una cita
2. ✅ Verifica que el auto-llenado funcione
3. ✅ Si falla, ajusta selectores
4. ✅ Monitorea tasa de éxito
5. ✅ Disfruta de citas automáticas 24/7 😴

## 📝 Changelog

### v1.0.0 (2024-11-21)
- ✅ Implementación inicial
- ✅ Auto-llenado con Playwright
- ✅ Sistema de respaldo manual
- ✅ Screenshots automáticos
- ✅ Notificaciones mejoradas

---

**¿Preguntas? ¿Problemas?** Revisa los logs o ajusta los selectores según necesites.

**¡Que no se te escape ninguna cita más!** 🎯✨
