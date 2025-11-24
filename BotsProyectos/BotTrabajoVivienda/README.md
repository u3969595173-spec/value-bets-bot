# 🏠💼 BOT "VIDA NUEVA" - Trabajo + Vivienda

**Bot automatizado para encontrar trabajo y vivienda para inmigrantes en España**

---

## 🎯 PROBLEMA QUE RESUELVE:

**Los 2 problemas MÁS CRÍTICOS de inmigrantes:**
1. ❌ Imposible encontrar trabajo (sin papeles, discriminación)
2. ❌ Imposible encontrar piso (sin nómina, sin fianza, discriminación)

**Resultado:** Personas tardan 2-6 MESES buscando manualmente

---

## ✅ SOLUCIÓN:

Bot que escanea 24/7 todas las ofertas de trabajo y vivienda, filtra por criterios específicos de inmigrantes y notifica INSTANTÁNEAMENTE (antes que nadie).

---

## 🔧 FUNCIONALIDADES:

### MÓDULO 1: TRABAJO 💼

**Búsqueda inteligente:**
- Scraping Indeed, Infojobs, LinkedIn
- Filtros especiales:
  - ✅ "Sin papeles OK" (trabajos que contratan sin NIE)
  - ✅ "Con contrato arraigo" (válido para regularizar)
  - ✅ Sectores: Hostelería, Limpieza, Construcción, Almacén
- Auto-aplicación con CV del usuario
- Seguimiento de aplicaciones

**Alertas:**
```
🔥 NUEVO TRABAJO
📍 Camarero - Madrid Centro
💰 1,200€/mes + propinas
📋 Sin papeles OK
⏰ Publicado hace 3 minutos
[VER OFERTA]
```

---

### MÓDULO 2: VIVIENDA 🏠

**Búsqueda inteligente:**
- Scraping Idealista, Fotocasa, Milanuncios
- Filtros especiales:
  - ✅ "Sin nómina OK"
  - ✅ "Sin fianza/depósito"
  - ✅ "Acepta extranjeros"
  - ✅ Precio máximo personalizado
- Detector anti-estafa (rechaza anuncios falsos)
- Velocidad <30 segundos

**Alertas:**
```
🏠 PISO DISPONIBLE
📍 Carabanchel, Madrid
💰 450€/mes (sin fianza)
🛏️ Habitación individual
👥 Acepta extranjeros
⏰ Publicado hace 45 segundos
[CONTACTAR YA]
```

---

## 🎁 CARACTERÍSTICAS KILLER:

### 1. **VELOCIDAD**
- Alertas en 30 segundos (vs 1-2 horas manual)
- Usuario contacta PRIMERO

### 2. **FILTROS ÚNICOS**
- "Sin papeles", "Sin nómina", "Acepta extranjeros"
- NO disponibles en webs oficiales

### 3. **AUTO-APLICACIÓN**
- Bot envía tu CV automáticamente
- Plantillas de mensaje optimizadas

### 4. **ANTI-ESTAFA**
- Detecta patrones de anuncios falsos
- Solo ofertas verificadas

### 5. **SEGUIMIENTO**
- Tracking de aplicaciones
- Recordatorios si no responden

---

## 💰 MODELO DE NEGOCIO:

### GRATIS:
- Alertas 1 vez/día
- 5 búsquedas guardadas
- Filtros básicos

### 15€/MES PREMIUM:
- ⚡ Alertas instantáneas (30 segundos)
- 🤖 Auto-aplicación trabajos
- 🔍 Búsquedas ilimitadas
- 🎯 Filtros avanzados completos
- 📊 Seguimiento aplicaciones
- 🚫 Detector anti-estafa premium

### 50€ SUCCESS FEE (OPCIONAL):
- Solo pagas SI consigues trabajo/piso
- Pagas cuando firmas contrato
- Win-win: Usuario solo paga si funciona

---

## 📊 CASOS DE USO REALES:

### Caso 1: José (Venezuela)
```
Problema: 3 meses buscando trabajo sin éxito
Bot: Encuentra trabajo camarero en 5 días
Resultado: Contrato + papeles arraigo en proceso
Pago: 15€ Premium (vs 2,000€ perdidos sin trabajar)
```

### Caso 2: María (Colombia)
```
Problema: Necesita piso sin nómina urgente
Bot: Alerta piso 480€ sin fianza en 2 días
Resultado: Piso conseguido antes que otros 50 interesados
Pago: 50€ Success fee (vs 1,500€ fianza gestoría)
```

---

## 🛠️ STACK TÉCNICO:

- **Backend:** Python 3.11+
- **Bot:** python-telegram-bot
- **Scraping:** BeautifulSoup + Selenium
- **Base Datos:** Supabase (PostgreSQL)
- **Hosting:** Render (24/7)
- **Pagos:** Stripe
- **Proxies:** Opcional (si escala)

---

## 📊 MÉTRICAS OBJETIVO:

**Mes 1:** 500 usuarios (beta)
**Mes 3:** 5,000 usuarios
**Mes 6:** 25,000 usuarios
**Año 1:** 100,000+ usuarios

**Revenue estimado Año 1:** 1.2M€
(80k usuarios × 15€/mes promedio)

---

## 🚀 ROADMAP:

### FASE 1: MVP (1-2 semanas)
- [ ] Scraping Indeed + Idealista
- [ ] Alertas Telegram básicas
- [ ] Filtros esenciales
- [ ] Base datos usuarios

### FASE 2: PREMIUM (2-3 semanas)
- [ ] Auto-aplicación trabajos
- [ ] Alertas instantáneas (<30 seg)
- [ ] Detector anti-estafa
- [ ] Sistema de pagos Stripe

### FASE 3: ESCALADO (1-2 meses)
- [ ] Más plataformas (Infojobs, Fotocasa, Milanuncios)
- [ ] Dashboard web
- [ ] Estadísticas usuario
- [ ] Sistema de referidos

### FASE 4: EXPANSIÓN (3-6 meses)
- [ ] App móvil
- [ ] Expansión otros países (Italia, Portugal)
- [ ] Integración con gestorías

---

## 🌍 PLATAFORMAS A SCRAPEAR:

### TRABAJO:
- Indeed.es ⭐⭐⭐⭐⭐
- Infojobs.net ⭐⭐⭐⭐
- LinkedIn ⭐⭐⭐
- Jooble ⭐⭐⭐

### VIVIENDA:
- Idealista.com ⭐⭐⭐⭐⭐
- Fotocasa.es ⭐⭐⭐⭐
- Milanuncios.com ⭐⭐⭐
- Badi.com ⭐⭐

---

## 📝 NOTAS DESARROLLO:

**Retos técnicos:**
- Anti-bot protection (solución: headers + delays)
- Rate limiting (solución: scraping moderado + proxies si necesario)
- Captchas (solución: 2captcha API en casos extremos)

**Ventaja competitiva:**
- NO existe bot con filtros "sin papeles" + "sin nómina"
- Velocidad crítica (30 seg vs competencia 1-2 horas)
- Enfoque 100% inmigrantes (nicho ignorado)

---

**Estado:** 📋 Planificación
**Prioridad:** 🔥 ALTA
**Potencial comercial:** 💰💰💰💰💰 (5/5)
**Inicio desarrollo:** Pendiente decisión usuario
