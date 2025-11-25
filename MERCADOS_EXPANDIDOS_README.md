# Mercados Expandidos - Documentación

## 📊 Implementación Completada

Se han agregado **mercados expandidos** al bot de value bets, aumentando significativamente las oportunidades de análisis:

### Mercados Implementados

#### 🏀 Mercados por Periodo

**Cuartos (Quarters)** - Para NBA y otros deportes con 4 períodos:
- `h2h_q1`, `h2h_q2`, `h2h_q3`, `h2h_q4` - Ganador por cuarto
- `spreads_q1`, `spreads_q2`, `spreads_q3`, `spreads_q4` - Hándicap por cuarto
- `totals_q1`, `totals_q2`, `totals_q3`, `totals_q4` - Total puntos por cuarto

**Mitades (Halves)** - Para todos los deportes:
- `h2h_h1`, `h2h_h2` - Ganador por mitad
- `spreads_h1`, `spreads_h2` - Hándicap por mitad
- `totals_h1`, `totals_h2` - Total puntos por mitad

#### 👤 Estadísticas de Jugadores (Player Props)

**Baloncesto:**
- `player_points` - Puntos del jugador
- `player_assists` - Asistencias del jugador
- `player_rebounds` - Rebotes del jugador

**Fútbol Americano:**
- `player_pass_tds` - Touchdowns de pase
- `player_rush_yds` - Yardas terrestres
- `player_receptions` - Recepciones

### 📈 Impacto en el Sistema

**Antes:** ~40-50 picks por análisis (3 mercados × ~15 eventos)
**Ahora:** ~200+ picks por análisis (hasta 15 mercados × ~15 eventos)

### 🔧 Implementación Técnica

#### 1. API Fetching (`data/odds_api.py`)

Estrategia de dos pasos:
```python
# 1. Fetch mercados básicos para todos los eventos
GET /v4/sports/{sport}/odds?markets=h2h,spreads,totals

# 2. Fetch mercados expandidos por evento específico
GET /v4/sports/{sport}/events/{event_id}/odds?markets=h2h_q1,...,player_points,...
```

**Ventaja:** Obtiene todos los mercados disponibles
**Costo:** Aumenta uso de API credits (1 credit por mercado por región)

#### 2. Traducciones (`utils/sport_translator.py`)

Nueva función `translate_market()` con traducciones en español:
- `h2h_q1` → "Ganador 1er Cuarto"
- `player_points` → "Puntos del Jugador"
- `totals_h1` → "Total 1era Mitad"

#### 3. Scanner (`scanner/scanner.py`)

Extendido para procesar los nuevos mercados:
- Acepta 26 tipos de mercados (vs 3 antes)
- Maneja campo `description` para nombres de jugadores en player props
- Aplica probabilidades conservadoras a player props (52%/48%)

#### 4. Formateo de Alertas (`notifier/alert_formatter.py`)

Nueva función `get_market_info()` que formatea mensajes según el tipo:

**Ejemplo - Quarter:**
```
🏀 Ganador 1er Cuarto
🎯 Apuesta: Los Angeles Lakers gana el 1er Cuarto
💰 Cuota: 1.95
```

**Ejemplo - Player Prop:**
```
📊 Puntos del Jugador
🏀 Jugador: LeBron James
🎯 Apuesta: OVER 25.5 puntos del jugador
💰 Cuota: 1.83
ℹ️ Significa: LeBron James debe hacer MÁS de 25.5 puntos del jugador
```

### ⚠️ Consideraciones de Uso

#### Costo de API

**Antes:**
- 3 mercados × 18 deportes = 54 credits por check
- ~16 checks/día = 864 credits/día
- Duración: ~35 días con 30,000 credits

**Ahora (con todos los mercados):**
- ~15 mercados × 18 deportes = 270 credits por check
- ~16 checks/día = 4,320 credits/día
- Duración: ~7 días con 30,000 credits

**Recomendación:** 
1. Usar solo para deportes clave (NBA, NFL) al inicio
2. Monitorear uso de credits con `/remaining` en la API
3. Ajustar frecuencia de checks según necesidad

#### Calidad de Mercados

Los mercados expandidos pueden tener:
- ✅ **Más oportunidades** de value (mercados menos eficientes)
- ⚠️ **Mayor varianza** (especialmente player props)
- ⚠️ **Menor liquidez** en algunas casas de apuestas

### 🧪 Testing

Ejecutar test completo:
```bash
python test_expanded_markets.py
```

Verifica:
1. ✅ Traducciones correctas
2. ✅ Formateo de alertas
3. ✅ Fetching de API real
4. ✅ Scanner procesando mercados
5. ✅ Ejemplos de picks expandidos

### 📊 Resultados de Test Real

```
Total candidatos: 207 picks
Distribución:
  - h2h: 41 picks
  - h2h_q1: 15 picks
  - player_assists: 77 picks
  - player_points: 32 picks
  - player_rebounds: 42 picks
```

### 🚀 Próximos Pasos Sugeridos

1. **Monitoreo Inicial** (1 semana):
   - Activar solo para NBA
   - Verificar tasas de acierto en quarters y player props
   - Ajustar probabilidades si es necesario

2. **Expansión Gradual**:
   - Agregar NFL (player_pass_tds, player_rush_yds)
   - Agregar Soccer (h2h_h1, h2h_h2 para mitades)
   - Mantener otros deportes solo con mercados básicos

3. **Optimización**:
   - Implementar caché de mercados expandidos
   - Fetch selectivo (solo eventos con high value en mercados básicos)
   - Rate limiting más inteligente

### 📝 Notas Técnicas

- Los player props usan el campo `description` de la API para el nombre del jugador
- Los mercados de quarters solo están disponibles para deportes con 4 períodos
- Las mitades están disponibles para la mayoría de deportes
- El scanner usa las mismas probabilidades base para quarters que para mercados completos
- El sistema de verificación todavía necesita adaptarse para period markets

---

**Fecha de Implementación:** Noviembre 25, 2025
**Versión:** 2.0 - Mercados Expandidos
**Estado:** ✅ Implementado y Testeado
