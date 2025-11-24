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

# Categorías de trabajo con sinónimos y palabras relacionadas
JOB_CATEGORIES = {
    'hosteleria': ['camarero', 'camarera', 'mesero', 'mesera', 'cocinero', 'cocinera', 'ayudante cocina', 
                   'chef', 'barista', 'bartender', 'sumiller', 'maitre', 'hostess', 'runner',
                   'pinche cocina', 'lavaplatos', 'friegaplatos', 'jefe sala', 'recepcionista hotel'],
    'construccion': ['albañil', 'albañileria', 'peon', 'oficial', 'construccion', 'obra', 
                     'electricista', 'fontanero', 'pintor', 'carpintero', 'yesero', 'solador',
                     'ferrallista', 'gruista', 'paleta', 'encofradores'],
    'limpieza': ['limpieza', 'limpiador', 'limpiadora', 'personal limpieza', 'servicio domestico',
                 'empleada hogar', 'empleado hogar', 'mucama', 'conserje'],
    'almacen': ['mozo almacen', 'peón almacen', 'carretillero', 'preparador pedidos', 'picking',
                'operario logistica', 'repartidor', 'conductor', 'chofer', 'delivery'],
    'comercio': ['dependiente', 'dependienta', 'vendedor', 'vendedora', 'cajero', 'cajera',
                 'reponedor', 'reponedora', 'promotor', 'promotora', 'atencion cliente'],
    'agricultura': ['agricultor', 'agricola', 'campo', 'jornalero', 'temporero', 'recolector',
                    'cosecha', 'invernadero', 'jardinero', 'jardineria', 'peón agricola'],
    'cuidados': ['cuidador', 'cuidadora', 'auxiliar enfermeria', 'gerocultor', 'auxiliar ayuda domicilio',
                 'canguro', 'niñera', 'cuidado mayores', 'cuidado niños'],
}

# Áreas metropolitanas (búsqueda expandida por ciudades cercanas)
METRO_AREAS = {
    'barcelona': ['barcelona', 'hospitalet', 'badalona', 'terrassa', 'sabadell', 'santa coloma'],
    'madrid': ['madrid', 'alcala henares', 'fuenlabrada', 'leganes', 'getafe', 'mostoles'],
    'valencia': ['valencia', 'torrente', 'paterna', 'mislata', 'burjassot'],
    'sevilla': ['sevilla', 'dos hermanas', 'alcala guadaira'],
    'bilbao': ['bilbao', 'barakaldo', 'getxo', 'portugalete'],
    'malaga': ['malaga', 'marbella', 'fuengirola', 'torremolinos'],
}

# Títulos inválidos que no son ofertas reales (elementos de interfaz)
INVALID_TITLES = [
    'busca trabajo', 'buscar empleo', 'ofertas de empleo', 'trabajos encontrados',
    'resultados', 'no se encontraron', 'cargando', 'ver más', 'filtrar',
    'ordenar por', 'empleo en', 'trabajo en', 'ofertas en', 'encuentra',
    'buscar', 'ver todas', 'mostrar', 'página', 'iniciar sesión', 'regístrate',
    'registro', 'login', 'acceder', 'mi cuenta'
]

class JobScraper:
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
    
    def is_valid_title(self, title):
        """Valida que un título sea una oferta real y no un elemento de interfaz"""
        if not title or len(title) < 5:
            return False
        if title.isdigit():
            return False
        
        title_lower = title.lower()
        # Rechazar títulos genéricos de la interfaz
        if any(invalid in title_lower for invalid in INVALID_TITLES):
            return False
        
        return True
    
    def expand_keywords(self, keywords):
        """Expande keywords basándose en categorías"""
        keywords_lower = keywords.lower()
        
        # Buscar si la keyword pertenece a alguna categoría
        for category, terms in JOB_CATEGORIES.items():
            for term in terms:
                if term in keywords_lower:
                    # Si encuentra coincidencia, devuelve TODAS las palabras de esa categoría
                    logger.info(f"🔍 Expandiendo '{keywords}' a categoría '{category}' con {len(terms)} términos")
                    return terms
        
        # Si no pertenece a ninguna categoría, devuelve la keyword original
        return [keywords]
    
    def expand_location(self, location):
        """Expande ubicación para incluir ciudades cercanas del área metropolitana"""
        location_lower = location.lower()
        
        # Buscar si pertenece a algún área metropolitana
        for metro, cities in METRO_AREAS.items():
            if metro in location_lower or location_lower in cities:
                logger.info(f"📍 Expandiendo '{location}' a área metropolitana con {len(cities)} ciudades")
                return cities
        
        # Si no es área metropolitana, devuelve la ubicación original
        return [location]
        
    def get_headers(self):
        """Headers para evitar bloqueos"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
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
                    job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                    
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
                        
                        # Validar que el título sea una oferta real
                        if not self.is_valid_title(title):
                            continue
                        
                        url = title_elem.get('href', '') if title_elem.name == 'a' else ''
                        if not url:
                            url_elem = card.find('a')
                            url = url_elem.get('href', '') if url_elem else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.infoempleo.com' + url
                        
                        # Extraer ubicación real del HTML
                        location_elem = card.find(['span', 'div', 'p'], class_=re.compile(r'location|ciudad|provincia|lugar'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
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
                        
                        # Extraer ubicación real
                        location_elem = item.find(['span', 'div', 'p'], class_=re.compile(r'location|ciudad|provincia'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "Trabajos.com",
                                'location': job_location,
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
                        
                        # Extraer ubicación real
                        location_elem = card.find(['span', 'div'], class_=re.compile(r'location|ciudad'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "TecnoEmpleo",
                                'location': job_location,
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
                        
                        # Extraer ubicación real
                        location_elem = listing.find(['span', 'div'], class_=re.compile(r'location|ciudad'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "Empleate",
                                'location': job_location,
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
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=20)
            
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
                        
                        # Extraer ubicación real
                        location_elem = card.find(['span', 'div'], class_=re.compile(r'location|ciudad'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': card.find(class_=re.compile(r'company')).get_text(strip=True) if card.find(class_=re.compile(r'company')) else "No especificada",
                                'location': job_location,
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
                        
                        # Extraer ubicación real
                        location_elem = card.find(['span', 'div'], class_=re.compile(r'location|lugar'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': card.find(class_=re.compile(r'company')).get_text(strip=True) if card.find(class_=re.compile(r'company')) else "No especificada",
                                'location': job_location,
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
                        
                        # Extraer ubicación real
                        location_elem = item.find(['span', 'div'], class_=re.compile(r'location|city'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': item.find(class_=re.compile(r'company')).get_text(strip=True) if item.find(class_=re.compile(r'company')) else "No especificada",
                                'location': job_location,
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
    
    def scrape_cornerjob(self, keywords, location="", max_results=20):
        """Scraper para Cornerjob.com"""
        jobs = []
        try:
            base_url = "https://www.cornerjob.com/es/jobs"
            params = {'q': keywords, 'l': location}
            
            logger.info(f"🔍 Scraping Cornerjob: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = soup.find_all(['div', 'article'], class_=re.compile(r'job|offer|card'))
                
                for card in job_cards[:max_results]:
                    try:
                        title_elem = card.find(['h2', 'h3', 'a'], class_=re.compile(r'title'))
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else card.find('a').get('href', '') if card.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.cornerjob.com' + url
                        
                        location_elem = card.find(['span', 'div'], class_=re.compile(r'location'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "Cornerjob",
                                'location': job_location,
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'cornerjob',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Cornerjob: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Cornerjob: {e}")
        
        return jobs
    
    def scrape_randstad(self, keywords, location="", max_results=20):
        """Scraper para Randstad.es"""
        jobs = []
        try:
            base_url = "https://www.randstad.es/candidatos/ofertas-empleo/"
            params = {'keywords': keywords, 'location': location}
            
            logger.info(f"🔍 Scraping Randstad: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_items = soup.find_all(['div', 'article'], class_=re.compile(r'job|offer|vacancy'))
                
                for item in job_items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        
                        # Validar que el título sea una oferta real
                        if not self.is_valid_title(title):
                            continue
                        
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.randstad.es' + url
                        
                        location_elem = item.find(['span', 'div'], class_=re.compile(r'location'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': 'Randstad',
                                'location': job_location,
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'randstad',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Randstad: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Randstad: {e}")
        
        return jobs
    
    def scrape_adecco(self, keywords, location="", max_results=20):
        """Scraper para Adecco.es"""
        jobs = []
        try:
            base_url = "https://www.adecco.es/ofertas-empleo"
            params = {'k': keywords, 'l': location}
            
            logger.info(f"🔍 Scraping Adecco: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = soup.find_all(['div', 'article'], class_=re.compile(r'job|offer'))
                
                for card in job_cards[:max_results]:
                    try:
                        title_elem = card.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else card.find('a').get('href', '') if card.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.adecco.es' + url
                        
                        location_elem = card.find(['span', 'div'], class_=re.compile(r'location'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': 'Adecco',
                                'location': job_location,
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'adecco',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Adecco: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Adecco: {e}")
        
        return jobs
    
    def scrape_manpower(self, keywords, location="", max_results=20):
        """Scraper para Manpower.es"""
        jobs = []
        try:
            base_url = "https://www.manpower.es/empleos"
            params = {'keywords': keywords, 'location': location}
            
            logger.info(f"🔍 Scraping Manpower: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_listings = soup.find_all(['div', 'li'], class_=re.compile(r'job|listing|result'))
                
                for listing in job_listings[:max_results]:
                    try:
                        title_elem = listing.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else listing.find('a').get('href', '') if listing.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.manpower.es' + url
                        
                        location_elem = listing.find(['span', 'div'], class_=re.compile(r'location'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': 'Manpower',
                                'location': job_location,
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'manpower',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Manpower: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Manpower: {e}")
        
        return jobs
    
    def scrape_empleofacil(self, keywords, location="", max_results=20):
        """Scraper para Empleofacil.es"""
        jobs = []
        try:
            base_url = "https://www.empleofacil.es/empleo"
            params = {'q': keywords, 'l': location}
            
            logger.info(f"🔍 Scraping Empleofacil: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = soup.find_all(['div', 'article'], class_=re.compile(r'job|offer'))
                
                for card in job_cards[:max_results]:
                    try:
                        title_elem = card.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else card.find('a').get('href', '') if card.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.empleofacil.es' + url
                        
                        location_elem = card.find(['span', 'div'], class_=re.compile(r'location'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "Empleofacil",
                                'location': job_location,
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'empleofacil',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Empleofacil: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Empleofacil: {e}")
        
        return jobs
    
    def scrape_opcionempleo(self, keywords, location="", max_results=20):
        """Scraper para Opcionempleo.es"""
        jobs = []
        try:
            base_url = "https://www.opcionempleo.com/empleos"
            params = {'q': keywords, 'l': location}
            
            logger.info(f"🔍 Scraping Opcionempleo: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_items = soup.find_all(['div', 'article'], class_=re.compile(r'job|offer'))
                
                for item in job_items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.opcionempleo.com' + url
                        
                        location_elem = item.find(['span', 'div'], class_=re.compile(r'location'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "Opcionempleo",
                                'location': job_location,
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'opcionempleo',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Opcionempleo: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Opcionempleo: {e}")
        
        return jobs
    
    def scrape_jobrapido(self, keywords, location="", max_results=20):
        """Scraper para Jobrapido.com"""
        jobs = []
        try:
            base_url = "https://es.jobrapido.com/"
            params = {'q': keywords, 'l': location}
            
            logger.info(f"🔍 Scraping Jobrapido: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_listings = soup.find_all(['div', 'li'], class_=re.compile(r'job|listing'))
                
                for listing in job_listings[:max_results]:
                    try:
                        title_elem = listing.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else listing.find('a').get('href', '') if listing.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://es.jobrapido.com' + url
                        
                        location_elem = listing.find(['span', 'div'], class_=re.compile(r'location'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "Jobrapido",
                                'location': job_location,
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'jobrapido',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Jobrapido: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Jobrapido: {e}")
        
        return jobs
    
    def scrape_domestiko(self, keywords, location="", max_results=20):
        """Scraper para Domestiko.com (empleadas hogar)"""
        jobs = []
        try:
            base_url = "https://www.domestiko.com/empleos"
            params = {'buscar': keywords, 'donde': location}
            
            logger.info(f"🔍 Scraping Domestiko: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = soup.find_all(['div', 'article'], class_=re.compile(r'empleo|oferta'))
                
                for card in job_cards[:max_results]:
                    try:
                        title_elem = card.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else card.find('a').get('href', '') if card.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.domestiko.com' + url
                        
                        location_elem = card.find(['span', 'div'], class_=re.compile(r'location|ciudad'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "Domestiko",
                                'location': job_location,
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'domestiko',
                                'special_tags': ['servicio_domestico'],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Domestiko: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Domestiko: {e}")
        
        return jobs
    
    def scrape_jobatus(self, keywords, location="", max_results=20):
        """Scraper para Jobatus.es"""
        jobs = []
        try:
            base_url = "https://www.jobatus.es/empleo"
            params = {'q': keywords, 'l': location}
            
            logger.info(f"🔍 Scraping Jobatus: {keywords}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                job_items = soup.find_all(['div'], class_=re.compile(r'job|offer'))
                
                for item in job_items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.jobatus.es' + url
                        
                        location_elem = item.find(['span', 'div'], class_=re.compile(r'location'))
                        job_location = location_elem.get_text(strip=True) if location_elem else "no especificada"
                        
                        if url:
                            jobs.append({
                                'title': title,
                                'company': "Jobatus",
                                'location': job_location,
                                'salary': None,
                                'description': '',
                                'url': url,
                                'source': 'jobatus',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Jobatus: {len(jobs)} trabajos encontrados")
        except Exception as e:
            logger.error(f"❌ Error scraping Jobatus: {e}")
        
        return jobs
    
    def scrape_all(self, keywords, location="España", max_per_source=10):
        """Scraping desde TODAS las fuentes populares"""
        all_jobs = []
        
        scrapers = [
            # ('Indeed', lambda: self.scrape_indeed(keywords, location, max_per_source)),  # Bloqueado 403
            ('InfoJobs', lambda: self.scrape_infojobs(keywords, location, max_per_source)),
            ('Milanuncios', lambda: self.scrape_milanuncios(keywords, location, max_per_source)),
            ('InfoEmpleo', lambda: self.scrape_infoempleo(keywords, location, max_per_source)),
            ('Trabajos.com', lambda: self.scrape_trabajos_com(keywords, location, max_per_source)),
            ('TecnoEmpleo', lambda: self.scrape_tecnoempleo(keywords, location, max_per_source)),
            ('Empleate', lambda: self.scrape_empleate(keywords, location, max_per_source)),
            ('Turijobs', lambda: self.scrape_turijobs(keywords, location, max_per_source)),
            ('Monster', lambda: self.scrape_monster(keywords, location, max_per_source)),
            ('Jooble', lambda: self.scrape_jooble(keywords, location, max_per_source)),
            # ('JobToday', lambda: self.scrape_jobtoday(keywords, location, max_per_source)),  # Bloqueado 403
            # Nuevos scrapers ETT y grandes portales
            ('Cornerjob', lambda: self.scrape_cornerjob(keywords, location, max_per_source)),
            ('Randstad', lambda: self.scrape_randstad(keywords, location, max_per_source)),
            ('Adecco', lambda: self.scrape_adecco(keywords, location, max_per_source)),
            ('Manpower', lambda: self.scrape_manpower(keywords, location, max_per_source)),
            # Más portales adicionales
            ('Empleofacil', lambda: self.scrape_empleofacil(keywords, location, max_per_source)),
            ('Opcionempleo', lambda: self.scrape_opcionempleo(keywords, location, max_per_source)),
            ('Jobrapido', lambda: self.scrape_jobrapido(keywords, location, max_per_source)),
            ('Domestiko', lambda: self.scrape_domestiko(keywords, location, max_per_source)),
            ('Jobatus', lambda: self.scrape_jobatus(keywords, location, max_per_source)),
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
        exact_match_jobs = []  # Trabajos que coinciden con categoría Y ubicación
        location_only_jobs = []  # Trabajos solo con ubicación correcta (sin categoría)
        
        # Expandir keywords por categoría
        expanded_keywords = self.expand_keywords(keywords)
        keywords_lower = [kw.lower() for kw in expanded_keywords]
        
        # Expandir ubicación por área metropolitana
        expanded_locations = self.expand_location(location)
        locations_lower = [loc.lower() for loc in expanded_locations]
        
        for job in all_jobs:
            if job['url'] not in seen_urls:
                seen_urls.add(job['url'])
                
                # Filtrar por palabras clave expandidas (debe contener al menos una de la categoría)
                job_text = (job['title'] + ' ' + job.get('description', '')).lower()
                has_keyword = any(keyword in job_text for keyword in keywords_lower)
                
                # Filtrar por ubicación (acepta ubicaciones expandidas)
                location_match = False
                if location.lower() not in ['españa', 'spain', 'nacional', '']:
                    job_location = job['location'].lower()
                    
                    # Si la ubicación está en el campo location
                    if any(loc in job_location for loc in locations_lower):
                        location_match = True
                    # Si es remoto/teletrabajo
                    elif 'remoto' in job_location or 'teletrabajo' in job_location or 'a distancia' in job_location:
                        location_match = True
                    # FALLBACK: Si no pudo extraer ubicación (común en muchos scrapers)
                    # CONFIAR en que el scraper buscó en la ubicación correcta
                    elif job_location == 'no especificada':
                        # Verificar si menciona la ciudad en título/descripción
                        # O simplemente confiar en el scraper (ya filtró por ciudad en la URL)
                        location_match = True  # Confiar en el scraper
                else:
                    # Si busca en toda España, acepta todo
                    location_match = True
                
                # Separar en dos grupos
                if has_keyword and location_match:
                    exact_match_jobs.append(job)  # Coincidencia exacta
                elif location_match:
                    location_only_jobs.append(job)  # Solo ubicación correcta
        
        # Devolver ambos grupos (SIN límite en exact_matches, enviar TODO lo encontrado)
        result = {
            'exact_matches': exact_match_jobs,  # TODOS los trabajos exactos
            'location_only': location_only_jobs[:20]  # Limitar a 20 para no saturar
        }
        
        logger.info(f"📊 Encontrados: {len(exact_match_jobs)} trabajos exactos + {len(location_only_jobs)} trabajos en la ubicación")
        
        return result


def search_jobs(keywords, location="España", max_results=50):
    """Función helper para buscar trabajos en TODAS las fuentes"""
    scraper = JobScraper()
    return scraper.scrape_all(keywords, location, max_results)  # Pasar límite completo

