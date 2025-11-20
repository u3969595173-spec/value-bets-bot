"""notifier/alert_formatter.py - Formatea mensajes diferenciados para usuarios gratuitos y premium.
"""
from typing import Dict
import sys
from pathlib import Path

# Asegurar que utils esté en el path
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.sport_translator import translate_sport
from utils.lineup_analyzer import get_lineup_section


def escape_markdown(text: str) -> str:
    """
    Escapa solo los caracteres que pueden romper Markdown básico.
    Para Telegram Markdown básico: escapar * _ ` [
    """
    if not text:
        return text
    # Escapar caracteres que rompen formato
    text = str(text).replace('*', '\\*').replace('_', '\\_').replace('`', '\\`').replace('[', '\\[')
    return text


def format_free_alert(candidate: Dict) -> str:
    """
    Mensaje resumido para usuarios gratuitos.
    
    Solo incluye:
    - Equipos y deporte
    - Tipo de mercado específico
    - Cuota y selección clara
    - Casa de apuestas
    """
    lines = []
    
    # Header simple
    sport_es = translate_sport(candidate.get('sport_key', ''), candidate.get('sport'))
    event_name = escape_markdown(candidate.get('event', 'N/A'))
    lines.append(f"🎯 **{sport_es.upper()}**")
    lines.append(f"⚽ **{event_name}**")
    lines.append("")
    
    # Información detallada del mercado con formato claro
    market = escape_markdown(candidate.get('market', 'N/A'))
    market_key = candidate.get('market_key', '')
    selection = escape_markdown(candidate['selection'])
    odd = candidate['odds']
    bookmaker = escape_markdown(candidate.get('bookmaker', 'N/A'))
    point = candidate.get('point')

    # Detectar tipo de mercado si no viene market_key
    if not market_key:
        if 'spread' in market.lower() or 'handicap' in market.lower() or 'hándicap' in market.lower():
            market_key = 'spreads'
        elif 'total' in market.lower() or 'over' in selection.lower() or 'under' in selection.lower():
            market_key = 'totals'
        else:
            market_key = 'h2h'

    # Formatear según el tipo de mercado DE FORMA CLARA
    lines.append("📋 **APUESTA:**")
    lines.append(f"   🏆 **Partido:** {event_name}")
    lines.append("")

    if market_key == 'h2h':
        # Ganador directo
        lines.append(f"   ⚽ **Tipo:** GANADOR DEL PARTIDO")
        lines.append(f"   🎯 **Apuesta:** {selection}")
        lines.append(f"   💰 **Cuota:** {odd:.2f}")

    elif market_key == 'spreads':
        # Hándicap
        lines.append(f"   🎯 **Tipo:** HÁNDICAP")
        lines.append(f"   ⚽ **Equipo:** {selection}")
        if point is not None:
            lines.append(f"   📊 **Línea:** {point:+.1f} puntos")
            lines.append(f"   💰 **Cuota:** {odd:.2f}")
            lines.append("")
            if point > 0:
                lines.append(f"   ℹ️ **Significa:** {selection} puede PERDER hasta {abs(point)} puntos y GANAS")
            else:
                lines.append(f"   ℹ️ **Significa:** {selection} debe GANAR por MÁS de {abs(point)} puntos")
        else:
            lines.append(f"   💰 **Cuota:** {odd:.2f}")

    elif market_key == 'totals':
        # Totales (Over/Under)
        over_under = "OVER" if "over" in selection.lower() else "UNDER"
        lines.append(f"   📊 **Tipo:** TOTAL DE PUNTOS")
        if point is not None:
            lines.append(f"   🎯 **Apuesta:** {over_under} {point} puntos")
            lines.append(f"   💰 **Cuota:** {odd:.2f}")
            lines.append("")
            if over_under == "OVER":
                lines.append(f"   ℹ️ **Significa:** Marcador TOTAL debe ser MAYOR a {point} puntos")
            else:
                lines.append(f"   ℹ️ **Significa:** Marcador TOTAL debe ser MENOR a {point} puntos")
        else:
            lines.append(f"   🎯 **Apuesta:** {selection}")
            lines.append(f"   💰 **Cuota:** {odd:.2f}")
    else:
        # Otro mercado
        lines.append(f"   📊 **Tipo:** {market}")
        lines.append(f"   🎯 **Apuesta:** {selection}")
        lines.append(f"   💰 **Cuota:** {odd:.2f}")


    lines.append("")
    lines.append(f"🏠 **Casa de apuestas:** {bookmaker}")
    
    # Mostrar si se usó casa estándar
    if candidate.get('was_bet365_adjusted'):
        original_odds_val = candidate.get('original_odds')
        original_bm = escape_markdown(candidate.get('original_bookmaker', 'N/A'))
        lines.append("")
        lines.append(f"💎 **Cuota ajustada a casa estándar:**")
        lines.append(f"   {original_bm}: @ {original_odds_val:.2f}")
        lines.append(f"   {bookmaker}: @ {odd:.2f} ✅")

    # --- PICK EXPLICADO ---
    lines.append("")
    lines.append("📝 **PICK EXPLICADO:**")
    # Cuota
    lines.append(f"• Cuota: {odd:.2f}")
    # Probabilidad real
    real_prob = candidate.get('real_probability')
    if real_prob is not None:
        lines.append(f"• Probabilidad real: {real_prob*100:.1f}%")
    # Valor esperado (EV)
    value = candidate.get('value')
    if value is not None:
        ev = (value-1)*100
        lines.append(f"• Valor esperado (EV): {ev:.1f}%")
    # Racha del equipo
    streak = candidate.get('streak')
    if streak:
        lines.append(f"• Racha del equipo: {streak}")
    lines.append("")

    # Información de valor básica
    if value is not None and value > 0:
        lines.append(f"💎 **VALOR:** {value:.3f}")
    
    if candidate.get('edge_percent', 0) > 0:
        lines.append(f"🎯 **VENTAJA:** +{candidate['edge_percent']:.1f}%")
    
    # Análisis detallado del pronóstico
    lines.append("")
    lines.append("🔍 **ANÁLISIS DETALLADO:**")
    
    if candidate.get('real_probability', 0) > 0:
        real_prob_pct = candidate['real_probability'] * 100
        implied_prob_pct = (100/candidate['odds'])
        lines.append(f"📊 **Probabilidad real:** {real_prob_pct:.0f}%")
        lines.append(f"📉 **Prob. implícita casa:** {implied_prob_pct:.0f}%")
        lines.append(f"💎 **Diferencia a tu favor:** +{real_prob_pct - implied_prob_pct:.1f}%")
    
    # Análisis específico del mercado
    market_key = candidate.get('market_key', '')
    if market_key == 'spreads' or 'hándicap' in candidate.get('market', '').lower():
        lines.append("🎯 **Tipo:** Hándicap - Línea favorable según estadísticas")
    elif market_key == 'h2h' or 'ganador' in candidate.get('market', '').lower():
        lines.append("⚽ **Tipo:** Ganador - Probabilidad subestimada por el mercado")
    elif market_key == 'totals' or 'total' in candidate.get('market', '').lower():
        lines.append("📊 **Tipo:** Totales - Línea mal calibrada por la casa")
    
    lines.append("✅ **Recomendación:** APOSTAR - Value bet confirmado")
    
    # Análisis de alineaciones usando sistema especializado
    lines.append("")
    lineup_analysis = get_lineup_section(candidate, is_premium=False)
    lines.extend(lineup_analysis)
    
    # Nota sobre mejora de cuotas
    lines.append("")
    lines.append("💡 **OPTIMIZA TUS GANANCIAS:**")
    lines.append("🔍 Busca esta misma apuesta en otras casas")
    lines.append("📈 Puedes encontrar cuotas mejores (hasta 0.05-0.10 más)")
    lines.append("💰 Cada 0.05 de mejora = +5% más ganancia")
    lines.append("")
    lines.append("🎯 **MEJORA TU % DE ACIERTO:**")
    lines.append("📊 Si buscas cuotas más pequeñas/conservadoras")
    lines.append("✅ Puedes acomodar mejor la apuesta a mi pronóstico")
    lines.append("🔧 Ajusta líneas de hándicap o totales más favorables")
    lines.append("📈 Menor riesgo = Mayor porcentaje de aciertos")
    
    # Call to action
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("🌟 UPGRADE A PREMIUM 🌟")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("Desbloquea:")
    lines.append("✨ Alertas ILIMITADAS")
    lines.append("📊 Análisis completo con estadísticas")
    lines.append("💎 Probabilidades y valor esperado")
    lines.append("💰 Stake recomendado según bankroll")
    lines.append("📈 Gestión automática de bankroll")
    lines.append("🎯 Tracking de resultados y ROI")
    lines.append("")
    lines.append("💬 Contacta para más info")
    
    return "\n".join(lines)


def format_premium_alert(candidate: Dict, user, stake: float) -> str:
    """
    Mensaje completo para usuarios premium.
    
    Incluye todo el análisis avanzado + stake recomendado.
    """
    lines = []
    
    # Header premium
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💎 ALERTA PREMIUM 💎")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    
    # Información detallada del evento
    sport_es = translate_sport(candidate.get('sport_key', ''), candidate.get('sport'))
    market = escape_markdown(candidate.get('market', 'N/A'))
    market_key = candidate.get('market_key', '')
    selection = escape_markdown(candidate['selection'])
    odd = candidate['odds']
    bookmaker = escape_markdown(candidate.get('bookmaker', 'N/A'))
    original_bookmaker = bookmaker
    event_name = escape_markdown(candidate.get('event', 'N/A'))
    
    point = candidate.get('point')

    # Detectar tipo de mercado si no viene market_key
    if not market_key:
        if 'spread' in market.lower() or 'handicap' in market.lower() or 'hándicap' in market.lower():
            market_key = 'spreads'
        elif 'total' in market.lower() or 'over' in selection.lower() or 'under' in selection.lower():
            market_key = 'totals'
        else:
            market_key = 'h2h'

    lines.append(f"🎯 **{sport_es.upper()}**")
    lines.append(f"⚽ **{event_name}**")
    lines.append("")
    lines.append("📋 **APUESTA RECOMENDADA:**")

    if market_key == 'h2h':
        # Ganador directo
        lines.append(f"   ⚽ **Tipo:** GANADOR DEL PARTIDO")
        lines.append(f"   🎯 **Apuesta:** {selection}")
        lines.append(f"   💰 **Cuota:** {odd:.2f}")

    elif market_key == 'spreads':
        # Hándicap
        lines.append(f"   🎯 **Tipo:** HÁNDICAP")
        lines.append(f"   ⚽ **Equipo:** {selection}")
        if point is not None:
            lines.append(f"   📊 **Línea:** {point:+.1f} puntos")
            lines.append(f"   💰 **Cuota:** {odd:.2f}")
            lines.append("")
            if point > 0:
                lines.append(f"   ℹ️ **Significa:** {selection} puede PERDER hasta {abs(point)} puntos y GANAS")
            else:
                lines.append(f"   ℹ️ **Significa:** {selection} debe GANAR por MÁS de {abs(point)} puntos")
        else:
            lines.append(f"   💰 **Cuota:** {odd:.2f}")

    elif market_key == 'totals':
        # Totales (Over/Under)
        over_under = "OVER" if "over" in selection.lower() else "UNDER"
        lines.append(f"   📊 **Tipo:** TOTAL DE PUNTOS")
        if point is not None:
            lines.append(f"   🎯 **Apuesta:** {over_under} {point} puntos")
            lines.append(f"   💰 **Cuota:** {odd:.2f}")
            lines.append("")
            if over_under == "OVER":
                lines.append(f"   ℹ️ **Significa:** Marcador TOTAL debe ser MAYOR a {point} puntos")
            else:
                lines.append(f"   ℹ️ **Significa:** Marcador TOTAL debe ser MENOR a {point} puntos")
        else:
            lines.append(f"   🎯 **Apuesta:** {selection}")
            lines.append(f"   💰 **Cuota:** {odd:.2f}")
    else:
        # Otro mercado
        lines.append(f"   📊 **Mercado:** {market}")
        lines.append(f"   ✅ **Selección:** {selection}")
        lines.append(f"   💰 **Cuota:** {odd:.2f}")

    lines.append("")
    lines.append(f"🏠 **Casa recomendada:** {original_bookmaker}")
    
    # Mostrar si se usó William Hill (casa estándar)
    if candidate.get('was_bet365_adjusted'):
        original_odds_val = candidate.get('original_odds')
        original_bm = escape_markdown(candidate.get('original_bookmaker', 'N/A'))
        lines.append("")
        lines.append(f"💎 **Cuota ajustada a casa estándar:**")
        lines.append(f"   {original_bm}: @ {original_odds_val:.2f}")
        lines.append(f"   {bookmaker}: @ {odd:.2f} ✅")
        if odd < original_odds_val:
            lines.append(f"   ℹ️ Cuota más conservadora y confiable")
    
    # Mostrar si la línea fue ajustada (handicap/total)
    if candidate.get('was_adjusted'):
        original_odds_val = candidate.get('original_odds')
        original_point_val = candidate.get('original_point')
        lines.append("")
        lines.append(f"🔧 **Línea ajustada automáticamente:**")
        if original_point_val is not None:
            lines.append(f"   Original: {selection} {original_point_val} @ {original_odds_val:.2f}")
            lines.append(f"   Ajustada: {selection} {point} @ {odd:.2f}")
        else:
            lines.append(f"   Original: @ {original_odds_val:.2f}")
            lines.append(f"   Ajustada: @ {odd:.2f}")
        lines.append(f"   💡 Línea más conservadora para mejor control")

    # --- PICK EXPLICADO ---
    lines.append("")
    lines.append("📝 **PICK EXPLICADO:**")
    # Cuota
    lines.append(f"• Cuota: {odd:.2f}")
    # Probabilidad real
    real_prob = candidate.get('real_probability')
    if real_prob is not None:
        lines.append(f"• Probabilidad real: {real_prob*100:.1f}%")
    # Valor esperado (EV)
    value = candidate.get('value')
    if value is not None:
        ev = (value-1)*100
        lines.append(f"• Valor esperado (EV): {ev:.1f}%")
    # Racha del equipo
    streak = candidate.get('streak')
    if streak:
        lines.append(f"• Racha del equipo: {streak}")
    lines.append("")

    if candidate.get('commence_time'):
        from datetime import datetime, timezone
        commence_time = candidate['commence_time']
        # Si es datetime, formatearlo bien
        if isinstance(commence_time, datetime):
            commence_str = commence_time.strftime('%Y-%m-%d %H:%M UTC')
        else:
            # Si es string, usarlo directamente
            commence_str = str(commence_time)
        lines.append(f"⏰ **INICIO:** {commence_str}")

    lines.append("")

    # Métricas de valor
    lines.append("📈 **ANÁLISIS PROFESIONAL DE VALOR:**")
    
    if candidate.get('real_probability', 0) > 0:
        real_prob_pct = candidate['real_probability'] * 100
        lines.append(f"✅ **Prob. Real:** {real_prob_pct:.1f}%")
    
    if candidate.get('implied_probability', 0) > 0:
        implied_prob_pct = candidate['implied_probability'] * 100
        lines.append(f"📉 **Prob. Implícita:** {implied_prob_pct:.1f}%")
        prob_diff = real_prob_pct - implied_prob_pct
        if prob_diff > 0:
            lines.append(f"⚡ **Ventaja detectada:** +{prob_diff:.1f}% a tu favor")
    
    if candidate.get('value', 0) > 0:
        lines.append(f"💎 **Valor:** {candidate['value']:.3f} (Ganancia esperada: {((candidate['value']-1)*100):.1f}%)")
    
    # Análisis detallado específico del mercado
    lines.append("")
    lines.append("🔍 **ANÁLISIS TÉCNICO DETALLADO:**")
    
    market_key = candidate.get('market_key', '')
    if market_key == 'spreads' or 'hándicap' in candidate.get('market', '').lower():
        lines.append("🎯 **Mercado Hándicap:**")
        lines.append("• Línea mal calibrada por la casa de apuestas")
        lines.append("• Estadísticas históricas favorecen esta selección")
        lines.append("• Probabilidad real superior a la implícita")
    elif market_key == 'h2h' or 'ganador' in candidate.get('market', '').lower():
        lines.append("⚽ **Mercado Ganador:**")
        lines.append("• Casa subestima probabilidades del favorito")
        lines.append("• Análisis de forma reciente favorable")
        lines.append("• Value bet confirmado por algoritmo avanzado")
    elif market_key == 'totals' or 'total' in candidate.get('market', '').lower():
        lines.append("📊 **Mercado Totales:**")
        lines.append("• Línea de puntos mal establecida")
        lines.append("• Estadísticas ofensivas/defensivas favorables")
        lines.append("• Patrón histórico confirma tendencia")
    
    lines.append("")
    lines.append("✅ **RECOMENDACIÓN PREMIUM:** APOSTAR CON CONFIANZA")
    lines.append("🎯 **Nivel de confianza:** ALTO (Value bet confirmado)")
    
    # Análisis crítico de alineaciones para Premium usando sistema especializado
    lines.append("")
    lineup_analysis = get_lineup_section(candidate, is_premium=True)
    lines.extend(lineup_analysis)
    
    # Optimización de cuotas mejorada para Premium
    lines.append("")
    lines.append("💰 **ESTRATEGIA DE OPTIMIZACIÓN:**")
    lines.append("🔍 **Paso 1:** Verifica esta cuota en 3-5 casas diferentes")
    lines.append("📈 **Paso 2:** Busca mejoras de 0.03-0.10 puntos")
    lines.append("💎 **Paso 3:** Cada 0.05 de mejora = +5% más ganancia")
    lines.append("🏆 **Objetivo:** Maximizar ROI en cada apuesta value")
    lines.append("")
    lines.append("🎯 **ESTRATEGIA CONSERVADORA (Mayor % Acierto):**")
    lines.append("📊 **Opción A:** Busca cuotas más pequeñas del mismo pronóstico")
    lines.append("🔧 **Opción B:** Ajusta líneas de hándicap más conservadoras")
    lines.append("✅ **Opción C:** Acomoda la apuesta para menor riesgo")
    lines.append("📈 **Resultado:** Menor ganancia pero mayor porcentaje de aciertos")
    lines.append("🎲 **Balance:** Tú decides entre más ganancia vs más aciertos")
    
    if candidate.get('edge_percent', 0) > 0:
        lines.append(f"🎯 **Ventaja:** +{candidate['edge_percent']:.1f}%")
    
    lines.append("")
    
    # Analytics avanzados (si existen)
    if candidate.get('vig'):
        lines.append("🔍 **INTELIGENCIA DE MERCADO:**")
        lines.append(f"📈 **Vig:** {candidate.get('vig', 0):.2f}%")
        
        if candidate.get('efficiency', 0) > 0:
            lines.append(f"⚙️ **Eficiencia:** {candidate['efficiency']:.2f}")
        
        if candidate.get('consensus_mean', 0) > 0:
            consensus_diff = candidate.get('consensus_diff_pct', 0)
            lines.append(f"🌐 **Media mercado:** {candidate['consensus_mean']:.2f}")
            lines.append(f"📊 **Diferencia:** {consensus_diff:+.1f}%")
        
        if candidate.get('moved'):
            lines.append(f"📈 **Movimiento:** {candidate.get('movement_direction', 'N/A')}")
        
        lines.append("")
    
    # Recomendación de stake
    lines.append("💰 **GESTIÓN DE BANKROLL:**")
    bankroll = getattr(user, 'dynamic_bank', getattr(user, 'bankroll', 1000))
    lines.append(f"💵 **Bankroll actual:** ${bankroll:.2f}")
    lines.append(f"🎯 **Stake:** 10% (${stake:.2f})")
    
    # Score final
    if candidate.get('final_score', 0) > 0:
        lines.append("")
        lines.append(f"⭐ **SCORE ALGORITMO:** {candidate['final_score']:.2f}/5.0")
        if candidate['final_score'] >= 4.0:
            lines.append("🔥 **CALIFICACIÓN:** EXCELENTE - Alta probabilidad de éxito")
        elif candidate['final_score'] >= 3.0:
            lines.append("✅ **CALIFICACIÓN:** BUENA - Apuesta recomendada")
        else:
            lines.append("⚠️ **CALIFICACIÓN:** MODERADA - Apostar con cautela")
    
    lines.append("")
    lines.append("🎯 **¡Buena suerte y que las probabilidades estén a tu favor!**")
    lines.append("")
    lines.append("💡 **RECUERDA:** Busca mejores cuotas en otras casas para maximizar ganancias")
    lines.append("🔧 **CONSEJO:** Ajusta a cuotas más conservadoras si prefieres mayor % de aciertos")
    
    return "\n".join(lines)


def format_limits_reached_message(user) -> str:
    """
    Mensaje cuando el usuario alcanza su límite diario.
    """
    lines = []
    lines.append("⏸️ **LÍMITE DIARIO ALCANZADO**")
    lines.append("")
    
    if user.is_premium_active():
        lines.append("Has recibido todas las alertas premium de hoy.")
        lines.append("Mañana recibirás nuevas oportunidades.")
    else:
        lines.append("⏸️  Has alcanzado tu límite de 1 alerta diaria.")
        lines.append("")
        lines.append("🌟 UPGRADE A PREMIUM para recibir ALERTAS ILIMITADAS con:")
        lines.append("• 📊 Análisis completo de valor")
        lines.append("• 💰 Stakes calculados profesionalmente")
        lines.append("• 📈 ROI tracking automatizado")
        lines.append("• 🎯 Alertas en tiempo real")
        lines.append("")
        lines.append("💬 Contacta para más información")
    
    return "\n".join(lines)


def format_stats_message(user) -> str:
    """
    Formato de estadísticas del usuario.
    """
    lines = []
    lines.append("📊 **ESTADÍSTICAS PERSONALES**")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    
    # Estado de cuenta
    if user.is_premium_active():
        lines.append("💎 **USUARIO PREMIUM**")
        if user.suscripcion_fin:
            lines.append(f"⏰ **Expira:** {user.suscripcion_fin}")
        lines.append("✨ Alertas ILIMITADAS")
    else:
        lines.append("🆓 **Usuario Gratuito**")
        lines.append("• 1 alerta diaria")
        lines.append("• Análisis básico")
    
    lines.append("")
    lines.append(f"📬 Alertas restantes hoy: {max(0, user.get_remaining_alerts())}/{user.get_max_alerts()}")
    
    # Stats premium
    if user.is_premium_active():
        # Bank dinámico semanal
        user.reset_dynamic_bank_if_needed()
        lines.append(f"💶 Bank dinámico semanal: {getattr(user, 'dynamic_bank', 200.0):.2f} €")
        lines.append(f"💸 Stake fijo por pronóstico: 10.00 €")
        # Bankroll real
        lines.append(f"💰 Bankroll actual: ${getattr(user, 'bankroll', 1000):.2f}")
        # ROI y aciertos (si existen)
        if hasattr(user, 'roi'):
            lines.append(f"📈 ROI acumulado: {user.roi:.2f}%")
        if hasattr(user, 'bets_won') and hasattr(user, 'bets_placed'):
            lines.append(f"🎯 Apuestas ganadas: {user.bets_won}/{user.bets_placed}")
            if user.bets_placed > 0:
                win_rate = (user.bets_won / user.bets_placed) * 100
                lines.append(f"📊 Tasa de acierto: {win_rate:.1f}%")
    
    return "\n".join(lines)