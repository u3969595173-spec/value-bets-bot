"""
Script para limpiar usuarios duplicados en Supabase
Mantiene solo el registro más reciente de cada usuario
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Agregar el directorio raíz al path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

def clean_duplicate_users():
    """Limpia usuarios duplicados en Supabase manteniendo solo el más reciente"""
    
    try:
        from supabase import create_client, Client
        
        SUPABASE_URL = os.getenv('SUPABASE_URL')
        SUPABASE_KEY = os.getenv('SUPABASE_KEY')
        
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("❌ No se encontraron credenciales de Supabase")
            return
        
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Obtener todos los usuarios
        response = supabase.table('users').select('*').execute()
        all_users = response.data
        
        print(f"📊 Total de registros en Supabase: {len(all_users)}")
        
        # Agrupar por chat_id
        users_by_chat_id = {}
        for user in all_users:
            chat_id = user['chat_id']
            if chat_id not in users_by_chat_id:
                users_by_chat_id[chat_id] = []
            users_by_chat_id[chat_id].append(user)
        
        # Buscar duplicados
        duplicates = {k: v for k, v in users_by_chat_id.items() if len(v) > 1}
        
        if not duplicates:
            print("✅ No se encontraron duplicados")
            return
        
        print(f"\n⚠️  DUPLICADOS ENCONTRADOS: {len(duplicates)} usuarios")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        for chat_id, records in duplicates.items():
            print(f"\n👤 Usuario: {chat_id} (@{records[0].get('username', 'N/A')})")
            print(f"   📋 Registros: {len(records)}")
            
            # Ordenar por fecha de actualización (más reciente primero)
            records_sorted = sorted(
                records, 
                key=lambda x: x.get('updated_at', x.get('created_at', '')), 
                reverse=True
            )
            
            # Mantener el más reciente
            keep = records_sorted[0]
            to_delete = records_sorted[1:]
            
            print(f"   ✅ Mantener: {keep.get('created_at')} (más reciente)")
            print(f"   ❌ Eliminar: {len(to_delete)} registros antiguos")
            
            # Eliminar duplicados
            for record in to_delete:
                try:
                    # En Supabase, necesitamos usar un campo único para eliminar
                    # Como chat_id es PRIMARY KEY, podemos buscar por created_at o otro campo
                    supabase.table('users').delete().match({
                        'chat_id': chat_id,
                        'created_at': record['created_at']
                    }).execute()
                    print(f"      🗑️  Eliminado registro: {record['created_at']}")
                except Exception as e:
                    print(f"      ❌ Error eliminando: {e}")
        
        # Verificar resultado
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        response_after = supabase.table('users').select('*').execute()
        print(f"✅ LIMPIEZA COMPLETADA")
        print(f"📊 Registros antes: {len(all_users)}")
        print(f"📊 Registros después: {len(response_after.data)}")
        print(f"🗑️  Registros eliminados: {len(all_users) - len(response_after.data)}")
        
    except ImportError:
        print("❌ Error: Instala supabase-py con: pip install supabase")
    except Exception as e:
        print(f"❌ Error limpiando duplicados: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🧹 LIMPIEZA DE USUARIOS DUPLICADOS EN SUPABASE")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    
    respuesta = input("⚠️  ADVERTENCIA: Esto eliminará registros duplicados de Supabase.\n¿Continuar? (s/n): ")
    
    if respuesta.lower() in ['s', 'si', 'yes', 'y']:
        clean_duplicate_users()
    else:
        print("❌ Operación cancelada")
