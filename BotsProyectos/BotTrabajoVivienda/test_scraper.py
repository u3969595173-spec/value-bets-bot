"""
Script de prueba para el scraper de trabajos
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.job_scraper import search_jobs
from database.db import save_jobs
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    print("=" * 60)
    print("🔍 PRUEBA DE SCRAPER DE TRABAJOS")
    print("=" * 60)
    
    # Palabras clave populares para inmigrantes
    test_searches = [
        ("camarero", "Madrid"),
        ("limpieza", "Barcelona"),
        ("repartidor", "Valencia"),
        ("almacen sin experiencia", "España")
    ]
    
    for keywords, location in test_searches:
        print(f"\n📍 Buscando: '{keywords}' en {location}")
        print("-" * 60)
        
        jobs = search_jobs(keywords, location, max_results=10)
        
        print(f"\n✅ Encontrados {len(jobs)} trabajos")
        
        # Mostrar primeros 3 resultados
        for i, job in enumerate(jobs[:3], 1):
            print(f"\n{i}. {job['title']}")
            print(f"   🏢 {job['company']}")
            print(f"   📍 {job['location']}")
            if job.get('salary'):
                print(f"   💰 {job['salary']}")
            print(f"   🔗 {job['url']}")
            if job.get('special_tags'):
                print(f"   🏷️  Tags: {', '.join(job['special_tags'])}")
            print(f"   📡 Fuente: {job['source']}")
        
        # Guardar en base de datos
        if jobs:
            saved = save_jobs(jobs)
            print(f"\n💾 Guardados {saved} trabajos nuevos en la base de datos")
        
        print("-" * 60)
        input("\nPresiona ENTER para continuar con la siguiente búsqueda...")
    
    print("\n" + "=" * 60)
    print("✅ PRUEBA COMPLETADA")
    print("=" * 60)

if __name__ == '__main__':
    main()
