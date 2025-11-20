"""
data/users.py - Sistema de gestión de usuarios gratuitos y premium.

Maneja:
- Niveles de usuario (free/premium)
- Límites de alertas diarias por nivel
- Bankroll management para usuarios premium
- Sistema de referidos con recompensas
- Persistencia en JSON
"""
import json
import os
import random
import string
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
from zoneinfo import ZoneInfo
from pathlib import Path


# Configuración de límites - SISTEMA PREMIUM EXCLUSIVO
ALERTS_FREE = 0  # Free users: sin alertas
ALERTS_PREMIUM = 5  # Premium users: máximo 5 alertas de calidad por día

# Configuración de bankroll (para premium)
DEFAULT_BANKROLL = float(os.getenv("DEFAULT_BANKROLL", "1000.0"))
FRACTION_KELLY = float(os.getenv("FRACTION_KELLY", "0.25"))  # 1/4 Kelly
FIXED_PERCENTAGE = float(os.getenv("FIXED_PERCENTAGE", "2.0"))  # 2% del bankroll
STAKE_METHOD = os.getenv("STAKE_METHOD", "fixed_percentage")  # "kelly" o "fixed_percentage"

# Configuración de referidos
REFERRALS_FOR_PREMIUM_WEEK = int(os.getenv("REFERRALS_FOR_PREMIUM_WEEK", "5"))  # 5 referidos = 1 semana premium
PREMIUM_WEEK_DAYS = 7  # Duración de una semana premium

# Configuración de comisiones (NUEVO SISTEMA)
PREMIUM_PRICE_EUR = float(os.getenv("PREMIUM_PRICE_EUR", "15.0"))  # 15€ semanales
PREMIUM_PRICE_USD = PREMIUM_PRICE_EUR  # Alias para compatibilidad (mismo valor en €)
COMMISSION_PERCENTAGE = float(os.getenv("COMMISSION_PERCENTAGE", "10.0"))  # 10% comisión
PAID_REFERRALS_FOR_FREE_WEEK = int(os.getenv("PAID_REFERRALS_FOR_FREE_WEEK", "3"))  # 3 referidos pagos = 1 semana gratis

# Zona horaria para reset diario
RESET_TIMEZONE = ZoneInfo("America/New_York")
RESET_HOUR = 6  # 6 AM Eastern


class User:
    """Representa un usuario del sistema."""
    
    def __init__(
        self, 
        chat_id: str,
        username: str = None,
        nivel: str = "gratis",
        bankroll: float = DEFAULT_BANKROLL,
        initial_bankroll: float = DEFAULT_BANKROLL,
        alerts_sent_today: int = 0,
        last_reset_date: str = None,
        total_bets: int = 0,
        won_bets: int = 0,
        total_profit: float = 0.0,
        bet_history: List[Dict] = None,
        # Campos de referidos (sistema anterior)
        referral_code: str = None,
        referrer_id: str = None,
        referred_users: List[str] = None,
        premium_weeks_earned: int = 0,
        premium_expires_at: str = None,
        is_permanent_premium: bool = False,
        # Campos de comisiones (NUEVO SISTEMA)
        referrals_paid: int = 0,
        saldo_comision: float = 0.0,
        suscripcion_fin: str = None,
        total_commission_earned: float = 0.0,
        free_weeks_earned: int = 0,
        # Bank dinámico semanal
        dynamic_bank: float = 200.0,
        dynamic_bank_last_reset: str = None,
        # Sistema de pago semanal (20% de ganancias)
        week_start_bank: float = 200.0,
        weekly_profit: float = 0.0,
        weekly_fee_due: float = 0.0,
        weekly_fee_paid: bool = False,
        base_fee_paid: bool = False,
        week_start_date: str = None
    ):
        self.chat_id = chat_id
        self.username = username
        self.nivel = nivel.lower()  # "gratis" o "premium"
        self.bankroll = bankroll
        self.initial_bankroll = initial_bankroll
        self.alerts_sent_today = alerts_sent_today
        self.last_reset_date = last_reset_date or self._get_current_date()
        self.total_bets = total_bets
        self.won_bets = won_bets
        self.total_profit = total_profit
        self.bet_history = bet_history or []
        
        # Sistema de referidos (anterior - mantener compatibilidad)
        self.referral_code = referral_code or self._generate_referral_code()
        self.referrer_id = referrer_id  # ID del usuario que me refirió
        self.referred_users = referred_users or []  # Lista de IDs que he referido
        self.referrals = self.referred_users  # Alias para compatibilidad
        self.premium_weeks_earned = premium_weeks_earned
        self.premium_expires_at = premium_expires_at
        self.is_permanent_premium = is_permanent_premium
        
        # Sistema de comisiones (NUEVO)
        self.referrals_paid = referrals_paid  # Cantidad de referidos que pagaron
        self.saldo_comision = saldo_comision  # Saldo acumulado en USD
        self.accumulated_balance = saldo_comision  # Alias para compatibilidad (20% de ganancias)
        self.suscripcion_fin = suscripcion_fin  # Fecha fin de suscripción ISO
        self.total_commission_earned = total_commission_earned  # Total ganado histórico
        self.free_weeks_earned = free_weeks_earned  # Semanas gratis por referidos pagos

        # Bank dinámico semanal
        self.dynamic_bank = dynamic_bank
        self.dynamic_bank_last_reset = dynamic_bank_last_reset or self._get_current_date()
        
        # Sistema de pago semanal (20% de ganancias)
        self.week_start_bank = week_start_bank
        self.weekly_profit = weekly_profit
        self.weekly_fee_due = weekly_fee_due
        self.weekly_fee_paid = weekly_fee_paid
        self.base_fee_paid = base_fee_paid
        self.week_start_date = week_start_date or self._get_current_date()
    
    def _get_current_date(self) -> str:
        """Obtiene la fecha actual en formato YYYY-MM-DD en timezone configurado."""
        now = datetime.now(RESET_TIMEZONE)
        return now.strftime("%Y-%m-%d")
    
    def _generate_referral_code(self) -> str:
        """Genera un código de referido único de 8 caracteres."""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    def _check_premium_expiration(self):
        """Verifica si el premium temporal ha expirado."""
        if self.premium_expires_at and not self.is_permanent_premium:
            expiry_date = datetime.fromisoformat(self.premium_expires_at)
            current_date = datetime.now(timezone.utc)
            
            if current_date >= expiry_date:
                # Premium expirado, degradar a gratis
                self.nivel = "gratis"
                self.premium_expires_at = None
                return True  # Indica que expiró
        return False
    
    def is_premium_active(self) -> bool:
        """Verifica si el usuario tiene premium activo (permanente o temporal)."""
        if self.is_permanent_premium:
            return True
        
        if self.premium_expires_at:
            expiry_date = datetime.fromisoformat(self.premium_expires_at)
            current_date = datetime.now(timezone.utc)
            return current_date < expiry_date
        
        return self.nivel == "premium"
    
    def add_premium_week(self):
        """Agrega una semana de premium por referidos."""
        current_date = datetime.now(timezone.utc)
        
        if self.premium_expires_at:
            # Si ya tiene premium temporal, extender desde la fecha actual de expiración
            expiry_date = datetime.fromisoformat(self.premium_expires_at)
            if expiry_date > current_date:
                # Extiende desde la fecha de expiración existente
                new_expiry = expiry_date + timedelta(days=PREMIUM_WEEK_DAYS)
            else:
                # Si ya expiró, empieza desde ahora
                new_expiry = current_date + timedelta(days=PREMIUM_WEEK_DAYS)
        else:
            # Primera semana premium
            new_expiry = current_date + timedelta(days=PREMIUM_WEEK_DAYS)
        
        self.premium_expires_at = new_expiry.isoformat()
        self.premium_weeks_earned += 1
        self.nivel = "premium"
    
    # ================================
    # SISTEMA DE COMISIONES (NUEVO)
    # ================================
    
    def add_paid_referral(self, payment_amount: float) -> Dict:
        """
        Procesa un pago de referido y calcula comisión.
        
        Args:
            payment_amount: Monto pagado por el referido en USD
            
        Returns:
            Dict con información del proceso: {
                'commission': float,
                'new_balance': float,
                'earned_free_week': bool,
                'total_paid_referrals': int
            }
        """
        # Calcular comisión (10% del pago)
        commission = payment_amount * (COMMISSION_PERCENTAGE / 100)
        
        # Actualizar saldos
        self.saldo_comision += commission
        self.total_commission_earned += commission
        self.referrals_paid += 1
        
        # Verificar si gana semana gratis (cada 3 referidos pagos)
        earned_free_week = (self.referrals_paid % PAID_REFERRALS_FOR_FREE_WEEK) == 0
        
        if earned_free_week:
            self.add_free_premium_week()
            self.free_weeks_earned += 1
        
        return {
            'commission': commission,
            'new_balance': self.saldo_comision,
            'earned_free_week': earned_free_week,
            'total_paid_referrals': self.referrals_paid,
            'payment_amount': payment_amount
        }
    
    def add_free_premium_week(self):
        """Agrega una semana de premium gratis por referidos pagos."""
        current_date = datetime.now(timezone.utc)
        
        if self.suscripcion_fin:
            # Si ya tiene suscripción activa, extender desde la fecha actual
            expiry_date = datetime.fromisoformat(self.suscripcion_fin)
            if expiry_date > current_date:
                # Extiende desde la fecha de expiración existente
                new_expiry = expiry_date + timedelta(days=7)
            else:
                # Si ya expiró, empieza desde ahora
                new_expiry = current_date + timedelta(days=7)
        else:
            # Primera semana premium
            new_expiry = current_date + timedelta(days=7)
        
        self.suscripcion_fin = new_expiry.isoformat()
        self.nivel = "premium"
    
    def process_premium_payment(self, amount: float) -> Dict:
        """
        Procesa un pago de suscripción premium.
        
        Args:
            amount: Monto pagado en USD
            
        Returns:
            Dict con información del pago
        """
        current_date = datetime.now(timezone.utc)
        
        # Calcular nueva fecha de fin (1 semana desde ahora)
        new_expiry = current_date + timedelta(days=7)
        
        # Si ya tiene suscripción activa, extender
        if self.suscripcion_fin:
            expiry_date = datetime.fromisoformat(self.suscripcion_fin)
            if expiry_date > current_date:
                new_expiry = expiry_date + timedelta(days=7)
        
        self.suscripcion_fin = new_expiry.isoformat()
        self.nivel = "premium"
        
        # Procesar comisión para el referidor si existe
        referrer_commission = None
        if self.referrer_id:
            referrer_commission = {
                'referrer_id': self.referrer_id,
                'amount': amount
            }
        
        return {
            'user_id': self.chat_id,
            'amount_paid': amount,
            'subscription_end': self.suscripcion_fin,
            'referrer_commission': referrer_commission
        }
    
    def pagar_comision(self) -> float:
        """
        Procesa el retiro de comisiones.
        
        Returns:
            Monto retirado (el saldo anterior)
        """
        amount_paid = self.saldo_comision
        self.saldo_comision = 0.0
        return amount_paid
    
    def is_subscription_active(self) -> bool:
        """Verifica si la suscripción está activa."""
        if not self.suscripcion_fin:
            return False
            
        expiry_date = datetime.fromisoformat(self.suscripcion_fin)
        current_date = datetime.now(timezone.utc)
        return current_date < expiry_date
    
    def get_commission_stats(self) -> Dict:
        """Obtiene estadísticas de comisiones."""
        return {
            'saldo_actual': self.saldo_comision,
            'total_ganado': self.total_commission_earned,
            'referidos_pagos': self.referrals_paid,
            'semanas_gratis': self.free_weeks_earned,
            'subscription_active': self.is_subscription_active(),
            'subscription_end': self.suscripcion_fin,
            'referidos_para_proxima_semana': PAID_REFERRALS_FOR_FREE_WEEK - (self.referrals_paid % PAID_REFERRALS_FOR_FREE_WEEK)
        }
    
    def _check_reset(self):
        """Verifica si debe resetear el contador diario (a las 6 AM Eastern)."""
        current_date = self._get_current_date()
        
        if current_date != self.last_reset_date:
            self.alerts_sent_today = 0
            self.last_reset_date = current_date
            return True
        return False
    
    def can_send_alert(self) -> bool:
        """Verifica si el usuario puede recibir más alertas hoy - SOLO PREMIUM."""
        self._check_reset()
        self._check_premium_expiration()  # Verificar si premium expiró
        
        # Admin siempre puede recibir alertas (sin límites)
        ADMIN_ID = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
        if str(self.chat_id) == str(ADMIN_ID):
            return True
        
        # NUEVO SISTEMA: Solo usuarios premium reciben alertas
        if self.is_premium_active():
            return self.alerts_sent_today < ALERTS_PREMIUM  # Máximo 5 de calidad
        else:  
            # Usuarios gratuitos NO reciben alertas, solo pueden suscribirse
            return False
    
    def record_alert_sent(self):
        """Registra que se envió una alerta."""
        self.alerts_sent_today += 1
    
    def get_max_alerts(self) -> int:
        """Retorna el límite de alertas para este usuario - SOLO PREMIUM."""
        # Admin sin límites
        ADMIN_ID = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
        if str(self.chat_id) == str(ADMIN_ID):
            return 999  # Sin límite para admin
        
        return ALERTS_PREMIUM if self.is_premium_active() else 0  # Solo premium recibe alertas
    
    def get_remaining_alerts(self) -> int:
        """Retorna cuántas alertas puede recibir hoy."""
        self._check_reset()
        return self.get_max_alerts() - self.alerts_sent_today
    
    def calculate_stake(self, odd: float, prob: float) -> float:
        """
        Calcula el stake recomendado para usuarios premium.
        
        Args:
            odd: Cuota de la apuesta
            prob: Probabilidad estimada (0-1)
        
        Returns:
            Stake en unidades monetarias
        """
        if self.nivel != "premium":
            return 0.0
        
        if STAKE_METHOD == "kelly":
            # Criterio de Kelly: f = (p*odd - 1) / (odd - 1)
            # Aplicamos fracción para reducir riesgo
            kelly_fraction = ((prob * odd) - 1) / (odd - 1)
            kelly_fraction = max(0, min(kelly_fraction, 0.5))  # Cap entre 0 y 50%
            stake = self.bankroll * kelly_fraction * FRACTION_KELLY
        else:  # fixed_percentage
            stake = self.bankroll * (FIXED_PERCENTAGE / 100)
        
        # Mínimo 1, máximo 10% del bankroll
        min_stake = 1.0
        max_stake = self.bankroll * 0.10
        
        return max(min_stake, min(stake, max_stake))
    
    def update_bankroll(self, bet_result: Dict):
        """
        Actualiza el bankroll tras el resultado de una apuesta.
        
        Args:
            bet_result: {
                'stake': float,
                'odd': float,
                'won': bool,
                'selection': str,
                'event': str,
                'date': str
            }
        """
        if self.nivel != "premium":
            return
        
        stake = bet_result.get('stake', 0)
        odd = bet_result.get('odd', 0)
        won = bet_result.get('won', False)
        
        if won:
            profit = stake * (odd - 1)
            self.bankroll += profit
            self.total_profit += profit
            self.won_bets += 1
        else:
            self.bankroll -= stake
            self.total_profit -= stake
        
        self.total_bets += 1
        self.bet_history.append(bet_result)
        
        # Mantener solo últimas 100 apuestas en history
        if len(self.bet_history) > 100:
            self.bet_history = self.bet_history[-100:]

        # Actualizar bank dinámico también
        self.update_dynamic_bank(bet_result)
    
    def update_dynamic_bank(self, bet_result: Dict):
        """
        Actualiza el bank dinámico semanal (200€ base) según resultados.
        Cada apuesta es 10% del bank actual.
        """
        if self.nivel != "premium":
            return
        
        stake = bet_result.get('stake', 0)
        odd = bet_result.get('odd', 0)
        won = bet_result.get('won', False)
        
        if won:
            profit = stake * (odd - 1)
            self.dynamic_bank += profit
        else:
            self.dynamic_bank -= stake
        
        # No permitir bank negativo
        if self.dynamic_bank < 0:
            self.dynamic_bank = 0
    
    def calculate_weekly_stats(self):
        """
        Calcula las estadísticas de la semana:
        - Ganancia/pérdida total (dynamic_bank - 200€)
        - 20% adeudado si hubo ganancia
        """
        if self.nivel != "premium":
            return
        
        # Calcular profit de la semana
        self.weekly_profit = self.dynamic_bank - self.week_start_bank
        
        # Si hubo ganancia, calcular 20%
        if self.weekly_profit > 0:
            self.weekly_fee_due = self.weekly_profit * 0.20
        else:
            self.weekly_fee_due = 0.0
        
        # Resetear flags de pago
        self.weekly_fee_paid = False
        self.base_fee_paid = False
    
    def reset_weekly_cycle(self):
        """
        Reinicia el ciclo semanal (cada lunes):
        - Calcula stats finales de la semana
        - Reinicia dynamic_bank a 200€
        - Actualiza fecha de inicio
        """
        if self.nivel != "premium":
            return
        
        # Calcular stats antes de resetear
        self.calculate_weekly_stats()
        
        # Resetear bank a 200€
        self.week_start_bank = 200.0
        self.dynamic_bank = 200.0
        self.week_start_date = self._get_current_date()
        self.dynamic_bank_last_reset = self._get_current_date()
    
    def mark_base_fee_paid(self):
        """Marca el pago base de 15€ como pagado."""
        self.base_fee_paid = True
    
    def mark_weekly_fee_paid(self):
        """Marca el 20% de ganancias como pagado."""
        self.weekly_fee_paid = True
    
    def get_payment_status(self) -> Dict:
        """Retorna el estado de pagos del usuario."""
        return {
            'base_fee': PREMIUM_PRICE_EUR,
            'base_paid': self.base_fee_paid,
            'weekly_profit': self.weekly_profit,
            'weekly_fee_due': self.weekly_fee_due,
            'weekly_fee_paid': self.weekly_fee_paid,
            'total_due': PREMIUM_PRICE_EUR if not self.base_fee_paid else 0 + (self.weekly_fee_due if not self.weekly_fee_paid else 0),
            'dynamic_bank_current': self.dynamic_bank,
            'week_start_bank': self.week_start_bank
        }
    
    def get_weekly_payment(self) -> float:
        """Calcula el pago total semanal: 15€ base + 20% de ganancias referidos."""
        base = PREMIUM_PRICE_EUR  # 15€
        referral_bonus = self.accumulated_balance  # 20% de ganancias de referidos
        return base + referral_bonus
    
    def get_stats(self):
        """Retorna estadísticas del usuario premium."""
        if self.nivel != "premium" or self.total_bets == 0:
            return {}
        
        win_rate = (self.won_bets / self.total_bets) * 100
        roi = (self.total_profit / self.initial_bankroll) * 100
        
        return {
            'nivel': self.nivel,
            'bankroll_actual': self.bankroll,
            'bankroll_inicial': self.initial_bankroll,
            'total_apuestas': self.total_bets,
            'ganadas': self.won_bets,
            'perdidas': self.total_bets - self.won_bets,
            'win_rate': win_rate,
            'profit_total': self.total_profit,
            'roi': roi,
            'alertas_hoy': self.alerts_sent_today,
            'max_alertas': self.get_max_alerts()
        }
    
    def to_dict(self) -> Dict:
        """Serializa a diccionario."""
        return {
            'chat_id': self.chat_id,
            'username': self.username,
            'nivel': self.nivel,
            'bankroll': self.bankroll,
            'initial_bankroll': self.initial_bankroll,
            'alerts_sent_today': self.alerts_sent_today,
            'last_reset_date': self.last_reset_date,
            'total_bets': self.total_bets,
            'won_bets': self.won_bets,
            'total_profit': self.total_profit,
            'bet_history': self.bet_history,
            # Campos de referidos (sistema anterior)
            'referral_code': self.referral_code,
            'referrer_id': self.referrer_id,
            'referred_users': self.referred_users,
            'premium_weeks_earned': self.premium_weeks_earned,
            'premium_expires_at': self.premium_expires_at,
            'is_permanent_premium': self.is_permanent_premium,
            # Campos de comisiones (NUEVO SISTEMA)
            'referrals_paid': self.referrals_paid,
            'saldo_comision': self.saldo_comision,
            'suscripcion_fin': self.suscripcion_fin,
            'total_commission_earned': self.total_commission_earned,
            'free_weeks_earned': self.free_weeks_earned,
            # Bank dinámico y sistema de pagos semanales
            'dynamic_bank': self.dynamic_bank,
            'dynamic_bank_last_reset': self.dynamic_bank_last_reset,
            'week_start_bank': self.week_start_bank,
            'weekly_profit': self.weekly_profit,
            'weekly_fee_due': self.weekly_fee_due,
            'weekly_fee_paid': self.weekly_fee_paid,
            'base_fee_paid': self.base_fee_paid,
            'week_start_date': self.week_start_date
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'User':
        """Deserializa desde diccionario."""
        return User(**data)


class UsersManager:
    """Gestor de usuarios con persistencia en JSON."""
    
    def __init__(self, storage_path: str = "data/users.json"):
        self.storage_path = Path(storage_path)
        self.users: Dict[str, User] = {}
        self.load()
    
    def load(self):
        """Carga usuarios desde archivo JSON."""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.users = {
                chat_id: User.from_dict(user_data)
                for chat_id, user_data in data.items()
            }
        except Exception as e:
            print(f"⚠️  Error cargando usuarios: {e}")
    
    def save(self):
        """Guarda usuarios a archivo JSON."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                chat_id: user.to_dict()
                for chat_id, user in self.users.items()
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Error guardando usuarios: {e}")
    
    def get_user(self, chat_id: str, referrer_code: str = None) -> User:
        """Obtiene o crea un usuario, procesando código de referido si es nuevo."""
        if chat_id not in self.users:
            # Nuevo usuario
            user = User(chat_id=chat_id, nivel="gratis")
            
            # Procesar referido si hay código
            if referrer_code:
                referrer = self.find_user_by_referral_code(referrer_code)
                if referrer and referrer.chat_id != chat_id:  # No auto-referirse
                    user.referrer_id = referrer.chat_id
                    referrer.referred_users.append(chat_id)
                    
                    # Verificar si el referidor gana semana premium
                    if len(referrer.referred_users) % REFERRALS_FOR_PREMIUM_WEEK == 0:
                        referrer.add_premium_week()
                        # Retornar información para notificar
                        user._referrer_earned_reward = True
                        user._referrer_weeks = referrer.premium_weeks_earned
            
            self.users[chat_id] = user
            self.save()
        
        return self.users[chat_id]
    
    def find_user_by_referral_code(self, code: str) -> Optional[User]:
        """Busca un usuario por su código de referido."""
        for user in self.users.values():
            if user.referral_code == code:
                return user
        return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Busca un usuario por su username de Telegram."""
        username_lower = username.lower().replace("@", "")
        for user in self.users.values():
            if user.username and user.username.lower() == username_lower:
                return user
        return None
    
    def add_user(self, chat_id: str, username: str, nivel: str = "gratis") -> User:
        """Crea un nuevo usuario y lo guarda."""
        user = User(chat_id=chat_id, username=username, nivel=nivel)
        self.users[chat_id] = user
        self.save()
        return user
    
    def save_users(self):
        """Alias para self.save() para compatibilidad."""
        self.save()
    
    def get_referral_stats(self, chat_id: str) -> Dict:
        """Obtiene estadísticas de referidos para un usuario."""
        user = self.get_user(chat_id)
        
        # Calcular días restantes de premium
        days_left = 0
        if user.premium_expires_at:
            expiry_date = datetime.fromisoformat(user.premium_expires_at)
            current_date = datetime.now(timezone.utc)
            if expiry_date > current_date:
                days_left = (expiry_date - current_date).days
        
        return {
            'referral_code': user.referral_code,
            'total_referidos': len(user.referred_users),
            'semanas_ganadas': user.premium_weeks_earned,
            'referidos_para_proxima': REFERRALS_FOR_PREMIUM_WEEK - (len(user.referred_users) % REFERRALS_FOR_PREMIUM_WEEK),
            'premium_activo': user.is_premium_active(),
            'premium_permanente': user.is_permanent_premium,
            'premium_dias_restantes': days_left,
            'referidos_recientes': user.referred_users[-5:] if user.referred_users else []  # Últimos 5
        }
    
    def upgrade_to_premium(self, chat_id: str, initial_bankroll: float = DEFAULT_BANKROLL):
        """Actualiza un usuario a premium."""
        user = self.get_user(chat_id)
        user.nivel = "premium"
        user.bankroll = initial_bankroll
        user.initial_bankroll = initial_bankroll
        self.save()
    
    def downgrade_to_free(self, chat_id: str):
        """Degrada un usuario a gratuito."""
        user = self.get_user(chat_id)
        user.nivel = "gratis"
        self.save()
    
    def get_all_users_by_level(self, nivel: str) -> List[User]:
        """Obtiene todos los usuarios de un nivel específico."""
        return [u for u in self.users.values() if u.nivel == nivel]
    
    def reset_all_alerts(self):
        """Resetea contadores de alertas para todos los usuarios (llamar a las 6 AM)."""
        for user in self.users.values():
            user._check_reset()
        self.save()


# Singleton global
_users_manager = None


def get_users_manager(storage_path: str = "data/users.json") -> UsersManager:
    """Obtiene la instancia global del UsersManager."""
    global _users_manager
    if _users_manager is None:
        _users_manager = UsersManager(storage_path)
    return _users_manager
