"""notifier/alert_formatter.py - Formatea mensajes diferenciados para usuarios gratuitos y premium.
"""
from typing import Dict
import sys
from pathlib import Path

# Asegurar que utils esté en el path
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.sport_translator import translate_sport, translate_market
from utils.lineup_analyzer import get_lineup_section


def escape_html(text: str) -> str:
    """
    Escapa caracteres especiales para HTML de Telegram.
    """
    if not text:
        return text
    # Escapar & < > " para HTML
    text = str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    return text


def get_market_info(market_key: str, selection: str, point, odd: float) -> Dict:
    """
    Obtiene información formateada del mercado incluyendo player props y period markets.
    
    Returns:
        Dict con 'type', 'description', 'details' para formatear alertas
    """
    info = {'type': '', 'description': '', 'details': []}
    
    # Player props (estadísticas de jugadores)
    if market_key.startswith('player_'):
        stat_type = translate_market(market_key)
        player_name = selection.split(' - ')[0] if ' - ' in selection else selection
        over_under = "OVER" if "over" in selection.lower() else "UNDER"
        
        info['type'] = f"📊 {stat_type}"
        info['description'] = f"🏀 <b>Jugador:</b> {escape_html(player_name)}"
        if point is not None:
            info['details'].append(f"   🎯 <b>Apuesta:</b> {over_under} {point} {stat_type.lower()}")
            info['details'].append(f"   💰 <b>Cuota:</b> {odd:.2f}")
            if over_under == "OVER":
                info['details'].append(f"   ℹ️ <b>Significa:</b> {player_name} debe hacer MÁS de {point} {stat_type.lower()}")
            else:
                info['details'].append(f"   ℹ️ <b>Significa:</b> {player_name} debe hacer MENOS de {point} {stat_type.lower()}")
        return info
    
    # Period markets - Quarters
    if '_q' in market_key:
        quarter = market_key[-1]  # '1', '2', '3', '4'
        base_market = market_key.rsplit('_', 1)[0]  # 'h2h', 'spreads', 'totals'
        period_name = f"{quarter}{'er' if quarter == '1' else 'do' if quarter == '2' else 'er' if quarter == '3' else 'to'} Cuarto"
        
        if base_market == 'h2h':
            info['type'] = f"🏀 Ganador {period_name}"
            info['description'] = f"   🎯 <b>Apuesta:</b> {escape_html(selection)} gana el {period_name}"
            info['details'].append(f"   💰 <b>Cuota:</b> {odd:.2f}")
        elif base_market == 'spreads':
            info['type'] = f"📊 Hándicap {period_name}"
            info['description'] = f"   ⚽ <b>Equipo:</b> {escape_html(selection)}"
            if point is not None:
                info['details'].append(f"   📊 <b>Línea:</b> {point:+.1f} puntos en el {period_name}")
                info['details'].append(f"   💰 <b>Cuota:</b> {odd:.2f}")
        elif base_market == 'totals':
            over_under = "OVER" if "over" in selection.lower() else "UNDER"
            info['type'] = f"📊 Total {period_name}"
            if point is not None:
                info['description'] = f"   🎯 <b>Apuesta:</b> {over_under} {point} puntos en el {period_name}"
                info['details'].append(f"   💰 <b>Cuota:</b> {odd:.2f}")
        return info
    
    # Period markets - Halves
    if '_h' in market_key and market_key[-1] in ['1', '2']:
        half = market_key[-1]
        base_market = market_key.rsplit('_', 1)[0]
        period_name = f"{'1era' if half == '1' else '2da'} Mitad"
        
        if base_market == 'h2h':
            info['type'] = f"⚽ Ganador {period_name}"
            info['description'] = f"   🎯 <b>Apuesta:</b> {escape_html(selection)} gana la {period_name}"
            info['details'].append(f"   💰 <b>Cuota:</b> {odd:.2f}")
        elif base_market == 'spreads':
            info['type'] = f"📊 Hándicap {period_name}"
            info['description'] = f"   ⚽ <b>Equipo:</b> {escape_html(selection)}"
            if point is not None:
                info['details'].append(f"   📊 <b>Línea:</b> {point:+.1f} puntos en la {period_name}")
                info['details'].append(f"   💰 <b>Cuota:</b> {odd:.2f}")
        elif base_market == 'totals':
            over_under = "OVER" if "over" in selection.lower() else "UNDER"
            info['type'] = f"📊 Total {period_name}"
            if point is not None:
                info['description'] = f"   🎯 <b>Apuesta:</b> {over_under} {point} puntos en la {period_name}"
                info['details'].append(f"   💰 <b>Cuota:</b> {odd:.2f}")
        return info
    
    # Standard markets (original logic)
    if market_key == 'h2h':
        info['type'] = "⚽ GANADOR DEL PARTIDO"
        info['description'] = f"   🎯 <b>Apuesta:</b> {escape_html(selection)}"
        info['details'].append(f"   💰 <b>Cuota:</b> {odd:.2f}")
    elif market_key == 'spreads':
        info['type'] = "🎯 HÁNDICAP"
        info['description'] = f"   ⚽ <b>Equipo:</b> {escape_html(selection)}"
        if point is not None:
            info['details'].append(f"   📊 <b>Línea:</b> {point:+.1f} puntos")
            info['details'].append(f"   💰 <b>Cuota:</b> {odd:.2f}")
            info['details'].append("")
            if point > 0:
                info['details'].append(f"   ℹ️ <b>Significa:</b> {escape_html(selection)} puede PERDER hasta {abs(point)} puntos y GANAS")
            else:
                info['details'].append(f"   ℹ️ <b>Significa:</b> {escape_html(selection)} debe GANAR por MÁS de {abs(point)} puntos")
    elif market_key == 'totals':
        over_under = "OVER" if "over" in selection.lower() else "UNDER"
        info['type'] = "📊 TOTAL DE PUNTOS"
        if point is not None:
            info['description'] = f"   🎯 <b>Apuesta:</b> {over_under} {point} puntos"
            info['details'].append(f"   💰 <b>Cuota:</b> {odd:.2f}")
            info['details'].append("")
            if over_under == "OVER":
                info['details'].append(f"   ℹ️ <b>Significa:</b> Marcador TOTAL debe ser MAYOR a {point} puntos")
            else:
                info['details'].append(f"   ℹ️ <b>Significa:</b> Marcador TOTAL debe ser MENOR a {point} puntos")
    
    return info



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
    event_name = escape_html(candidate.get('event', 'N/A'))
    lines.append(f"🎯 <b>{sport_es.upper()}</b>")
    lines.append(f"⚽ <b>{event_name}</b>")
    lines.append("")
    
    # Información detallada del mercado con formato claro
    market = escape_html(candidate.get('market', 'N/A'))
    market_key = candidate.get('market_key', '')
    selection = escape_html(candidate['selection'])
    odd = candidate['odds']
    bookmaker = escape_html(candidate.get('bookmaker', 'N/A'))
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
    lines.append("📋 <b>APUESTA:</b>")
    lines.append(f"   🏆 <b>Partido:</b> {event_name}")
    lines.append("")

    # Usar el helper para formatear el mercado
    market_info = get_market_info(market_key, selection, point, odd)
    lines.append(f"   {market_info['type']}")
    if market_info['description']:
        lines.append(market_info['description'])
    lines.extend(market_info['details'])

    lines.append("")
    lines.append(f"🏠 <b>Casa de apuestas:</b> {bookmaker}")
    
    # Mostrar si se usó casa estándar
    if candidate.get('was_bet365_adjusted'):
        original_odds_val = candidate.get('original_odds')
        original_bm = escape_html(candidate.get('original_bookmaker', 'N/A'))
        lines.append("")
        lines.append(f"💎 <b>Cuota ajustada a casa estándar:</b>")
        lines.append(f"   {original_bm}: @ {original_odds_val:.2f}")
        lines.append(f"   {bookmaker}: @ {odd:.2f} ✅")

    # --- PICK EXPLICADO ---
    lines.append("")
    lines.append("📝 <b>PICK EXPLICADO:</b>")
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
        lines.append(f"💎 <b>VALOR:</b> {value:.3f}")
    
    if candidate.get('edge_percent', 0) > 0:
        lines.append(f"🎯 <b>VENTAJA:</b> +{candidate['edge_percent']:.1f}%")
    
    # Análisis detallado del pronóstico
    lines.append("")
    lines.append("🔍 <b>ANÁLISIS DETALLADO:</b>")
    
    if candidate.get('real_probability', 0) > 0:
        real_prob_pct = candidate['real_probability'] * 100
        implied_prob_pct = (100/candidate['odds'])
        lines.append(f"📊 <b>Probabilidad real:</b> {real_prob_pct:.0f}%")
        lines.append(f"📉 <b>Prob. implícita casa:</b> {implied_prob_pct:.0f}%")
        lines.append(f"💎 <b>Diferencia a tu favor:</b> +{real_prob_pct - implied_prob_pct:.1f}%")
    
    # Análisis específico del mercado
    market_key = candidate.get('market_key', '')
    if market_key == 'spreads' or 'hándicap' in candidate.get('market', '').lower():
        lines.append("🎯 <b>Tipo:</b> Hándicap - Línea favorable según estadísticas")
    elif market_key == 'h2h' or 'ganador' in candidate.get('market', '').lower():
        lines.append("⚽ <b>Tipo:</b> Ganador - Probabilidad subestimada por el mercado")
    elif market_key == 'totals' or 'total' in candidate.get('market', '').lower():
        lines.append("📊 <b>Tipo:</b> Totales - Línea mal calibrada por la casa")
    
    lines.append("✅ <b>Recomendación:</b> APOSTAR - Value bet confirmado")
    
    # Análisis de alineaciones usando sistema especializado
    lines.append("")
    lineup_analysis = get_lineup_section(candidate, is_premium=False)
    lines.extend(lineup_analysis)
    
    # Nota sobre mejora de cuotas
    lines.append("")
    lines.append("💡 <b>OPTIMIZA TUS GANANCIAS:</b>")
    lines.append("🔍 Busca esta misma apuesta en otras casas")
    lines.append("📈 Puedes encontrar cuotas mejores (hasta 0.05-0.10 más)")
    lines.append("💰 Cada 0.05 de mejora = +5% más ganancia")
    lines.append("")
    lines.append("🎯 <b>MEJORA TU % DE ACIERTO:</b>")
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
    market = escape_html(candidate.get('market', 'N/A'))
    market_key = candidate.get('market_key', '')
    selection = escape_html(candidate['selection'])
    odd = candidate['odds']
    bookmaker = escape_html(candidate.get('bookmaker', 'N/A'))
    original_bookmaker = bookmaker
    
    # Obtener equipos con fallback
    home = candidate.get('home', candidate.get('home_team', ''))
    away = candidate.get('away', candidate.get('away_team', ''))
    
    # Si no hay equipos, intentar construir desde el event
    if not home or not away:
        event_name = candidate.get('event', '')
        if ' vs ' in event_name:
            parts = event_name.split(' vs ')
            if len(parts) == 2:
                home = parts[0].strip()
                away = parts[1].strip()
    
    # Si TODAVÍA no hay equipos, usar sport como fallback
    if not home or not away:
        event_name = escape_html(f"{sport_es.upper()} - {selection}")
    else:
        event_name = escape_html(f"{home} vs {away}")
    
    point = candidate.get('point')

    # Detectar tipo de mercado si no viene market_key
    if not market_key:
        if 'spread' in market.lower() or 'handicap' in market.lower() or 'hándicap' in market.lower():
            market_key = 'spreads'
        elif 'total' in market.lower() or 'over' in selection.lower() or 'under' in selection.lower():
            market_key = 'totals'
        else:
            market_key = 'h2h'

    lines.append(f"🎯 <b>{sport_es.upper()}</b>")
    lines.append(f"⚽ <b>{event_name}</b>")
    lines.append("")
    lines.append("📋 <b>APUESTA RECOMENDADA:</b>")

    # Usar el helper para formatear el mercado
    market_info = get_market_info(market_key, selection, point, odd)
    lines.append(f"   {market_info['type']}")
    if market_info['description']:
        lines.append(market_info['description'])
    lines.extend(market_info['details'])

    lines.append("")
    lines.append(f"🏠 <b>Casa recomendada:</b> {original_bookmaker}")
    
    # Mostrar si se usó William Hill (casa estándar)
    if candidate.get('was_bet365_adjusted'):
        original_odds_val = candidate.get('original_odds')
        original_bm = escape_html(candidate.get('original_bookmaker', 'N/A'))
        lines.append("")
        lines.append(f"💎 <b>Cuota ajustada a casa estándar:</b>")
        lines.append(f"   {original_bm}: @ {original_odds_val:.2f}")
        lines.append(f"   {bookmaker}: @ {odd:.2f} ✅")
        if odd < original_odds_val:
            lines.append(f"   ℹ️ Cuota más conservadora y confiable")
    
    # Mostrar si la línea fue ajustada (handicap/total)
    if candidate.get('was_adjusted'):
        original_odds_val = candidate.get('original_odds')
        original_point_val = candidate.get('original_point')
        lines.append("")
        lines.append(f"🔧 <b>Línea ajustada automáticamente:</b>")
        if original_point_val is not None:
            lines.append(f"   Original: {selection} {original_point_val} @ {original_odds_val:.2f}")
            lines.append(f"   Ajustada: {selection} {point} @ {odd:.2f}")
        else:
            lines.append(f"   Original: @ {original_odds_val:.2f}")
            lines.append(f"   Ajustada: @ {odd:.2f}")
        lines.append(f"   💡 Línea más conservadora para mejor control")

    # --- PICK EXPLICADO ---
    lines.append("")
    lines.append("📝 <b>PICK EXPLICADO:</b>")
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
        lines.append(f"⏰ <b>INICIO:</b> {commence_str}")

    lines.append("")

    # Métricas de valor
    lines.append("📈 <b>ANÁLISIS PROFESIONAL DE VALOR:</b>")
    
    if candidate.get('real_probability', 0) > 0:
        real_prob_pct = candidate['real_probability'] * 100
        lines.append(f"✅ <b>Prob. Real:</b> {real_prob_pct:.1f}%")
    
    if candidate.get('implied_probability', 0) > 0:
        implied_prob_pct = candidate['implied_probability'] * 100
        lines.append(f"📉 <b>Prob. Implícita:</b> {implied_prob_pct:.1f}%")
        prob_diff = real_prob_pct - implied_prob_pct
        if prob_diff > 0:
            lines.append(f"⚡ <b>Ventaja detectada:</b> +{prob_diff:.1f}% a tu favor")
    
    if candidate.get('value', 0) > 0:
        lines.append(f"💎 <b>Valor:</b> {candidate['value']:.3f} (Ganancia esperada: {((candidate['value']-1)*100):.1f}%)")
    
    # Análisis detallado específico del mercado
    lines.append("")
    lines.append("🔍 <b>ANÁLISIS TÉCNICO DETALLADO:</b>")
    
    market_key = candidate.get('market_key', '')
    if market_key == 'spreads' or 'hándicap' in candidate.get('market', '').lower():
        lines.append("🎯 <b>Mercado Hándicap:</b>")
        lines.append("• Línea mal calibrada por la casa de apuestas")
        lines.append("• Estadísticas históricas favorecen esta selección")
        lines.append("• Probabilidad real superior a la implícita")
    elif market_key == 'h2h' or 'ganador' in candidate.get('market', '').lower():
        lines.append("⚽ <b>Mercado Ganador:</b>")
        lines.append("• Casa subestima probabilidades del favorito")
        lines.append("• Análisis de forma reciente favorable")
        lines.append("• Value bet confirmado por algoritmo avanzado")
    elif market_key == 'totals' or 'total' in candidate.get('market', '').lower():
        lines.append("📊 <b>Mercado Totales:</b>")
        lines.append("• Línea de puntos mal establecida")
        lines.append("• Estadísticas ofensivas/defensivas favorables")
        lines.append("• Patrón histórico confirma tendencia")
    
    lines.append("")
    lines.append("✅ <b>RECOMENDACIÓN PREMIUM:</b> APOSTAR CON CONFIANZA")
    lines.append("🎯 <b>Nivel de confianza:</b> ALTO (Value bet confirmado)")
    
    # Análisis crítico de alineaciones para Premium usando sistema especializado
    lines.append("")
    lineup_analysis = get_lineup_section(candidate, is_premium=True)
    lines.extend(lineup_analysis)
    
    # Optimización de cuotas mejorada para Premium
    lines.append("")
    lines.append("💰 <b>ESTRATEGIA DE OPTIMIZACIÓN:</b>")
    lines.append("🔍 <b>Paso 1:</b> Verifica esta cuota en 3-5 casas diferentes")
    lines.append("📈 <b>Paso 2:</b> Busca mejoras de 0.03-0.10 puntos")
    lines.append("💎 <b>Paso 3:</b> Cada 0.05 de mejora = +5% más ganancia")
    lines.append("🏆 <b>Objetivo:</b> Maximizar ROI en cada apuesta value")
    lines.append("")
    lines.append("🎯 <b>ESTRATEGIA CONSERVADORA (Mayor % Acierto):</b>")
    lines.append("📊 <b>Opción A:</b> Busca cuotas más pequeñas del mismo pronóstico")
    lines.append("🔧 <b>Opción B:</b> Ajusta líneas de hándicap más conservadoras")
    lines.append("✅ <b>Opción C:</b> Acomoda la apuesta para menor riesgo")
    lines.append("📈 <b>Resultado:</b> Menor ganancia pero mayor porcentaje de aciertos")
    lines.append("🎲 <b>Balance:</b> Tú decides entre más ganancia vs más aciertos")
    
    if candidate.get('edge_percent', 0) > 0:
        lines.append(f"🎯 <b>Ventaja:</b> +{candidate['edge_percent']:.1f}%")
    
    lines.append("")
    
    # Analytics avanzados (si existen)
    if candidate.get('vig'):
        lines.append("🔍 <b>INTELIGENCIA DE MERCADO:</b>")
        lines.append(f"📈 <b>Vig:</b> {candidate.get('vig', 0):.2f}%")
        
        if candidate.get('efficiency', 0) > 0:
            lines.append(f"⚙️ <b>Eficiencia:</b> {candidate['efficiency']:.2f}")
        
        if candidate.get('consensus_mean', 0) > 0:
            consensus_diff = candidate.get('consensus_diff_pct', 0)
            lines.append(f"🌐 <b>Media mercado:</b> {candidate['consensus_mean']:.2f}")
            lines.append(f"📊 <b>Diferencia:</b> {consensus_diff:+.1f}%")
        
        if candidate.get('moved'):
            lines.append(f"📈 <b>Movimiento:</b> {candidate.get('movement_direction', 'N/A')}")
        
        lines.append("")
    
    # Recomendación de stake
    lines.append("💰 <b>GESTIÓN DE BANKROLL:</b>")
    bankroll = getattr(user, 'dynamic_bank', getattr(user, 'bankroll', 1000))
    lines.append(f"💵 <b>Bankroll actual:</b> ${bankroll:.2f}")
    lines.append(f"🎯 <b>Stake:</b> 10% (${stake:.2f})")
    
    # Score final
    if candidate.get('final_score', 0) > 0:
        lines.append("")
        lines.append(f"⭐ <b>SCORE ALGORITMO:</b> {candidate['final_score']:.2f}/5.0")
        if candidate['final_score'] >= 4.0:
            lines.append("🔥 <b>CALIFICACIÓN:</b> EXCELENTE - Alta probabilidad de éxito")
        elif candidate['final_score'] >= 3.0:
            lines.append("✅ <b>CALIFICACIÓN:</b> BUENA - Apuesta recomendada")
        else:
            lines.append("⚠️ <b>CALIFICACIÓN:</b> MODERADA - Apostar con cautela")
    
    lines.append("")
    lines.append("🎯 <b>¡Buena suerte y que las probabilidades estén a tu favor!</b>")
    lines.append("")
    lines.append("💡 <b>RECUERDA:</b> Busca mejores cuotas en otras casas para maximizar ganancias")
    lines.append("🔧 <b>CONSEJO:</b> Ajusta a cuotas más conservadoras si prefieres mayor % de aciertos")
    
    return "\n".join(lines)


def format_limits_reached_message(user) -> str:
    """
    Mensaje cuando el usuario alcanza su límite diario.
    """
    lines = []
    lines.append("⏸️ <b>LÍMITE DIARIO ALCANZADO</b>")
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
    lines.append("📊 <b>ESTADÍSTICAS PERSONALES</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    
    # Estado de cuenta
    if user.is_premium_active():
        lines.append("💎 <b>USUARIO PREMIUM</b>")
        if user.suscripcion_fin:
            lines.append(f"⏰ <b>Expira:</b> {user.suscripcion_fin}")
        lines.append("✨ Alertas ILIMITADAS")
    else:
        lines.append("🆓 <b>Usuario Gratuito</b>")
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
