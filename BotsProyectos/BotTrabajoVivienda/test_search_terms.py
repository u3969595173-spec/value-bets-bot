from scrapers.job_scraper import JobScraper

s = JobScraper()

print("Buscando 'hosteleria' en InfoEmpleo...")
jobs = s.scrape_infoempleo('hosteleria', 'barcelona', 10)
print(f"Hosteleria: {len(jobs)} trabajos")
for j in jobs[:5]:
    print(f"  - {j['title'][:60]}")

print("\nBuscando 'camarero' en InfoEmpleo...")
jobs2 = s.scrape_infoempleo('camarero', 'barcelona', 10)
print(f"Camarero: {len(jobs2)} trabajos")
for j in jobs2[:5]:
    print(f"  - {j['title'][:60]}")
