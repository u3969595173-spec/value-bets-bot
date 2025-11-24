"""Debug: ver qué están devolviendo los scrapers"""
from scrapers.job_scraper import JobScraper

scraper = JobScraper()

print("=" * 70)
print("PROBANDO SCRAPER: InfoEmpleo")
print("=" * 70)

jobs = scraper.scrape_infoempleo('Medico', 'Madrid', 10)

print(f"\n✅ InfoEmpleo encontró: {len(jobs)} trabajos\n")

for i, job in enumerate(jobs, 1):
    print(f"{i}. {job['title']}")
    print(f"   📍 Location extraída: '{job['location']}'")
    print(f"   🔗 {job['url'][:80]}...\n")

print("\n" + "=" * 70)
print("PROBANDO SCRAPER: Jobrapido")
print("=" * 70)

jobs = scraper.scrape_jobrapido('Medico', 'Madrid', 10)

print(f"\n✅ Jobrapido encontró: {len(jobs)} trabajos\n")

for i, job in enumerate(jobs, 1):
    print(f"{i}. {job['title']}")
    print(f"   📍 Location extraída: '{job['location']}'")
    print(f"   🔗 {job['url'][:80]}...\n")
