from database import get_connection

conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
print('✅ Tablas creadas en PostgreSQL:')
for row in cursor.fetchall():
    print(f"  - {row['table_name']}")
cursor.close()
conn.close()
