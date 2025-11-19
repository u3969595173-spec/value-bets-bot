"""
referrals/referral_system.py - Sistema completo de referidos y recompensas

Características:
- Enlaces únicos de referido por usuario
- Registro automático de referidos
- Recompensas por referidos que pagan Premium
- Sistema de saldo virtual
- Prevención de fraudes y auto-referidos
- Historial completo de transacciones
- Integración con sistema Premium
"""

import json
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ReferralSystem:
    """
    Sistema completo de gestión de referidos y recompensas
    """
    
    # Configuración de recompensas
    COMMISSION_PERCENTAGE = 10.0  # 10% de comisión por referido
    PREMIUM_PRICE_EUR = 15.0  # Precio semanal de Premium (euros)
    PREMIUM_PRICE_USD = 15.0  # Precio semanal de Premium (euros, misma moneda)
    FREE_WEEK_THRESHOLD = 3  # 3 referidos pagos = 1 semana gratis
    REWARD_PER_REFERRAL = PREMIUM_PRICE_USD * (COMMISSION_PERCENTAGE / 100)  # 1.5€ por referido
    
    def __init__(self, data_file: str = "data/referrals.json"):
        """
        Args:
            data_file: Ruta al archivo JSON de referidos
        """
        self.data_file = data_file
        self.referrals = {}  # user_id -> referral_data
        self.transactions = []  # Lista de todas las transacciones
        self._load_data()
        
        logger.info(f"ReferralSystem inicializado: {len(self.referrals)} usuarios")
    
    def _load_data(self):
        """Carga datos de referidos desde archivo"""
        path = Path(self.data_file)
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.referrals = data.get('referrals', {})
                    self.transactions = data.get('transactions', [])
                logger.info(f"Datos cargados: {len(self.referrals)} usuarios, {len(self.transactions)} transacciones")
            except Exception as e:
                logger.error(f"Error cargando datos de referidos: {e}")
                self.referrals = {}
                self.transactions = []
        else:
            self.referrals = {}
            self.transactions = []
            path.parent.mkdir(parents=True, exist_ok=True)
    
    def _save_data(self):
        """Guarda datos de referidos a archivo"""
        try:
            path = Path(self.data_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    'last_updated': datetime.now(timezone.utc).isoformat(),
                    'total_users': len(self.referrals),
                    'total_transactions': len(self.transactions),
                    'referrals': self.referrals,
                    'transactions': self.transactions
                }, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Datos guardados: {len(self.referrals)} usuarios")
        except Exception as e:
            logger.error(f"Error guardando datos de referidos: {e}")
    
    def generate_referral_code(self, user_id: str) -> str:
        """
        Genera un código único de referido para un usuario
        
        Args:
            user_id: ID del usuario
            
        Returns:
            str: Código de referido único
        """
        # Usar hash del user_id + timestamp + salt para único
        salt = secrets.token_hex(4)
        raw = f"{user_id}_{datetime.now(timezone.utc).timestamp()}_{salt}"
        hash_code = hashlib.sha256(raw.encode()).hexdigest()[:12].upper()
        
        # Verificar que no exista (muy improbable pero seguro)
        while any(r.get('code') == hash_code for r in self.referrals.values()):
            salt = secrets.token_hex(4)
            raw = f"{user_id}_{datetime.now(timezone.utc).timestamp()}_{salt}"
            hash_code = hashlib.sha256(raw.encode()).hexdigest()[:12].upper()
        
        return hash_code
    
    def register_user(self, user_id: str, referrer_code: Optional[str] = None) -> Dict:
        """
        Registra un nuevo usuario en el sistema de referidos
        
        Args:
            user_id: ID del usuario nuevo
            referrer_code: Código del usuario que lo refirió (opcional)
            
        Returns:
            Dict con información del registro
        """
        # Verificar si ya está registrado
        if user_id in self.referrals:
            logger.warning(f"Usuario {user_id} ya está registrado")
            return {
                'success': False,
                'reason': 'Usuario ya registrado',
                'referral_code': self.referrals[user_id]['code']
            }
        
        # Generar código único
        code = self.generate_referral_code(user_id)
        
        # Buscar referrer si se proporcionó código
        referrer_id = None
        if referrer_code:
            referrer_id = self._find_user_by_code(referrer_code)
            
            # Validar que no sea auto-referido
            if referrer_id == user_id:
                logger.warning(f"Intento de auto-referido detectado: {user_id}")
                referrer_id = None
        
        # Crear registro de usuario
        user_data = {
            'user_id': user_id,
            'code': code,
            'referrer_id': referrer_id,
            'referred_users': [],  # IDs de usuarios referidos
            'referred_paid': [],  # IDs de referidos que pagaron
            'total_referrals': 0,
            'paid_referrals': 0,
            'balance_usd': 0.0,
            'total_earned': 0.0,
            'free_weeks_earned': 0,
            'registered_at': datetime.now(timezone.utc).isoformat(),
            'last_reward_date': None
        }
        
        self.referrals[user_id] = user_data
        
        # Si tiene referrer, actualizar su lista
        if referrer_id:
            if referrer_id in self.referrals:
                self.referrals[referrer_id]['referred_users'].append(user_id)
                self.referrals[referrer_id]['total_referrals'] += 1
                
                logger.info(f"Usuario {user_id} referido por {referrer_id}")
                
                # Registrar transacción
                self._add_transaction(
                    user_id=referrer_id,
                    transaction_type='referral_registered',
                    amount=0.0,
                    referred_user=user_id,
                    description=f"Nuevo referido registrado: {user_id}"
                )
        
        self._save_data()
        
        return {
            'success': True,
            'referral_code': code,
            'referral_link': self.get_referral_link(code),
            'referred_by': referrer_id
        }
    
    def _find_user_by_code(self, code: str) -> Optional[str]:
        """
        Encuentra el user_id por código de referido
        
        Args:
            code: Código de referido
            
        Returns:
            user_id o None si no se encuentra
        """
        for user_id, data in self.referrals.items():
            if data.get('code') == code:
                return user_id
        return None
    
    def get_referral_link(self, code: str, bot_username: str = "Valueapuestasbot") -> str:
        """
        Genera el enlace de referido completo
        
        Args:
            code: Código de referido
            bot_username: Username del bot de Telegram
            
        Returns:
            str: URL completa del enlace de referido
        """
        return f"https://t.me/{bot_username}?start={code}"
    
    def process_premium_payment(
        self,
        user_id: str,
        amount_usd: float,
        payment_method: str = "manual"
    ) -> Dict:
        """
        Procesa un pago Premium y otorga recompensas al referrer
        
        Args:
            user_id: ID del usuario que pagó
            amount_usd: Monto pagado en USD
            payment_method: Método de pago
            
        Returns:
            Dict con información del procesamiento
        """
        if user_id not in self.referrals:
            logger.warning(f"Usuario {user_id} no está en sistema de referidos")
            return {
                'success': False,
                'reason': 'Usuario no registrado en sistema de referidos'
            }
        
        user_data = self.referrals[user_id]
        referrer_id = user_data.get('referrer_id')
        
        # Si no tiene referrer, no hay recompensa
        if not referrer_id or referrer_id not in self.referrals:
            logger.info(f"Usuario {user_id} pagó pero no tiene referrer válido")
            return {
                'success': True,
                'reward_granted': False,
                'reason': 'Sin referrer'
            }
        
        # Verificar si ya se procesó este pago antes (evitar duplicados)
        if user_id in self.referrals[referrer_id].get('referred_paid', []):
            logger.warning(f"Pago de {user_id} ya fue procesado antes")
            return {
                'success': False,
                'reason': 'Pago ya procesado anteriormente'
            }
        
        # Calcular comisión
        commission = amount_usd * (self.COMMISSION_PERCENTAGE / 100)
        
        # Actualizar datos del referrer
        referrer_data = self.referrals[referrer_id]
        referrer_data['referred_paid'].append(user_id)
        referrer_data['paid_referrals'] += 1
        referrer_data['balance_usd'] += commission
        referrer_data['total_earned'] += commission
        referrer_data['last_reward_date'] = datetime.now(timezone.utc).isoformat()
        
        # Verificar si gana semana gratis
        free_week_granted = False
        if referrer_data['paid_referrals'] % self.FREE_WEEK_THRESHOLD == 0:
            referrer_data['free_weeks_earned'] += 1
            free_week_granted = True
        
        # Registrar transacción
        self._add_transaction(
            user_id=referrer_id,
            transaction_type='commission_earned',
            amount=commission,
            referred_user=user_id,
            description=f"Comisión por pago Premium de referido {user_id}: ${amount_usd:.2f}"
        )
        
        if free_week_granted:
            self._add_transaction(
                user_id=referrer_id,
                transaction_type='free_week_earned',
                amount=self.PREMIUM_PRICE_USD,
                referred_user=None,
                description=f"Semana Premium gratis ganada ({referrer_data['paid_referrals']} referidos pagos)"
            )
        
        self._save_data()
        
        logger.info(
            f"Recompensa otorgada a {referrer_id}: ${commission:.2f} "
            f"({referrer_data['paid_referrals']} referidos pagos)"
        )
        
        return {
            'success': True,
            'reward_granted': True,
            'referrer_id': referrer_id,
            'commission': commission,
            'new_balance': referrer_data['balance_usd'],
            'paid_referrals': referrer_data['paid_referrals'],
            'free_week_granted': free_week_granted,
            'free_weeks_total': referrer_data['free_weeks_earned']
        }
    
    def _add_transaction(
        self,
        user_id: str,
        transaction_type: str,
        amount: float,
        referred_user: Optional[str] = None,
        description: str = ""
    ):
        """Registra una transacción en el historial"""
        transaction = {
            'id': len(self.transactions) + 1,
            'user_id': user_id,
            'type': transaction_type,
            'amount': amount,
            'referred_user': referred_user,
            'description': description,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        self.transactions.append(transaction)
    
    def get_user_stats(self, user_id: str) -> Optional[Dict]:
        """
        Obtiene estadísticas de referidos de un usuario
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Dict con estadísticas o None si no existe
        """
        if user_id not in self.referrals:
            return None
        
        data = self.referrals[user_id]
        
        return {
            'referral_code': data['code'],
            'referral_link': self.get_referral_link(data['code']),
            'total_referrals': data['total_referrals'],
            'paid_referrals': data['paid_referrals'],
            'pending_referrals': data['total_referrals'] - data['paid_referrals'],
            'balance_usd': data['balance_usd'],
            'total_earned': data['total_earned'],
            'free_weeks_earned': data['free_weeks_earned'],
            'free_weeks_pending': data['free_weeks_earned'] - self._count_redeemed_weeks(user_id),
            'next_free_week_in': self.FREE_WEEK_THRESHOLD - (data['paid_referrals'] % self.FREE_WEEK_THRESHOLD),
            'registered_at': data['registered_at'],
            'last_reward': data['last_reward_date']
        }
    
    def _count_redeemed_weeks(self, user_id: str) -> int:
        """Cuenta cuántas semanas gratis ha canjeado el usuario"""
        redeemed = 0
        for tx in self.transactions:
            if tx['user_id'] == user_id and tx['type'] == 'free_week_redeemed':
                redeemed += 1
        return redeemed
    
    def redeem_free_week(self, user_id: str) -> Tuple[bool, str]:
        """
        Canjea una semana gratis ganada por referidos
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        if user_id not in self.referrals:
            return False, "Usuario no registrado"
        
        data = self.referrals[user_id]
        redeemed = self._count_redeemed_weeks(user_id)
        available = data['free_weeks_earned'] - redeemed
        
        if available <= 0:
            return False, "No tienes semanas gratis disponibles"
        
        # Registrar canje
        self._add_transaction(
            user_id=user_id,
            transaction_type='free_week_redeemed',
            amount=self.PREMIUM_PRICE_USD,
            description="Semana Premium gratis canjeada"
        )
        
        self._save_data()
        
        logger.info(f"Usuario {user_id} canjeó 1 semana gratis ({available-1} restantes)")
        
        return True, f"Semana Premium gratis activada! Te quedan {available-1} disponibles"
    
    def withdraw_balance(self, user_id: str, amount: float) -> Tuple[bool, str]:
        """
        Procesa un retiro de saldo (requiere aprobación admin)
        
        Args:
            user_id: ID del usuario
            amount: Monto a retirar
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        if user_id not in self.referrals:
            return False, "Usuario no registrado"
        
        data = self.referrals[user_id]
        
        if amount <= 0:
            return False, "Monto inválido"
        
        if amount > data['balance_usd']:
            return False, f"Saldo insuficiente (disponible: ${data['balance_usd']:.2f})"
        
        # Registrar solicitud de retiro
        self._add_transaction(
            user_id=user_id,
            transaction_type='withdrawal_requested',
            amount=amount,
            description=f"Solicitud de retiro de ${amount:.2f}"
        )
        
        self._save_data()
        
        logger.info(f"Usuario {user_id} solicitó retiro de ${amount:.2f}")
        
        return True, f"Solicitud de retiro de ${amount:.2f} registrada. Contacta al admin para procesar."
    
    def approve_withdrawal(self, user_id: str, amount: float, admin_id: str) -> Tuple[bool, str]:
        """
        Aprueba un retiro (solo admin)
        
        Args:
            user_id: ID del usuario
            amount: Monto aprobado
            admin_id: ID del admin que aprueba
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        if user_id not in self.referrals:
            return False, "Usuario no registrado"
        
        data = self.referrals[user_id]
        
        if amount > data['balance_usd']:
            return False, f"Saldo insuficiente"
        
        # Descontar del saldo
        data['balance_usd'] -= amount
        
        # Registrar retiro aprobado
        self._add_transaction(
            user_id=user_id,
            transaction_type='withdrawal_approved',
            amount=-amount,
            description=f"Retiro aprobado por admin {admin_id}: ${amount:.2f}"
        )
        
        self._save_data()
        
        logger.info(f"Retiro de ${amount:.2f} aprobado para {user_id} por admin {admin_id}")
        
        return True, f"Retiro de ${amount:.2f} procesado exitosamente"
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """
        Obtiene el ranking de usuarios por referidos
        
        Args:
            limit: Número máximo de usuarios a retornar
            
        Returns:
            Lista de usuarios ordenados por referidos pagos
        """
        ranked = []
        
        for user_id, data in self.referrals.items():
            ranked.append({
                'user_id': user_id,
                'paid_referrals': data['paid_referrals'],
                'total_referrals': data['total_referrals'],
                'total_earned': data['total_earned'],
                'balance': data['balance_usd']
            })
        
        # Ordenar por referidos pagos (descendente)
        ranked.sort(key=lambda x: x['paid_referrals'], reverse=True)
        
        return ranked[:limit]
    
    def detect_fraud(self, user_id: str) -> Dict:
        """
        Analiza patrones sospechosos de fraude
        
        Args:
            user_id: ID del usuario a analizar
            
        Returns:
            Dict con análisis de fraude
        """
        if user_id not in self.referrals:
            return {'risk_level': 'unknown', 'reasons': ['Usuario no registrado']}
        
        data = self.referrals[user_id]
        risk_factors = []
        risk_score = 0
        
        # Factor 1: Muchos referidos en poco tiempo
        if data['total_referrals'] > 10:
            reg_date = datetime.fromisoformat(data['registered_at'])
            days_since = (datetime.now(timezone.utc) - reg_date).days
            
            if days_since < 7:
                risk_factors.append('Muchos referidos en poco tiempo')
                risk_score += 3
        
        # Factor 2: Tasa de conversión muy alta (sospechoso)
        if data['total_referrals'] > 5:
            conversion_rate = data['paid_referrals'] / data['total_referrals']
            if conversion_rate > 0.8:  # >80% conversión
                risk_factors.append('Tasa de conversión anormalmente alta')
                risk_score += 2
        
        # Factor 3: Todos los referidos pagaron el mismo día
        payment_dates = set()
        for tx in self.transactions:
            if tx['user_id'] == user_id and tx['type'] == 'commission_earned':
                payment_dates.add(tx['timestamp'][:10])  # Solo fecha
        
        if len(payment_dates) == 1 and data['paid_referrals'] > 3:
            risk_factors.append('Todos los pagos en el mismo día')
            risk_score += 3
        
        # Determinar nivel de riesgo
        if risk_score >= 5:
            risk_level = 'HIGH'
        elif risk_score >= 3:
            risk_level = 'MEDIUM'
        elif risk_score >= 1:
            risk_level = 'LOW'
        else:
            risk_level = 'SAFE'
        
        return {
            'user_id': user_id,
            'risk_level': risk_level,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'total_referrals': data['total_referrals'],
            'paid_referrals': data['paid_referrals'],
            'total_earned': data['total_earned']
        }
    
    def generate_report(self) -> str:
        """
        Genera reporte completo del sistema de referidos
        
        Returns:
            str: Reporte formateado
        """
        total_users = len(self.referrals)
        total_referrals = sum(d['total_referrals'] for d in self.referrals.values())
        total_paid = sum(d['paid_referrals'] for d in self.referrals.values())
        total_commissions = sum(d['total_earned'] for d in self.referrals.values())
        total_balance = sum(d['balance_usd'] for d in self.referrals.values())
        
        lines = [
            "="*70,
            "REPORTE DEL SISTEMA DE REFERIDOS",
            "="*70,
            "",
            "ESTADISTICAS GENERALES:",
            f"  Total usuarios: {total_users}",
            f"  Total referidos: {total_referrals}",
            f"  Referidos pagos: {total_paid}",
            f"  Tasa conversión: {(total_paid/total_referrals*100):.1f}%" if total_referrals > 0 else "  Tasa conversión: 0%",
            "",
            "FINANZAS:",
            f"  Comisiones totales: ${total_commissions:.2f}",
            f"  Saldo pendiente: ${total_balance:.2f}",
            f"  Comisiones pagadas: ${total_commissions - total_balance:.2f}",
            "",
            "TOP 5 REFERRERS:",
        ]
        
        leaderboard = self.get_leaderboard(5)
        for i, user in enumerate(leaderboard, 1):
            lines.append(
                f"  #{i}: User {user['user_id'][:8]}... - "
                f"{user['paid_referrals']} pagos, ${user['total_earned']:.2f} ganado"
            )
        
        lines.append("")
        lines.append("="*70)
        
        return "\n".join(lines)


# Funciones helper
def format_referral_stats(stats: Dict) -> str:
    """Formatea estadísticas de referidos para mostrar al usuario"""
    lines = [
        "TUS ESTADISTICAS DE REFERIDOS",
        "="*50,
        "",
        f"Tu código de referido: {stats['referral_code']}",
        f"Tu enlace: {stats['referral_link']}",
        "",
        "REFERIDOS:",
        f"  Total invitados: {stats['total_referrals']}",
        f"  Pagaron Premium: {stats['paid_referrals']}",
        f"  Pendientes: {stats['pending_referrals']}",
        "",
        "GANANCIAS:",
        f"  Saldo actual: ${stats['balance_usd']:.2f}",
        f"  Total ganado: ${stats['total_earned']:.2f}",
        "",
        "SEMANAS GRATIS:",
        f"  Ganadas: {stats['free_weeks_earned']}",
        f"  Disponibles: {stats['free_weeks_pending']}",
        f"  Próxima en: {stats['next_free_week_in']} referidos pagos más",
        "",
        "RECOMPENSAS:",
        f"  Por cada referido que paga: ${ReferralSystem.REWARD_PER_REFERRAL:.2f}",
        f"  Cada {ReferralSystem.FREE_WEEK_THRESHOLD} pagos: 1 semana Premium gratis",
    ]
    
    return "\n".join(lines)


# Ejemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Crear sistema
    system = ReferralSystem("data/test_referrals.json")
    
    # Registrar usuario sin referrer
    result1 = system.register_user("user_123")
    print(f"Usuario 1: {result1}")
    
    # Registrar usuario con referrer
    result2 = system.register_user("user_456", referrer_code=result1['referral_code'])
    print(f"Usuario 2: {result2}")
    
    # Simular pago de user_456
    payment = system.process_premium_payment("user_456", 50.0)
    print(f"\nPago procesado: {payment}")
    
    # Ver stats de user_123 (el referrer)
    stats = system.get_user_stats("user_123")
    print(f"\n{format_referral_stats(stats)}")
    
    # Reporte completo
    print(f"\n{system.generate_report()}")
