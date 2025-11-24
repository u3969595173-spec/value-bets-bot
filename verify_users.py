"""Verificar usuarios en Supabase"""
import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("\n📋 Usuarios en Supabase:")
response = supabase.table('users').select('*').execute()
print(f"Total: {len(response.data)}")
for user in response.data:
    print(f"  - {user.get('chat_id')} (@{user.get('username')}) - {user.get('nivel')}")
