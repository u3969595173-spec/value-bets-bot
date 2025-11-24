from scrapers.job_scraper import JobScraper

scraper = JobScraper()

print("=" * 70)
print("PROBANDO TODOS LOS SCRAPERS CON 'CAMARERO' EN BARCELONA")
print("=" * 70)

# Probar cada scraper individualmente
scrapers_to_test = [
    ('InfoJobs', lambda: scraper.scrape_infojobs('camarero', 'barcelona', 5)),
    ('InfoEmpleo', lambda: scraper.scrape_infoempleo('camarero', 'barcelona', 5)),
    ('Milanuncios', lambda: scraper.scrape_milanuncios('camarero', 'barcelona', 5)),
    ('Monster', lambda: scraper.scrape_monster('camarero', 'barcelona', 5)),
    ('Jooble', lambda: scraper.scrape_jooble('camarero', 'barcelona', 5)),
    ('Cornerjob', lambda: scraper.scrape_cornerjob('camarero', 'barcelona', 5)),
    ('Randstad', lambda: scraper.scrape_randstad('camarero', 'barcelona', 5)),
    ('Adecco', lambda: scraper.scrape_adecco('camarero', 'barcelona', 5)),
    ('Empleofacil', lambda: scraper.scrape_empleofacil('camarero', 'barcelona', 5)),
    ('Opcionempleo', lambda: scraper.scrape_opcionempleo('camarero', 'barcelona', 5)),
]

total_found = 0
for name, func in scrapers_to_test:
    try:
        jobs = func()
        total_found += len(jobs)
        print(f"\n{name}: {len(jobs)} trabajos")
        for i, job in enumerate(jobs[:2], 1):
            print(f"  {i}. {job['title'][:60]} | {job['location']}")
    except Exception as e:
        print(f"\n{name}: ERROR - {str(e)[:50]}")

print("\n" + "=" * 70)
print(f"TOTAL ENCONTRADO (sin filtros): {total_found} trabajos")
print("=" * 70)

# Ahora probar con scrape_all (con filtros)
print("\nProbando scrape_all() con filtros de categoría y ubicación...")
all_jobs = scraper.scrape_all('camarero', 'barcelona', max_per_source=3)
print(f"\nDespués de filtros: {len(all_jobs)} trabajos")
for i, job in enumerate(all_jobs[:5], 1):
    print(f"{i}. {job['title'][:60]} | {job['location']} ({job['source']})")
