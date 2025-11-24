from scrapers.job_scraper import JobScraper

scraper = JobScraper()

print("=" * 60)
print("PRUEBA DE EXPANSIÓN DE CATEGORÍAS")
print("=" * 60)

# Probar expansión
keywords_tests = ['camarero', 'albañil', 'limpieza', 'programador']

for keyword in keywords_tests:
    expanded = scraper.expand_keywords(keyword)
    print(f"\n'{keyword}' → {len(expanded)} términos:")
    print(f"  {', '.join(expanded[:5])}{'...' if len(expanded) > 5 else ''}")

print("\n" + "=" * 60)
print("BÚSQUEDA REAL: Camarero en Barcelona")
print("=" * 60)

jobs = scraper.scrape_all('camarero', 'barcelona', max_per_source=3)
print(f"\n✅ Encontrados: {len(jobs)} trabajos")
for i, job in enumerate(jobs[:10], 1):
    print(f"{i}. {job['title'][:60]} - {job['location']} ({job['source']})")
