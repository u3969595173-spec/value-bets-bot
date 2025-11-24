"""
Scraper de ofertas de trabajo desde múltiples fuentes
"""
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import logging
from datetime import datetime
import time
import re

logger = logging.getLogger(__name__)

class JobScraper:
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        
    def get_headers(self):
        """Headers para evitar bloqueos"""
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def scrape_indeed(self, keywords, location="España", max_results=20):
        """Scraper para Indeed.es"""
        jobs = []
        try:
            # Construir URL de búsqueda
            base_url = "https://es.indeed.com/jobs"
            params = {
                'q': keywords,
                'l': location,
                'sort': 'date'
            }
            
            logger.info(f"🔍 Scraping Indeed: {keywords} en {location}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Indeed error: {response.status_code}")
                return jobs
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar tarjetas de trabajo
            job_cards = soup.find_all('div', class_=re.compile(r'job_seen_beacon|jobsearch-SerpJobCard'))
            
            for card in job_cards[:max_results]:
                try:
                    # Título
                    title_elem = card.find('h2', class_=re.compile(r'jobTitle'))
                    if not title_elem:
                        title_elem = card.find('a', class_=re.compile(r'jcs-JobTitle'))
                    title = title_elem.get_text(strip=True) if title_elem else "Sin título"
                    
                    # Empresa
                    company_elem = card.find('span', class_=re.compile(r'companyName'))
                    company = company_elem.get_text(strip=True) if company_elem else "No especificada"
                    
                    # Ubicación
                    location_elem = card.find('div', class_=re.compile(r'companyLocation'))
                    job_location = location_elem.get_text(strip=True) if location_elem else location
                    
                    # Salario
                    salary_elem = card.find('div', class_=re.compile(r'salary-snippet'))
                    salary = salary_elem.get_text(strip=True) if salary_elem else None
                    
                    # URL
                    link_elem = card.find('a', class_=re.compile(r'jcs-JobTitle'))
                    if not link_elem:
                        link_elem = title_elem.find('a') if title_elem else None
                    
                    job_id = link_elem.get('data-jk', '') if link_elem else ''
                    url = f"https://es.indeed.com/viewjob?jk={job_id}" if job_id else None
                    
                    # Descripción corta
                    desc_elem = card.find('div', class_=re.compile(r'job-snippet'))
                    description = desc_elem.get_text(strip=True) if desc_elem else ""
                    
                    # Detectar tags especiales
                    special_tags = []
                    text_lower = (title + ' ' + description).lower()
                    
                    if any(word in text_lower for word in ['sin experiencia', 'no experiencia', 'sin exp']):
                        special_tags.append('sin_experiencia')
                    if any(word in text_lower for word in ['sin papeles', 'irregular', 'sin permiso']):
                        special_tags.append('sin_papeles')
                    if any(word in text_lower for word in ['urgente', 'inmediato', 'incorporación inmediata']):
                        special_tags.append('urgente')
                    
                    if url:
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': job_location,
                            'salary': salary,
                            'description': description[:500],
                            'url': url,
                            'source': 'indeed',
                            'special_tags': special_tags,
                            'posted_date': datetime.now()
                        })
                        
                except Exception as e:
                    logger.error(f"Error procesando trabajo Indeed: {e}")
                    continue
            
            logger.info(f"✅ Indeed: {len(jobs)} trabajos encontrados")
            
        except Exception as e:
            logger.error(f"❌ Error scraping Indeed: {e}")
        
        return jobs
    
    def scrape_infojobs(self, keywords, location="", max_results=20):
        """Scraper para InfoJobs.net"""
        jobs = []
        try:
            base_url = "https://www.infojobs.net/jobsearch/search-results/list.xhtml"
            params = {
                'keyword': keywords,
                'location': location
            }
            
            logger.info(f"🔍 Scraping InfoJobs: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code != 200:
                logger.error(f"InfoJobs error: {response.status_code}")
                return jobs
            
            soup = BeautifulSoup(response.content, 'html.parser')
            job_items = soup.find_all('div', class_=re.compile(r'offer-item|job-item'))
            
            for item in job_items[:max_results]:
                try:
                    title_elem = item.find('a', class_=re.compile(r'job-title|title'))
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get('href', '')
                    if url and not url.startswith('http'):
                        url = 'https://www.infojobs.net' + url
                    
                    company_elem = item.find('a', class_=re.compile(r'company'))
                    company = company_elem.get_text(strip=True) if company_elem else "No especificada"
                    
                    location_elem = item.find('span', class_=re.compile(r'location'))
                    job_location = location_elem.get_text(strip=True) if location_elem else ""
                    
                    salary_elem = item.find('span', class_=re.compile(r'salary'))
                    salary = salary_elem.get_text(strip=True) if salary_elem else None
                    
                    if url:
                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': job_location,
                            'salary': salary,
                            'description': '',
                            'url': url,
                            'source': 'infojobs',
                            'special_tags': [],
                            'posted_date': datetime.now()
                        })
                        
                except Exception as e:
                    logger.error(f"Error procesando trabajo InfoJobs: {e}")
                    continue
            
            logger.info(f"✅ InfoJobs: {len(jobs)} trabajos encontrados")
            
        except Exception as e:
            logger.error(f"❌ Error scraping InfoJobs: {e}")
        
        return jobs
    
    def scrape_jobtoday(self, keywords, location="", max_results=20):
        """Scraper para JobToday (app popular para trabajos sin experiencia)"""
        jobs = []
        try:
            # JobToday es principalmente app móvil, pero intentamos scraping web
            base_url = "https://jobtoday.com/es/jobs"
            
            logger.info(f"🔍 Scraping JobToday: {keywords}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code != 200:
                logger.error(f"JobToday error: {response.status_code}")
                return jobs
            
            soup = BeautifulSoup(response.content, 'html.parser')
            job_cards = soup.find_all('div', class_=re.compile(r'job-card|listing'))
            
            for card in job_cards[:max_results]:
                try:
                    title_elem = card.find(['h2', 'h3', 'a'], class_=re.compile(r'title|name'))
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    url_elem = card.find('a')
                    url = url_elem.get('href', '') if url_elem else ''
                    
                    if url and not url.startswith('http'):
                        url = 'https://jobtoday.com' + url
                    
                    if url:
                        jobs.append({
                            'title': title,
                            'company': "JobToday",
                            'location': location or "España",
                            'salary': None,
                            'description': '',
                            'url': url,
                            'source': 'jobtoday',
                            'special_tags': ['sin_experiencia'],  # JobToday es conocido por esto
                            'posted_date': datetime.now()
                        })
                        
                except Exception as e:
                    logger.error(f"Error procesando trabajo JobToday: {e}")
                    continue
            
            logger.info(f"✅ JobToday: {len(jobs)} trabajos encontrados")
            
        except Exception as e:
            logger.error(f"❌ Error scraping JobToday: {e}")
        
        return jobs
    
    def scrape_infoempleo(self, keywords, location="", max_results=20):
        """Scraper para InfoEmpleo.com"""
        jobs = []
        try:
            base_url = "https://www.infoempleo.com/trabajo"
            params = {'s': keywords, 'l': location}
            
            logger.info(f"🔍 Scraping InfoEmpleo: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = soup.find_all(['article', 'div'], class_=re.compile(r'offer|job'))
                
                for card in job_cards[:max_results]:
                    try:
                        title_elem = card.find(['h2', 'h3', 'a'], class_=re.compile(r'title|job'))
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else ''
                        if not url:
                            url_elem = card.find('a')
                            url = url_elem.get('href', '') if url_elem else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.infoempleo.com' + url
                        
                        # Extraer ubicación real del HTML
                        location_elem = card.find(['span', 'div', 'p'], class_=re.compile(r'location|ciudad|provincia|lugar'))
                        job_location = location_elem.get_text(strip=True) if location_elem else (location or "España")
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': card.find(class_=re.compile(r'company')).get_text(strip=True) if card.find(class_=re.compile(r'company')) else "No especificada",
                                'location': job_location,
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'infoempleo',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ InfoEmpleo: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping InfoEmpleo: {e}")
        
        return jobs
    
    def scrape_trabajos_com(self, keywords, location="", max_results=20):
        """Scraper para Trabajos.com"""
        jobs = []
        try:
            base_url = "https://www.trabajos.com/buscar-empleo"
            params = {'q': keywords, 'l': location}
            
            logger.info(f"🔍 Scraping Trabajos.com: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_items = soup.find_all(['div', 'article'], class_=re.compile(r'job|offer|listing'))
                
                for item in job_items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'], class_=re.compile(r'title'))
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.trabajos.com' + url
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "Trabajos.com",
                                'location': location or "España",
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'trabajos',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Trabajos.com: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Trabajos.com: {e}")
        
        return jobs
    
    def scrape_tecnoempleo(self, keywords, location="", max_results=20):
        """Scraper para TecnoEmpleo.com"""
        jobs = []
        try:
            base_url = "https://www.tecnoempleo.com/buscar-trabajo"
            params = {'keywords': keywords, 'location': location}
            
            logger.info(f"🔍 Scraping TecnoEmpleo: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = soup.find_all(['div', 'article'], class_=re.compile(r'job|offer'))
                
                for card in job_cards[:max_results]:
                    try:
                        title_elem = card.find(['h2', 'h3'], class_=re.compile(r'title'))
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url_elem = card.find('a')
                        url = url_elem.get('href', '') if url_elem else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.tecnoempleo.com' + url
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "TecnoEmpleo",
                                'location': location or "España",
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'tecnoempleo',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ TecnoEmpleo: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping TecnoEmpleo: {e}")
        
        return jobs
    
    def scrape_empleate(self, keywords, location="", max_results=20):
        """Scraper para Empleate.com"""
        jobs = []
        try:
            base_url = "https://www.empleate.com/empleo"
            params = {'q': keywords, 'l': location}
            
            logger.info(f"🔍 Scraping Empleate: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_listings = soup.find_all(['div', 'li'], class_=re.compile(r'job|offer|result'))
                
                for listing in job_listings[:max_results]:
                    try:
                        title_elem = listing.find(['h2', 'h3', 'a'], class_=re.compile(r'title|name'))
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else listing.find('a').get('href', '') if listing.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.empleate.com' + url
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "Empleate",
                                'location': location or "España",
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'empleate',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Empleate: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Empleate: {e}")
        
        return jobs
    
    def scrape_turijobs(self, keywords, location="", max_results=20):
        """Scraper para Turijobs.com (hostelería y turismo)"""
        jobs = []
        try:
            base_url = "https://www.turijobs.com/empleo"
            params = {'search': keywords, 'location': location}
            
            logger.info(f"🔍 Scraping Turijobs: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = soup.find_all(['div', 'article'], class_=re.compile(r'job|offer'))
                
                for card in job_cards[:max_results]:
                    try:
                        title_elem = card.find(['h2', 'h3'], class_=re.compile(r'title'))
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url_elem = card.find('a')
                        url = url_elem.get('href', '') if url_elem else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.turijobs.com' + url
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': card.find(class_=re.compile(r'company')).get_text(strip=True) if card.find(class_=re.compile(r'company')) else "No especificada",
                                'location': location or "España",
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'turijobs',
                                'special_tags': ['hosteleria'],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Turijobs: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Turijobs: {e}")
        
        return jobs
    
    def scrape_monster(self, keywords, location="", max_results=20):
        """Scraper para Monster.es"""
        jobs = []
        try:
            base_url = "https://www.monster.es/empleos/buscar"
            params = {'q': keywords, 'where': location}
            
            logger.info(f"🔍 Scraping Monster: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = soup.find_all(['div', 'article'], class_=re.compile(r'job|card'))
                
                for card in job_cards[:max_results]:
                    try:
                        title_elem = card.find(['h2', 'h3', 'a'], class_=re.compile(r'title|job'))
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else card.find('a').get('href', '') if card.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.monster.es' + url
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': card.find(class_=re.compile(r'company')).get_text(strip=True) if card.find(class_=re.compile(r'company')) else "No especificada",
                                'location': location or "España",
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'monster',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Monster: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Monster: {e}")
        
        return jobs
    
    def scrape_jooble(self, keywords, location="", max_results=20):
        """Scraper para Jooble.org"""
        jobs = []
        try:
            base_url = "https://es.jooble.org/SearchResult"
            params = {'keywords': keywords, 'location': location}
            
            logger.info(f"🔍 Scraping Jooble: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_items = soup.find_all(['div', 'article'], class_=re.compile(r'job|vacancy'))
                
                for item in job_items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'], class_=re.compile(r'title|position'))
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://es.jooble.org' + url
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': item.find(class_=re.compile(r'company')).get_text(strip=True) if item.find(class_=re.compile(r'company')) else "No especificada",
                                'location': location or "España",
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'jooble',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Jooble: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Jooble: {e}")
        
        return jobs
    
    def scrape_milanuncios(self, keywords, location="", max_results=20):
        """Scraper para Milanuncios.com"""
        jobs = []
        try:
            # Milanuncios usa categorías - empleo es categoría 11
            base_url = "https://www.milanuncios.com/anuncios/empleo.htm"
            params = {'demanda': '1', 'palabra': keywords}
            if location:
                params['provincia'] = location
            
            logger.info(f"🔍 Scraping Milanuncios: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Milanuncios tiene estructura específica
                job_items = soup.find_all(['div', 'article'], class_=re.compile(r'aditem|ma-AdCard'))
                
                for item in job_items[:max_results]:
                    try:
                        # Título
                        title_elem = item.find(['h2', 'h3', 'a'], class_=re.compile(r'aditem-detail-title|ma-AdCard-title'))
                        if not title_elem:
                            title_elem = item.find('a', attrs={'title': True})
                        
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True) if not title_elem.get('title') else title_elem.get('title')
                        
                        # URL
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.milanuncios.com' + url
                        
                        # Ubicación
                        location_elem = item.find(class_=re.compile(r'x-location|ubicacion|provincia'))
                        job_location = location_elem.get_text(strip=True) if location_elem else location or "España"
                        
                        # Descripción
                        desc_elem = item.find(class_=re.compile(r'tx|description|texto'))
                        description = desc_elem.get_text(strip=True)[:300] if desc_elem else ""
                        
                        if url and title:
                            # Detectar si es sin papeles/experiencia
                            text_lower = (title + ' ' + description).lower()
                            special_tags = []
                            
                            if any(word in text_lower for word in ['sin papeles', 'sin documentos', 'irregulares']):
                                special_tags.append('sin_papeles')
                            if any(word in text_lower for word in ['sin experiencia', 'principiantes', 'primer empleo']):
                                special_tags.append('sin_experiencia')
                            if any(word in text_lower for word in ['urgente', 'inmediato', 'ya']):
                                special_tags.append('urgente')
                            
                            jobs.append({
                                'title': title,
                                'company': "Milanuncios",
                                'location': job_location,
                                'salary': None,
                                'description': description,
                                'url': url,
                                'source': 'milanuncios',
                                'special_tags': special_tags,
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        logger.error(f"Error procesando anuncio Milanuncios: {e}")
                        continue
                
                logger.info(f"✅ Milanuncios: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Milanuncios: {e}")
        
        return jobs
    
    def scrape_all(self, keywords, location="España", max_per_source=10):
        """Scraping desde TODAS las fuentes populares"""
        all_jobs = []
        
        scrapers = [
            ('Indeed', lambda: self.scrape_indeed(keywords, location, max_per_source)),
            ('InfoJobs', lambda: self.scrape_infojobs(keywords, location, max_per_source)),
            ('Milanuncios', lambda: self.scrape_milanuncios(keywords, location, max_per_source)),
            ('InfoEmpleo', lambda: self.scrape_infoempleo(keywords, location, max_per_source)),
            ('Trabajos.com', lambda: self.scrape_trabajos_com(keywords, location, max_per_source)),
            ('TecnoEmpleo', lambda: self.scrape_tecnoempleo(keywords, location, max_per_source)),
            ('Empleate', lambda: self.scrape_empleate(keywords, location, max_per_source)),
            ('Turijobs', lambda: self.scrape_turijobs(keywords, location, max_per_source)),
            ('Monster', lambda: self.scrape_monster(keywords, location, max_per_source)),
            ('Jooble', lambda: self.scrape_jooble(keywords, location, max_per_source)),
            ('JobToday', lambda: self.scrape_jobtoday(keywords, location, max_per_source)),
        ]
        
        for name, scraper_func in scrapers:
            try:
                jobs = scraper_func()
                all_jobs.extend(jobs)
                time.sleep(2)  # Respetar rate limits
            except Exception as e:
                logger.error(f"Error en {name}: {e}")
                continue
        
        # Eliminar duplicados por URL y filtrar por relevancia
        seen_urls = set()
        unique_jobs = []
        keywords_lower = keywords.lower().split()
        location_lower = location.lower()
        
        for job in all_jobs:
            if job['url'] not in seen_urls:
                seen_urls.add(job['url'])
                
                # Filtrar por palabras clave (debe contener al menos una)
                job_text = (job['title'] + ' ' + job.get('description', '')).lower()
                has_keyword = any(keyword in job_text for keyword in keywords_lower)
                
                # Filtrar por ubicación
                location_match = True
                if location_lower not in ['españa', 'spain', 'nacional', '']:
                    job_location = job['location'].lower()
                    # Acepta si: coincide ubicación exacta, es remoto, o ubicación vacía/genérica
                    location_match = (
                        location_lower in job_location or 
                        'remoto' in job_location or 
                        'teletrabajo' in job_location or
                        'a distancia' in job_location or
                        job_location in ['españa', 'spain', 'nacional', '', 'no especificada']
                    )
                
                # Debe cumplir AMBAS condiciones: keyword Y ubicación
                if has_keyword and location_match:
                    unique_jobs.append(job)
        
        logger.info(f"📊 Total: {len(unique_jobs)} trabajos únicos y relevantes de {len(all_jobs)} encontrados desde 11 fuentes")
        
        return unique_jobs


def search_jobs(keywords, location="España", max_results=50):
    """Función helper para buscar trabajos en TODAS las fuentes"""
    scraper = JobScraper()
    return scraper.scrape_all(keywords, location, max_results // 10)
