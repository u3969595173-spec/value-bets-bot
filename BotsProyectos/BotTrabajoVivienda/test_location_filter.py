"""Test para ver qué trabajos están pasando el filtro de ubicación"""
from scrapers.job_scraper import JobScraper

scraper = JobScraper()

# Buscar médico en Madrid
print("=" * 70)
print("BUSCANDO: Medico en Madrid")
print("=" * 70)

result = scraper.scrape_all('Medico', 'Madrid', max_per_source=10)

exact_jobs = result.get('exact_matches', [])
location_jobs = result.get('location_only', [])

print(f"\n✅ TRABAJOS EXACTOS (Medico + Madrid): {len(exact_jobs)}")
for i, job in enumerate(exact_jobs, 1):
    print(f"  {i}. {job['title']}")
    print(f"     📍 Ubicación: {job['location']}")
    print(f"     🔗 Fuente: {job['source']}\n")

print(f"\n📍 TRABAJOS SOLO EN MADRID: {len(location_jobs)}")
for i, job in enumerate(location_jobs, 1):
    print(f"  {i}. {job['title']}")
    print(f"     📍 Ubicación: {job['location']}")
    print(f"     🔗 Fuente: {job['source']}\n")

print("=" * 70)
print("ANÁLISIS DE UBICACIONES:")
print("=" * 70)

# Verificar si hay ubicaciones problemáticas
all_jobs = exact_jobs + location_jobs
problem_locations = []

for job in all_jobs:
    loc_lower = job['location'].lower()
    # Buscar ubicaciones que no deberían pasar
    if 'andorra' in loc_lower or 'barcelona' in loc_lower:
        if 'madrid' not in loc_lower:
            problem_locations.append(job)

if problem_locations:
    print(f"\n⚠️  ENCONTRADAS {len(problem_locations)} UBICACIONES INCORRECTAS:")
    for job in problem_locations:
        print(f"  - {job['title']}")
        print(f"    📍 {job['location']} (Fuente: {job['source']})")
else:
    print("\n✅ Todas las ubicaciones son correctas")
