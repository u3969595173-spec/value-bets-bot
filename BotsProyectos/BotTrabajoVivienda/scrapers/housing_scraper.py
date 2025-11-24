"""
Scraper de ofertas de vivienda desde múltiples fuentes
"""
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import logging
from datetime import datetime
import time
import re

logger = logging.getLogger(__name__)

# Áreas metropolitanas para vivienda
METRO_AREAS = {
    'barcelona': ['barcelona', 'hospitalet', 'badalona', 'terrassa', 'sabadell', 'santa coloma'],
    'madrid': ['madrid', 'alcala henares', 'fuenlabrada', 'leganes', 'getafe', 'mostoles'],
    'valencia': ['valencia', 'torrente', 'paterna', 'mislata', 'burjassot'],
    'sevilla': ['sevilla', 'dos hermanas', 'alcala guadaira'],
    'bilbao': ['bilbao', 'barakaldo', 'getxo', 'portugalete'],
    'malaga': ['malaga', 'marbella', 'fuengirola', 'torremolinos'],
}

class HousingScraper:
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
    
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
    
    def scrape_idealista(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Idealista.com"""
        listings = []
        try:
            # Idealista requiere URLs específicas por ciudad
            location_slug = location.lower().replace(" ", "-")
            base_url = f"https://www.idealista.com/alquiler-viviendas/{location_slug}/"
            
            logger.info(f"🔍 Scraping Idealista: {location}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all('article', class_=re.compile(r'item|advert'))
                
                for item in items[:max_results]:
                    try:
                        # Título
                        title_elem = item.find(['a', 'span'], class_=re.compile(r'item-link|title'))
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.idealista.com' + url
                        
                        # Precio
                        price_elem = item.find(['span', 'div'], class_=re.compile(r'item-price|price'))
                        price_str = price_elem.get_text(strip=True) if price_elem else ""
                        price = self.extract_price(price_str)
                        
                        # Filtrar por precio
                        if max_price and price and price > max_price:
                            continue
                        
                        # Habitaciones
                        rooms_elem = item.find(['span'], class_=re.compile(r'item-detail-char.*rooms|rooms'))
                        bedrooms = self.extract_number(rooms_elem.get_text(strip=True)) if rooms_elem else None
                        
                        # Descripción
                        desc_elem = item.find(['p', 'div'], class_=re.compile(r'description|item-description'))
                        description = desc_elem.get_text(strip=True)[:300] if desc_elem else ""
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': bedrooms,
                                'bathrooms': None,
                                'description': description,
                                'url': url,
                                'source': 'idealista',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        logger.error(f"Error procesando item Idealista: {e}")
                        continue
                
                logger.info(f"✅ Idealista: {len(listings)} viviendas encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Idealista: {e}")
        
        return listings
    
    def scrape_fotocasa(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Fotocasa.es"""
        listings = []
        try:
            location_slug = location.lower().replace(" ", "-")
            base_url = f"https://www.fotocasa.es/es/alquiler/viviendas/{location_slug}/todas"
            
            logger.info(f"🔍 Scraping Fotocasa: {location}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['article', 'div'], class_=re.compile(r're-Card|listing'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['a', 'h3'], class_=re.compile(r'title|link'))
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.fotocasa.es' + url
                        
                        price_elem = item.find(['span'], class_=re.compile(r'price'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'fotocasa',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Fotocasa: {len(listings)} viviendas encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Fotocasa: {e}")
        
        return listings
    
    def scrape_badi(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Badi.com (habitaciones compartidas)"""
        listings = []
        try:
            base_url = "https://badi.com/es/rooms"
            params = {'city': location}
            
            logger.info(f"🔍 Scraping Badi: {location}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div', 'article'], class_=re.compile(r'room-card|listing'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['a', 'h3'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://badi.com' + url
                        
                        price_elem = item.find(['span', 'div'], class_=re.compile(r'price'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title or "Habitación en piso compartido",
                                'price': price,
                                'location': location,
                                'bedrooms': 1,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'badi',
                                'special_tags': ['compartido', 'sin_fianza'],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Badi: {len(listings)} habitaciones encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Badi: {e}")
        
        return listings
    
    def scrape_milanuncios_housing(self, keywords, location="", max_price=None, max_results=20):
        """Scraper para Milanuncios.com (vivienda)"""
        listings = []
        try:
            base_url = "https://www.milanuncios.com/alquiler-de-pisos/"
            params = {}
            if location:
                params['provincia'] = location
            
            logger.info(f"🔍 Scraping Milanuncios vivienda: {location}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div', 'article'], class_=re.compile(r'aditem|ma-AdCard'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['a'], attrs={'title': True})
                        if not title_elem:
                            title_elem = item.find(['h2', 'h3'])
                        
                        if not title_elem:
                            continue
                        
                        title = title_elem.get('title', '') or title_elem.get_text(strip=True)
                        url = title_elem.get('href', '')
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.milanuncios.com' + url
                        
                        price_elem = item.find(class_=re.compile(r'price|precio'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        # Extraer ubicación real
                        location_elem = item.find(class_=re.compile(r'x-location|ubicacion|provincia'))
                        job_location = location_elem.get_text(strip=True) if location_elem else (location or "España")
                        
                        desc_elem = item.find(class_=re.compile(r'tx|description'))
                        description = desc_elem.get_text(strip=True)[:300] if desc_elem else ""
                        
                        # Detectar tags especiales
                        text_lower = (title + ' ' + description).lower()
                        special_tags = []
                        
                        if any(word in text_lower for word in ['sin fianza', 'sin deposito', 'no fianza']):
                            special_tags.append('sin_fianza')
                        if any(word in text_lower for word in ['sin nomina', 'sin contrato', 'no nomina']):
                            special_tags.append('sin_nomina')
                        if any(word in text_lower for word in ['extranjeros', 'inmigrantes', 'acepta extranjeros']):
                            special_tags.append('acepta_extranjeros')
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': job_location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': description,
                                'url': url,
                                'source': 'milanuncios',
                                'special_tags': special_tags,
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Milanuncios vivienda: {len(listings)} encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Milanuncios vivienda: {e}")
        
        return listings
    
    def scrape_pisos_com(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Pisos.com"""
        listings = []
        try:
            location_slug = location.lower().replace(" ", "-")
            base_url = f"https://www.pisos.com/alquiler/pisos-{location_slug}/"
            
            logger.info(f"🔍 Scraping Pisos.com: {location}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div'], class_=re.compile(r'ad-preview'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['a', 'h3'], class_=re.compile(r'title|link'))
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '')
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.pisos.com' + url
                        
                        price_elem = item.find(['span', 'div'], class_=re.compile(r'price'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'pisos',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Pisos.com: {len(listings)} viviendas encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Pisos.com: {e}")
        
        return listings
    
    def scrape_habitaclia(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Habitaclia.com"""
        listings = []
        try:
            location_slug = location.lower().replace(" ", "_")
            base_url = f"https://www.habitaclia.com/alquiler-{location_slug}.htm"
            
            logger.info(f"🔍 Scraping Habitaclia: {location}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['li', 'article'], class_=re.compile(r'listing|property'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['a', 'h3'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.habitaclia.com' + url
                        
                        price_elem = item.find(['span'], class_=re.compile(r'price|precio'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'habitaclia',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Habitaclia: {len(listings)} viviendas encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Habitaclia: {e}")
        
        return listings
    
    def extract_price(self, price_str):
        """Extraer precio numérico de un string"""
        try:
            # Eliminar texto y símbolos, mantener solo números
            price_clean = re.sub(r'[^\d]', '', price_str)
            if price_clean:
                return int(price_clean)
        except:
            pass
        return None
    
    def extract_number(self, text):
        """Extraer primer número de un texto"""
        try:
            match = re.search(r'\d+', text)
            if match:
                return int(match.group())
        except:
            pass
        return None
    
    def scrape_enalquiler(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Enalquiler.com"""
        listings = []
        try:
            location_slug = location.lower().replace(" ", "-")
            base_url = f"https://www.enalquiler.com/pisos-en-{location_slug}.html"
            
            logger.info(f"🔍 Scraping Enalquiler: {location}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div', 'article'], class_=re.compile(r'listing|advert|property'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['a', 'h2', 'h3'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.enalquiler.com' + url
                        
                        price_elem = item.find(['span', 'div'], class_=re.compile(r'price'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'enalquiler',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Enalquiler: {len(listings)} viviendas encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Enalquiler: {e}")
        
        return listings
    
    def scrape_alquiler_com(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Alquiler.com"""
        listings = []
        try:
            location_slug = location.lower().replace(" ", "-")
            base_url = f"https://www.alquiler.com/{location_slug}"
            
            logger.info(f"🔍 Scraping Alquiler.com: {location}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div', 'article'], class_=re.compile(r'property|listing'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.alquiler.com' + url
                        
                        price_elem = item.find(['span'], class_=re.compile(r'price'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'alquiler',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Alquiler.com: {len(listings)} viviendas encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Alquiler.com: {e}")
        
        return listings
    
    def scrape_spotahome(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Spotahome.com"""
        listings = []
        try:
            location_slug = location.lower()
            base_url = f"https://www.spotahome.com/es/{location_slug}"
            
            logger.info(f"🔍 Scraping Spotahome: {location}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div'], class_=re.compile(r'property-card|listing'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.spotahome.com' + url
                        
                        price_elem = item.find(['span', 'div'], class_=re.compile(r'price'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'spotahome',
                                'special_tags': ['verificado'],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Spotahome: {len(listings)} habitaciones encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Spotahome: {e}")
        
        return listings
    
    def scrape_uniplaces(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Uniplaces.com (estudiantes)"""
        listings = []
        try:
            location_slug = location.lower()
            base_url = f"https://www.uniplaces.com/es/accommodation/{location_slug}"
            
            logger.info(f"🔍 Scraping Uniplaces: {location}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div'], class_=re.compile(r'accommodation|property'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.uniplaces.com' + url
                        
                        price_elem = item.find(['span'], class_=re.compile(r'price'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'uniplaces',
                                'special_tags': ['estudiantes'],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Uniplaces: {len(listings)} habitaciones encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Uniplaces: {e}")
        
        return listings
    
    def scrape_housinganywhere(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para HousingAnywhere.com"""
        listings = []
        try:
            location_slug = location.lower()
            base_url = f"https://housinganywhere.com/es/s/{location_slug}"
            
            logger.info(f"🔍 Scraping HousingAnywhere: {location}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div'], class_=re.compile(r'listing|property'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://housinganywhere.com' + url
                        
                        price_elem = item.find(['span'], class_=re.compile(r'price'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'housinganywhere',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ HousingAnywhere: {len(listings)} habitaciones encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping HousingAnywhere: {e}")
        
        return listings
    
    def scrape_rentalia(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Rentalia.com"""
        listings = []
        try:
            location_slug = location.lower()
            base_url = f"https://www.rentalia.com/alquiler-{location_slug}"
            
            logger.info(f"🔍 Scraping Rentalia: {location}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div', 'article'], class_=re.compile(r'property|listing'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.rentalia.com' + url
                        
                        price_elem = item.find(['span'], class_=re.compile(r'price'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'rentalia',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Rentalia: {len(listings)} viviendas encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Rentalia: {e}")
        
        return listings
    
    def scrape_yaencontre(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Yaencontre.com"""
        listings = []
        try:
            base_url = "https://www.yaencontre.com/pisos-alquiler"
            params = {'lugar': location}
            
            logger.info(f"🔍 Scraping Yaencontre: {location}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div', 'article'], class_=re.compile(r'anuncio|listing'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.yaencontre.com' + url
                        
                        price_elem = item.find(['span'], class_=re.compile(r'price|precio'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'yaencontre',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Yaencontre: {len(listings)} viviendas encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Yaencontre: {e}")
        
        return listings
    
    def scrape_nuroa(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Nuroa.es"""
        listings = []
        try:
            location_slug = location.lower().replace(" ", "-")
            base_url = f"https://www.nuroa.es/alquiler/{location_slug}"
            
            logger.info(f"🔍 Scraping Nuroa: {location}")
            response = self.session.get(base_url, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div'], class_=re.compile(r'property|vivienda'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.nuroa.es' + url
                        
                        price_elem = item.find(['span'], class_=re.compile(r'price'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'nuroa',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Nuroa: {len(listings)} viviendas encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Nuroa: {e}")
        
        return listings
    
    def scrape_casadirecta(self, keywords, location="madrid", max_price=None, max_results=20):
        """Scraper para Casadirecta.com"""
        listings = []
        try:
            base_url = "https://www.casadirecta.com/alquiler"
            params = {'ubicacion': location}
            
            logger.info(f"🔍 Scraping Casadirecta: {location}")
            response = self.session.get(base_url, params=params, headers=self.get_headers(), timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                items = soup.find_all(['div', 'article'], class_=re.compile(r'property|inmueble'))
                
                for item in items[:max_results]:
                    try:
                        title_elem = item.find(['h2', 'h3', 'a'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '') if title_elem.name == 'a' else item.find('a').get('href', '') if item.find('a') else ''
                        
                        if url and not url.startswith('http'):
                            url = 'https://www.casadirecta.com' + url
                        
                        price_elem = item.find(['span'], class_=re.compile(r'price'))
                        price = self.extract_price(price_elem.get_text(strip=True)) if price_elem else None
                        
                        if max_price and price and price > max_price:
                            continue
                        
                        if url:
                            listings.append({
                                'title': title,
                                'price': price,
                                'location': location,
                                'bedrooms': None,
                                'bathrooms': None,
                                'description': '',
                                'url': url,
                                'source': 'casadirecta',
                                'special_tags': [],
                                'posted_date': datetime.now()
                            })
                    except Exception as e:
                        continue
                
                logger.info(f"✅ Casadirecta: {len(listings)} viviendas encontradas")
        except Exception as e:
            logger.error(f"❌ Error scraping Casadirecta: {e}")
        
        return listings
    
    def scrape_all(self, keywords, location="madrid", max_price=None, max_per_source=10):
        """Scraping desde TODAS las fuentes de vivienda"""
        all_listings = []
        
        scrapers = [
            ('Idealista', lambda: self.scrape_idealista(keywords, location, max_price, max_per_source)),
            ('Fotocasa', lambda: self.scrape_fotocasa(keywords, location, max_price, max_per_source)),
            ('Badi', lambda: self.scrape_badi(keywords, location, max_price, max_per_source)),
            ('Milanuncios', lambda: self.scrape_milanuncios_housing(keywords, location, max_price, max_per_source)),
            ('Pisos.com', lambda: self.scrape_pisos_com(keywords, location, max_price, max_per_source)),
            ('Habitaclia', lambda: self.scrape_habitaclia(keywords, location, max_price, max_per_source)),
            # Nuevos scrapers internacionales
            ('Enalquiler', lambda: self.scrape_enalquiler(keywords, location, max_price, max_per_source)),
            ('Alquiler.com', lambda: self.scrape_alquiler_com(keywords, location, max_price, max_per_source)),
            ('Spotahome', lambda: self.scrape_spotahome(keywords, location, max_price, max_per_source)),
            ('Uniplaces', lambda: self.scrape_uniplaces(keywords, location, max_price, max_per_source)),
            ('HousingAnywhere', lambda: self.scrape_housinganywhere(keywords, location, max_price, max_per_source)),
            # Más portales adicionales
            ('Rentalia', lambda: self.scrape_rentalia(keywords, location, max_price, max_per_source)),
            ('Yaencontre', lambda: self.scrape_yaencontre(keywords, location, max_price, max_per_source)),
            ('Nuroa', lambda: self.scrape_nuroa(keywords, location, max_price, max_per_source)),
            ('Casadirecta', lambda: self.scrape_casadirecta(keywords, location, max_price, max_per_source)),
        ]
        
        for name, scraper_func in scrapers:
            try:
                listings = scraper_func()
                all_listings.extend(listings)
                time.sleep(2)  # Respetar rate limits
            except Exception as e:
                logger.error(f"Error en {name}: {e}")
                continue
        
        # Eliminar duplicados por URL y filtrar por relevancia
        seen_urls = set()
        exact_match_listings = []  # Viviendas que coinciden con tipo Y ubicación
        location_only_listings = []  # Viviendas solo con ubicación correcta
        keywords_lower = keywords.lower()
        
        # Expandir ubicación por área metropolitana
        expanded_locations = self.expand_location(location)
        locations_lower = [loc.lower() for loc in expanded_locations]
        
        for listing in all_listings:
            if listing['url'] not in seen_urls:
                seen_urls.add(listing['url'])
                
                # Filtrar por tipo de vivienda
                listing_text = (listing['title'] + ' ' + listing.get('description', '')).lower()
                
                # Determinar si coincide con el tipo buscado
                has_type_match = False
                if 'habitacion' in keywords_lower:
                    # Busca habitación: debe contener "habitacion" y NO "piso completo"
                    if 'habitacion' in listing_text or 'hab' in listing_text:
                        if 'piso completo' not in listing_text and 'apartamento completo' not in listing_text:
                            has_type_match = True
                else:
                    # Busca piso/apartamento: cualquier vivienda vale
                    has_type_match = True
                
                # Filtrar por ubicación (acepta área metropolitana)
                listing_location = listing['location'].lower()
                location_match = False
                
                if location.lower() not in ['españa', 'spain', 'nacional', '']:
                    # DEBE coincidir con la ciudad específica o área metropolitana
                    # NO acepta ubicaciones genéricas como "España" o vacías
                    location_match = any(loc in listing_location for loc in locations_lower)
                else:
                    # Si busca en toda España, acepta todo
                    location_match = True
                
                # Separar en dos grupos
                if has_type_match and location_match:
                    exact_match_listings.append(listing)  # Coincidencia exacta
                elif location_match:
                    location_only_listings.append(listing)  # Solo ubicación correcta
        
        # Devolver ambos grupos
        result = {
            'exact_matches': exact_match_listings,
            'location_only': location_only_listings[:20]  # Limitar a 20
        }
        
        logger.info(f"📊 Encontradas: {len(exact_match_listings)} viviendas exactas + {len(location_only_listings)} viviendas en la ubicación")
        
        return result


def search_housing(keywords, location="madrid", max_price=None, max_results=40):
    """Función helper para buscar vivienda"""
    scraper = HousingScraper()
    return scraper.scrape_all(keywords, location, max_price, max_results // 6)
