"""
Módulo de conexión a PostgreSQL
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')

def get_connection():
    """Obtener conexión a la base de datos"""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"Error conectando a PostgreSQL: {e}")
        raise

def init_database():
    """Inicializar tablas de la base de datos"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Tabla de usuarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                is_premium BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de búsquedas guardadas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                search_type VARCHAR(20) NOT NULL, -- 'trabajo' o 'vivienda'
                keywords TEXT NOT NULL,
                location VARCHAR(255),
                filters JSONB, -- Filtros especiales: sin_papeles, sin_nomina, etc.
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de alertas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                search_id INTEGER REFERENCES searches(id) ON DELETE CASCADE,
                result_id INTEGER, -- ID del resultado (job o housing)
                result_type VARCHAR(20), -- 'trabajo' o 'vivienda'
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                was_opened BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Tabla de ofertas de trabajo scrapeadas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                company VARCHAR(255),
                location VARCHAR(255),
                salary VARCHAR(255),
                description TEXT,
                url TEXT UNIQUE NOT NULL,
                source VARCHAR(100) NOT NULL, -- 'indeed', 'infojobs', etc.
                posted_date TIMESTAMP,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                special_tags JSONB -- sin_papeles, sin_experiencia, etc.
            )
        """)
        
        # Tabla de ofertas de vivienda scrapeadas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS housing (
                id SERIAL PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                price DECIMAL(10, 2),
                location VARCHAR(255),
                bedrooms INTEGER,
                bathrooms INTEGER,
                size_m2 INTEGER,
                description TEXT,
                url TEXT UNIQUE NOT NULL,
                source VARCHAR(100) NOT NULL, -- 'idealista', 'fotocasa', etc.
                posted_date TIMESTAMP,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                special_tags JSONB -- sin_nomina, acepta_extranjeros, etc.
            )
        """)
        
        # Índices para búsquedas rápidas
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_searches_user_id ON searches(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_user_id ON alerts(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at ON jobs(scraped_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_housing_scraped_at ON housing(scraped_at)")
        
        conn.commit()
        logger.info("✅ Base de datos inicializada correctamente")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error inicializando base de datos: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def get_or_create_user(user_id, username=None, first_name=None):
    """Obtener o crear usuario en la base de datos"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Intentar obtener usuario
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        if user:
            # Actualizar last_active
            cursor.execute(
                "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = %s",
                (user_id,)
            )
            conn.commit()
            return dict(user)
        
        # Crear nuevo usuario
        cursor.execute(
            """
            INSERT INTO users (user_id, username, first_name)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (user_id, username, first_name)
        )
        user = cursor.fetchone()
        conn.commit()
        logger.info(f"✅ Nuevo usuario creado: {user_id}")
        return dict(user)
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error en get_or_create_user: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def save_search(user_id, search_type, keywords, location=None, filters=None):
    """Guardar una búsqueda del usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """
            INSERT INTO searches (user_id, search_type, keywords, location, filters)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, search_type, keywords, location, filters)
        )
        search_id = cursor.fetchone()['id']
        conn.commit()
        logger.info(f"✅ Búsqueda guardada: {search_id}")
        return search_id
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error guardando búsqueda: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def get_user_searches(user_id):
    """Obtener búsquedas activas de un usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """
            SELECT * FROM searches 
            WHERE user_id = %s AND is_active = TRUE
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        searches = cursor.fetchall()
        return [dict(s) for s in searches]
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo búsquedas: {e}")
        return []
    finally:
        cursor.close()
        conn.close()
