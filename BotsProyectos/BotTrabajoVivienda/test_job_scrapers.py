from scrapers.job_scraper import JobScraper

scraper = JobScraper()

print("=" * 50)
print("Probando InfoJobs...")
jobs = scraper.scrape_infojobs('camarero', 'barcelona', 5)
print(f"InfoJobs encontró: {len(jobs)} trabajos")
for job in jobs[:3]:
    print(f"- {job['title']} en {job['location']}")

print("\n" + "=" * 50)
print("Probando InfoEmpleo...")
jobs = scraper.scrape_infoempleo('camarero', 'barcelona', 5)
print(f"InfoEmpleo encontró: {len(jobs)} trabajos")
for job in jobs[:3]:
    print(f"- {job['title']} en {job['location']}")

print("\n" + "=" * 50)
print("Probando Milanuncios...")
jobs = scraper.scrape_milanuncios('camarero', 'barcelona', 5)
print(f"Milanuncios encontró: {len(jobs)} trabajos")
for job in jobs[:3]:
    print(f"- {job['title']} en {job['location']}")

print("\n" + "=" * 50)
print("Probando scrape_all con filtros...")

# Debug: ver trabajos antes del filtro
from scrapers.job_scraper import JobScraper
scraper2 = JobScraper()
jobs_infoempleo = scraper2.scrape_infoempleo('camarero', 'barcelona', 5)
print(f"\nDEBUG - InfoEmpleo devolvió {len(jobs_infoempleo)} trabajos:")
for job in jobs_infoempleo:
    print(f"  Título: '{job['title']}'")
    print(f"  Location: '{job['location']}'")
    print(f"  Tiene 'camarero': {'camarero' in job['title'].lower()}")
    print(f"  Tiene 'barcelona': {'barcelona' in job['location'].lower()}")
    print()

all_jobs = scraper.scrape_all('camarero', 'barcelona', max_per_source=5)
print(f"Total después de filtros: {len(all_jobs)} trabajos")
for job in all_jobs[:5]:
    print(f"- {job['title']} en {job['location']} ({job['source']})")
