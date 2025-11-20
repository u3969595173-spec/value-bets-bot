"""
reset_stats.py - Script para resetear estadísticas del bot a 0

Elimina todas las predicciones de Supabase
"""
import os
from dotenv import load_dotenv
from data.historical_db import historical_db
from analytics.performance_tracker import performance_tracker

load_dotenv()

def reset_statistics():
    """Resetea todas las estadísticas eliminando predicciones"""
    try:
        print("⚠️  ADVERTENCIA: Esto eliminará TODAS las predicciones guardadas")
        confirm = input("¿Estás seguro? (escribe 'SI' para confirmar): ")
        
        if confirm != "SI":
            print("❌ Operación cancelada")
            return
        
        print("\n🗑️  Eliminando predicciones...")
        
        # Eliminar todas las predicciones
        response = historical_db.supabase.table('predictions').delete().neq('id', 0).execute()
        
        print(f"✅ Eliminadas todas las predicciones")
        print(f"📊 Estadísticas reseteadas a 0")
        
        # Verificar
        stats = performance_tracker.get_global_stats(days=365)
        print(f"\n✅ Verificación:")
        print(f"   Total predicciones: {stats['total_predictions']}")
        print(f"   Aciertos: {stats['won']}")
        print(f"   Fallos: {stats['lost']}")
        print(f"   Win rate: {stats['win_rate']:.1f}%")
        print(f"   ROI: {stats['roi']:.1f}%")
        print(f"   Profit: ${stats['total_profit']:.2f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    reset_statistics()
