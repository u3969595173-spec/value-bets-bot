"""
Script para limpiar usuarios duplicados en Supabase
Solo mantiene el usuario 5901833301
"""
import os
from supabase import create_client, Client

# Configuración de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def clean_supabase():
    """Elimina todos los usuarios excepto 5901833301"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ ERROR: Variables SUPABASE_URL y SUPABASE_KEY no configuradas")
        return
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    try:
        # 1. Ver usuarios actuales
        print("\n📋 Usuarios actuales en Supabase:")
        response = supabase.table('users').select('*').execute()
        for user in response.data:
            print(f"  - {user.get('chat_id')} (@{user.get('username')}) - {user.get('nivel')}")
        
        # 2. Eliminar todos excepto 5901833301
        print("\n🗑️ Eliminando usuarios duplicados...")
        
        # Obtener IDs a eliminar
        users_to_delete = [u['chat_id'] for u in response.data if str(u['chat_id']) != '5901833301']
        deleted_count = 0
        
        for user_id in users_to_delete:
            try:
                supabase.table('users').delete().eq('chat_id', user_id).execute()
                print(f"  ✓ Eliminado: {user_id}")
                deleted_count += 1
            except Exception as e:
                print(f"  ✗ Error eliminando {user_id}: {e}")
        
        print(f"\n✅ Total eliminados: {deleted_count} usuarios")
        
        # 3. Verificar resultado
        print("\n📋 Usuarios finales:")
        final_response = supabase.table('users').select('*').execute()
        for user in final_response.data:
            print(f"  - {user.get('chat_id')} (@{user.get('username')}) - {user.get('nivel')}")
        
        print("\n✅ Limpieza completada")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    clean_supabase()
