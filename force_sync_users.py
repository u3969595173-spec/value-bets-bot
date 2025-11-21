"""Script para forzar sincronización de users.json a Supabase"""
import json
from data.users import UsersManager

# Cargar manager
manager = UsersManager()

# Forzar guardado (sobrescribirá Supabase con datos del JSON local)
manager.save()

print("✅ Sincronización forzada completada")
print(f"📊 Total usuarios: {len(manager.users)}")

# Mostrar referidos de cada usuario
for chat_id, user in manager.users.items():
    refs = len(user.referred_users) if hasattr(user, 'referred_users') else 0
    print(f"  - {user.username or chat_id}: {refs} referidos")
