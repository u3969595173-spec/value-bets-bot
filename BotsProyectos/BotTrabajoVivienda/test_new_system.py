"""Test del nuevo sistema: categoría Y ubicación, con fallback a solo ubicación"""
from scrapers.job_scraper import JobScraper

scraper = JobScraper()

print("=" * 70)
print("TEST: Buscando 'camarero' en Barcelona")
print("=" * 70)

result = scraper.scrape_all('camarero', 'barcelona', max_per_source=10)

exact_matches = result.get('exact_matches', [])
location_only = result.get('location_only', [])

print(f"\n✅ TRABAJOS EXACTOS (camarero + Barcelona): {len(exact_matches)}")
if exact_matches:
    for i, job in enumerate(exact_matches[:5], 1):
        print(f"  {i}. {job['title']} | {job['location']} | {job['source']}")
else:
    print("  (Ninguno encontrado)")

print(f"\n📍 TRABAJOS EN UBICACIÓN (solo Barcelona): {len(location_only)}")
if location_only:
    for i, job in enumerate(location_only[:10], 1):
        print(f"  {i}. {job['title']} | {job['location']} | {job['source']}")
else:
    print("  (Ninguno encontrado)")

print("\n" + "=" * 70)
print("RESUMEN:")
if exact_matches:
    print(f"✅ Encontrados {len(exact_matches)} trabajos de camarero en Barcelona")
elif location_only:
    print(f"⚠️  No hay trabajos de camarero, pero hay {len(location_only)} trabajos en Barcelona")
else:
    print("❌ No se encontró nada")
print("=" * 70)
