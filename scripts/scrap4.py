import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BeritaPanganScraperEnhanced:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # EXPANDED: Keywords lebih banyak dan variatif
        self.keywords = [
            # General keywords
            'harga beras jawa barat', 'harga beras jabar', 'harga pangan jawa barat',
            'harga sembako jabar', 'inflasi pangan jawa barat', 'stok beras jawa barat',
            
            # Specific cities
            'harga beras bandung', 'harga beras bekasi', 'harga beras bogor',
            'harga beras cirebon', 'harga beras depok', 'harga beras sukabumi',
            'harga beras tasikmalaya', 'harga beras garut', 'harga beras karawang',
            'harga beras indramayu', 'harga beras subang', 'harga beras purwakarta',
            
            # Specific types
            'harga beras ciherang', 'harga beras IR64', 'harga beras premium',
            'harga beras medium', 'harga beras pandan wangi',
            
            # Government programs
            'operasi pasar beras jawa barat', 'bulog jawa barat', 
            'stabilitas harga pangan jabar', 'subsidi beras jawa barat',
            
            # Related terms
            'harga gabah jawa barat', 'pasar beras jawa barat',
            'distribusi beras jawa barat', 'ketersediaan beras jabar'
        ]
        
        self.results = []
        
        # Enhanced location detection (cities, districts, subdistricts)
        self.jabar_locations = {
            'kota': ['bandung', 'bekasi', 'bogor', 'cirebon', 'depok', 'sukabumi', 
                     'tasikmalaya', 'banjar', 'cimahi'],
            'kabupaten': ['bandung barat', 'garut', 'indramayu', 'karawang', 'kuningan',
                         'majalengka', 'pangandaran', 'purwakarta', 'subang', 'sumedang',
                         'cianjur', 'ciamis'],
            'kecamatan': ['arcamanik', 'antapani', 'astana anyar', 'babakan ciparay',
                         'bandung kidul', 'bandung kulon', 'bandung wetan', 'batununggal',
                         'buah batu', 'cibeunying kaler', 'cibeunying kidul', 'cibiru',
                         'cicendo', 'cidadap', 'cinambo', 'coblong', 'gedebage', 
                         'kiaracondong', 'lengkong', 'mandalajati', 'panyileukan',
                         'rancasari', 'regol', 'sukajadi', 'sukasari', 'sumur bandung',
                         'ujung berung']
        }
        
    def extract_detailed_address(self, text):
        """Ekstrak alamat lengkap dari teks"""
        addresses = []
        
        # Pattern untuk alamat lengkap
        address_patterns = [
            r'(?:di|Di)\s+([A-Z][a-zA-Z\s,]+(?:Jalan|Jl\.?|Raya|RT|RW|Kelurahan|Kecamatan|Pasar)[^.!?]{0,100})',
            r'(?:Jalan|Jl\.?|Raya)\s+([A-Z][a-zA-Z0-9\s,\.\/\-]+)(?:,|\s+RT|\s+RW|\s+No)',
            r'(?:Pasar|Market|Toko)\s+([A-Z][a-zA-Z\s]+)',
            r'(?:RT\s*\d{1,3}\/RW\s*\d{1,3})',
            r'Kelurahan\s+([A-Z][a-zA-Z\s]+)',
            r'Kecamatan\s+([A-Z][a-zA-Z\s]+)',
        ]
        
        for pattern in address_patterns:
            matches = re.findall(pattern, text)
            addresses.extend(matches)
        
        # Bersihkan dan filter
        cleaned_addresses = []
        for addr in addresses:
            if isinstance(addr, str):
                addr = addr.strip()
                if len(addr) > 5 and len(addr) < 200:  # Filter panjang wajar
                    cleaned_addresses.append(addr)
        
        return list(set(cleaned_addresses))
    
    def extract_price_info(self, text):
        """Ekstrak informasi harga dari teks dengan lebih detail dan normalisasi"""
        price_data = []
        
        # Pattern komprehensif untuk berbagai format harga
        price_patterns = [
            # Harga dengan satuan jelas (prioritas tertinggi)
            (r'Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?\s*(?:per\s*kg|\/kg|per\s*kilogram)', 'per_kg'),
            (r'[\d.,]+(?:\s*ribu|rb|juta|jt)\s*(?:per\s*kg|\/kg|per\s*kilogram)', 'per_kg'),
            
            # Harga padi/gabah
            (r'Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?\s*(?:per\s*kuintal|\/kuintal|per\s*kwintal)', 'per_kuintal'),
            (r'[\d.,]+(?:\s*ribu|rb|juta|jt)\s*(?:per\s*kuintal|\/kuintal)', 'per_kuintal'),
            
            # Konteks gabah/padi
            (r'(?:gabah|padi|GKP|GKG).*?Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?', 'gabah'),
            (r'Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?.*?(?:gabah|padi|GKP|GKG)', 'gabah'),
            
            # Konteks beras konsumen
            (r'(?:beras|konsumen|eceran|pasar).*?Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?', 'beras_konsumen'),
            
            # Harga dengan kata kunci
            (r'harga\s+(?:beras\s+)?Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?(?:\s*per\s*kg|\/kg)?', 'generic'),
            (r'seharga\s+Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?', 'generic'),
            (r'berkisar\s+Rp\s*[\d.,]+-+Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?', 'range'),
            (r'mulai\s+(?:dari\s+)?Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?', 'min'),
            (r'mencapai\s+Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?', 'max'),
            (r'tertinggi\s+Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?', 'max'),
            (r'terendah\s+Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?', 'min'),
        ]
        
        for pattern, price_type in price_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                price_data.append({
                    'raw': match,
                    'type': price_type,
                    'normalized': self.normalize_price(match)
                })
        
        # Deduplikasi
        unique_prices = {}
        for p in price_data:
            key = p['raw'].lower().strip()
            if key not in unique_prices:
                unique_prices[key] = p
        
        return list(unique_prices.values())
    
    def normalize_price(self, price_str):
        """Normalisasi harga ke format standar (Rupiah)"""
        try:
            # Ekstrak angka
            numbers = re.findall(r'[\d.,]+', price_str)
            if not numbers:
                return None
            
            # Ambil angka pertama
            num_str = numbers[0].replace('.', '').replace(',', '.')
            value = float(num_str)
            
            # Konversi ribu/juta
            if 'juta' in price_str.lower() or 'jt' in price_str.lower():
                value *= 1000000
            elif 'ribu' in price_str.lower() or 'rb' in price_str.lower():
                value *= 1000
            
            return int(value)
        except:
            return None
    
    def categorize_price(self, text, price_info):
        """Kategorisasi harga: beras konsumen vs padi produsen"""
        text_lower = text.lower()
        
        categories = {
            'beras_konsumen': [],
            'padi_produsen': [],
            'gabah_kering': [],
            'tidak_terkategori': []
        }
        
        for price in price_info:
            context = price['raw'].lower()
            
            # Deteksi padi/gabah produsen
            if any(word in context or word in text_lower[:100] for word in [
                'gabah', 'padi', 'gkp', 'gkg', 'petani', 'produsen', 
                'panen', 'sawah', 'kuintal'
            ]):
                categories['padi_produsen'].append(price)
            
            # Deteksi beras konsumen
            elif any(word in context or word in text_lower[:100] for word in [
                'beras', 'konsumen', 'eceran', 'pasar', 'toko', 'per kg', '/kg',
                'premium', 'medium', 'ciherang', 'ir64', 'retail'
            ]):
                categories['beras_konsumen'].append(price)
            
            # Gabah kering khusus
            elif any(word in context for word in ['gkg', 'gabah kering']):
                categories['gabah_kering'].append(price)
            
            else:
                categories['tidak_terkategori'].append(price)
        
        return categories
    
    def extract_location_info(self, text):
        """Ekstrak informasi lokasi di Jawa Barat dengan detail"""
        locations = {
            'kota': [],
            'kabupaten': [],
            'kecamatan': [],
            'general': []
        }
        
        text_lower = text.lower()
        
        # Deteksi kota
        for kota in self.jabar_locations['kota']:
            if kota in text_lower:
                locations['kota'].append(kota.title())
        
        # Deteksi kabupaten
        for kab in self.jabar_locations['kabupaten']:
            if kab in text_lower:
                locations['kabupaten'].append(kab.title())
        
        # Deteksi kecamatan
        for kec in self.jabar_locations['kecamatan']:
            if kec in text_lower:
                locations['kecamatan'].append(kec.title())
        
        # General
        if 'jawa barat' in text_lower or 'jabar' in text_lower:
            locations['general'].append('Jawa Barat')
        
        # Remove duplicates
        for key in locations:
            locations[key] = list(set(locations[key]))
        
        return locations
    
    def extract_quality_info(self, text):
        """Ekstrak informasi kualitas beras"""
        qualities = []
        quality_keywords = [
            'premium', 'super', 'medium', 'kualitas baik', 'kualitas sedang',
            'IR 64', 'IR64', 'Ciherang', 'Slyp', 'Pandan Wangi', 'Pandanwangi',
            'Mentik', 'Rojolele', 'grade A', 'grade B', 'grade C',
            'kualitas tinggi', 'kualitas rendah', 'organik', 'non-organik'
        ]
        
        text_lower = text.lower()
        for quality in quality_keywords:
            if quality.lower() in text_lower:
                qualities.append(quality)
        
        return list(set(qualities))
    
    def extract_date_info(self, text):
        """Ekstrak informasi tanggal dari artikel"""
        date_patterns = [
            r'\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4}',
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}/\d{2}/\d{4}',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return None
    
    def scrape_detik(self, keyword, max_pages=5):
        """Scrape berita dari Detik.com"""
        logger.info(f"Scraping Detik.com untuk keyword: {keyword}")
        
        for page in range(1, max_pages + 1):
            try:
                url = f"https://www.detik.com/search/searchall?query={quote(keyword)}&page={page}"
                response = requests.get(url, headers=self.headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    articles = soup.find_all('article') or soup.find_all('div', class_='list-content')
                    
                    for article in articles:
                        try:
                            title_elem = article.find('h3') or article.find('h2') or article.find('a')
                            link_elem = article.find('a', href=True)
                            desc_elem = article.find('p') or article.find('span', class_='desc')
                            
                            if title_elem and link_elem:
                                title = title_elem.get_text(strip=True)
                                link = link_elem['href']
                                description = desc_elem.get_text(strip=True) if desc_elem else ""
                                
                                # Get full content
                                content = self.get_article_content(link)
                                combined_text = f"{title} {description} {content}"
                                
                                # Extract all information
                                locations = self.extract_location_info(combined_text)
                                
                                # Only keep if related to Jawa Barat
                                if locations['kota'] or locations['kabupaten'] or locations['general']:
                                    # Extract and categorize prices
                                    price_info = self.extract_price_info(combined_text)
                                    price_categories = self.categorize_price(combined_text, price_info)
                                    
                                    article_data = {
                                        'source': 'Detik.com',
                                        'title': title,
                                        'url': link,
                                        'description': description,
                                        'content': content,
                                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'published_date': self.extract_date_info(combined_text),
                                        'keyword': keyword,
                                        'prices': {
                                            'beras_konsumen': price_categories['beras_konsumen'],
                                            'padi_produsen': price_categories['padi_produsen'],
                                            'gabah_kering': price_categories['gabah_kering'],
                                            'tidak_terkategori': price_categories['tidak_terkategori'],
                                            'all_raw': price_info
                                        },
                                        'locations': locations,
                                        'detailed_addresses': self.extract_detailed_address(combined_text),
                                        'qualities': self.extract_quality_info(combined_text)
                                    }
                                    
                                    self.results.append(article_data)
                                    logger.info(f"✓ Scraped: {title[:60]}...")
                        
                        except Exception as e:
                            logger.warning(f"Error parsing article: {e}")
                            continue
                    
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"Error scraping Detik page {page}: {e}")
                continue
    
    def scrape_kompas(self, keyword, max_pages=5):
        """Scrape berita dari Kompas.com"""
        logger.info(f"Scraping Kompas.com untuk keyword: {keyword}")
        
        for page in range(1, max_pages + 1):
            try:
                url = f"https://search.kompas.com/search/?q={quote(keyword)}&page={page}"
                response = requests.get(url, headers=self.headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    articles = soup.find_all('div', class_='gs-result')
                    
                    for article in articles:
                        try:
                            title_elem = article.find('a', class_='gs-title')
                            desc_elem = article.find('div', class_='gs-snippet')
                            
                            if title_elem:
                                title = title_elem.get_text(strip=True)
                                link = title_elem.get('href', '')
                                description = desc_elem.get_text(strip=True) if desc_elem else ""
                                
                                content = self.get_article_content(link)
                                combined_text = f"{title} {description} {content}"
                                
                                locations = self.extract_location_info(combined_text)
                                
                                if locations['kota'] or locations['kabupaten'] or locations['general']:
                                    price_info = self.extract_price_info(combined_text)
                                    price_categories = self.categorize_price(combined_text, price_info)
                                    
                                    article_data = {
                                        'source': 'Kompas.com',
                                        'title': title,
                                        'url': link,
                                        'description': description,
                                        'content': content,
                                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'published_date': self.extract_date_info(combined_text),
                                        'keyword': keyword,
                                        'prices': {
                                            'beras_konsumen': price_categories['beras_konsumen'],
                                            'padi_produsen': price_categories['padi_produsen'],
                                            'gabah_kering': price_categories['gabah_kering'],
                                            'tidak_terkategori': price_categories['tidak_terkategori'],
                                            'all_raw': price_info
                                        },
                                        'locations': locations,
                                        'detailed_addresses': self.extract_detailed_address(combined_text),
                                        'qualities': self.extract_quality_info(combined_text)
                                    }
                                    
                                    self.results.append(article_data)
                                    logger.info(f"✓ Scraped: {title[:60]}...")
                        
                        except Exception as e:
                            logger.warning(f"Error parsing article: {e}")
                            continue
                    
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"Error scraping Kompas page {page}: {e}")
                continue
    
    def scrape_tribun(self, keyword, max_pages=5):
        """Scrape berita dari Tribunnews"""
        logger.info(f"Scraping Tribunnews untuk keyword: {keyword}")
        
        for page in range(1, max_pages + 1):
            try:
                url = f"https://www.tribunnews.com/search?q={quote(keyword)}&page={page}"
                response = requests.get(url, headers=self.headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    articles = soup.find_all('li', class_='ptb15') or soup.find_all('div', class_='txt')
                    
                    for article in articles:
                        try:
                            title_elem = article.find('h3') or article.find('h2')
                            link_elem = article.find('a', href=True)
                            
                            if title_elem and link_elem:
                                title = title_elem.get_text(strip=True)
                                link = link_elem['href']
                                if not link.startswith('http'):
                                    link = urljoin('https://www.tribunnews.com', link)
                                
                                desc_elem = article.find('p')
                                description = desc_elem.get_text(strip=True) if desc_elem else ""
                                
                                content = self.get_article_content(link)
                                combined_text = f"{title} {description} {content}"
                                
                                locations = self.extract_location_info(combined_text)
                                
                                if locations['kota'] or locations['kabupaten'] or locations['general']:
                                    price_info = self.extract_price_info(combined_text)
                                    price_categories = self.categorize_price(combined_text, price_info)
                                    
                                    article_data = {
                                        'source': 'Tribunnews',
                                        'title': title,
                                        'url': link,
                                        'description': description,
                                        'content': content,
                                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'published_date': self.extract_date_info(combined_text),
                                        'keyword': keyword,
                                        'prices': {
                                            'beras_konsumen': price_categories['beras_konsumen'],
                                            'padi_produsen': price_categories['padi_produsen'],
                                            'gabah_kering': price_categories['gabah_kering'],
                                            'tidak_terkategori': price_categories['tidak_terkategori'],
                                            'all_raw': price_info
                                        },
                                        'locations': locations,
                                        'detailed_addresses': self.extract_detailed_address(combined_text),
                                        'qualities': self.extract_quality_info(combined_text)
                                    }
                                    
                                    self.results.append(article_data)
                                    logger.info(f"✓ Scraped: {title[:60]}...")
                        
                        except Exception as e:
                            logger.warning(f"Error parsing article: {e}")
                            continue
                    
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"Error scraping Tribun page {page}: {e}")
                continue
    
    def scrape_antara(self, keyword, max_pages=5):
        """Scrape berita dari Antara News"""
        logger.info(f"Scraping Antara News untuk keyword: {keyword}")
        
        for page in range(1, max_pages + 1):
            try:
                url = f"https://www.antaranews.com/search?q={quote(keyword)}&page={page}"
                response = requests.get(url, headers=self.headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    articles = soup.find_all('article') or soup.find_all('div', class_='simple-post')
                    
                    for article in articles:
                        try:
                            title_elem = article.find('h3') or article.find('a')
                            link_elem = article.find('a', href=True)
                            
                            if title_elem and link_elem:
                                title = title_elem.get_text(strip=True)
                                link = link_elem['href']
                                if not link.startswith('http'):
                                    link = urljoin('https://www.antaranews.com', link)
                                
                                desc_elem = article.find('p')
                                description = desc_elem.get_text(strip=True) if desc_elem else ""
                                
                                content = self.get_article_content(link)
                                combined_text = f"{title} {description} {content}"
                                
                                locations = self.extract_location_info(combined_text)
                                
                                if locations['kota'] or locations['kabupaten'] or locations['general']:
                                    price_info = self.extract_price_info(combined_text)
                                    price_categories = self.categorize_price(combined_text, price_info)
                                    
                                    article_data = {
                                        'source': 'Antara News',
                                        'title': title,
                                        'url': link,
                                        'description': description,
                                        'content': content,
                                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'published_date': self.extract_date_info(combined_text),
                                        'keyword': keyword,
                                        'prices': {
                                            'beras_konsumen': price_categories['beras_konsumen'],
                                            'padi_produsen': price_categories['padi_produsen'],
                                            'gabah_kering': price_categories['gabah_kering'],
                                            'tidak_terkategori': price_categories['tidak_terkategori'],
                                            'all_raw': price_info
                                        },
                                        'locations': locations,
                                        'detailed_addresses': self.extract_detailed_address(combined_text),
                                        'qualities': self.extract_quality_info(combined_text)
                                    }
                                    
                                    self.results.append(article_data)
                                    logger.info(f"✓ Scraped: {title[:60]}...")
                        
                        except Exception as e:
                            logger.warning(f"Error parsing article: {e}")
                            continue
                    
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"Error scraping Antara page {page}: {e}")
                continue
    
    def scrape_pikiran_rakyat(self, keyword, max_pages=5):
        """Scrape berita dari Pikiran Rakyat (Media Lokal Jabar)"""
        logger.info(f"Scraping Pikiran Rakyat untuk keyword: {keyword}")
        
        for page in range(1, max_pages + 1):
            try:
                url = f"https://www.pikiran-rakyat.com/search?q={quote(keyword)}"
                response = requests.get(url, headers=self.headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    articles = soup.find_all('article') or soup.find_all('div', class_='latest__item')
                    
                    for article in articles:
                        try:
                            title_elem = article.find('h2') or article.find('h3')
                            link_elem = article.find('a', href=True)
                            
                            if title_elem and link_elem:
                                title = title_elem.get_text(strip=True)
                                link = link_elem['href']
                                if not link.startswith('http'):
                                    link = urljoin('https://www.pikiran-rakyat.com', link)
                                
                                desc_elem = article.find('p')
                                description = desc_elem.get_text(strip=True) if desc_elem else ""
                                
                                content = self.get_article_content(link)
                                combined_text = f"{title} {description} {content}"
                                
                                locations = self.extract_location_info(combined_text)
                                
                                if locations['kota'] or locations['kabupaten'] or locations['general']:
                                    price_info = self.extract_price_info(combined_text)
                                    price_categories = self.categorize_price(combined_text, price_info)
                                    
                                    article_data = {
                                        'source': 'Pikiran Rakyat',
                                        'title': title,
                                        'url': link,
                                        'description': description,
                                        'content': content,
                                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'published_date': self.extract_date_info(combined_text),
                                        'keyword': keyword,
                                        'prices': {
                                            'beras_konsumen': price_categories['beras_konsumen'],
                                            'padi_produsen': price_categories['padi_produsen'],
                                            'gabah_kering': price_categories['gabah_kering'],
                                            'tidak_terkategori': price_categories['tidak_terkategori'],
                                            'all_raw': price_info
                                        },
                                        'locations': locations,
                                        'detailed_addresses': self.extract_detailed_address(combined_text),
                                        'qualities': self.extract_quality_info(combined_text)
                                    }
                                    
                                    self.results.append(article_data)
                                    logger.info(f"✓ Scraped: {title[:60]}...")
                        
                        except Exception as e:
                            logger.warning(f"Error parsing article: {e}")
                            continue
                    
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"Error scraping Pikiran Rakyat: {e}")
                continue
    
    def scrape_google_news(self, keyword, max_results=20):
        """Scrape dari Google News untuk agregasi lebih banyak sumber"""
        logger.info(f"Scraping Google News untuk keyword: {keyword}")
        
        try:
            # Google News RSS feed
            url = f"https://news.google.com/rss/search?q={quote(keyword + ' jawa barat')}&hl=id&gl=ID&ceid=ID:id"
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                items = soup.find_all('item')[:max_results]
                
                for item in items:
                    try:
                        title = item.find('title').get_text(strip=True) if item.find('title') else ""
                        link = item.find('link').get_text(strip=True) if item.find('link') else ""
                        description = item.find('description').get_text(strip=True) if item.find('description') else ""
                        pub_date = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ""
                        
                        if title and link:
                            # Try to get full content
                            content = self.get_article_content(link)
                            combined_text = f"{title} {description} {content}"
                            
                            locations = self.extract_location_info(combined_text)
                            
                            if locations['kota'] or locations['kabupaten'] or locations['general']:
                                price_info = self.extract_price_info(combined_text)
                                price_categories = self.categorize_price(combined_text, price_info)
                                
                                article_data = {
                                    'source': 'Google News Aggregator',
                                    'title': title,
                                    'url': link,
                                    'description': description,
                                    'content': content,
                                    'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'published_date': pub_date,
                                    'keyword': keyword,
                                    'prices': {
                                        'beras_konsumen': price_categories['beras_konsumen'],
                                        'padi_produsen': price_categories['padi_produsen'],
                                        'gabah_kering': price_categories['gabah_kering'],
                                        'tidak_terkategori': price_categories['tidak_terkategori'],
                                        'all_raw': price_info
                                    },
                                    'locations': locations,
                                    'detailed_addresses': self.extract_detailed_address(combined_text),
                                    'qualities': self.extract_quality_info(combined_text)
                                }
                                
                                self.results.append(article_data)
                                logger.info(f"✓ Scraped: {title[:60]}...")
                    
                    except Exception as e:
                        logger.warning(f"Error parsing Google News item: {e}")
                        continue
                
                time.sleep(2)
                
        except Exception as e:
            logger.error(f"Error scraping Google News: {e}")
    
    def get_article_content(self, url):
        """Ambil konten lengkap artikel"""
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Coba berbagai selector untuk konten artikel
                content_selectors = [
                    {'name': 'div', 'class_': 'detail__body-text'},
                    {'name': 'div', 'class_': 'read__content'},
                    {'name': 'div', 'class_': 'article-content'},
                    {'name': 'div', 'class_': 'entry-content'},
                    {'name': 'div', 'class_': 'post-content'},
                    {'name': 'article'},
                    {'name': 'div', 'class_': 'content'},
                    {'name': 'div', 'id': 'article-body'},
                ]
                
                for selector in content_selectors:
                    content_elem = soup.find(selector['name'], class_=selector.get('class_')) if 'class_' in selector else soup.find(selector['name'], id=selector.get('id'))
                    if content_elem:
                        paragraphs = content_elem.find_all('p')
                        return ' '.join([p.get_text(strip=True) for p in paragraphs])
                
                return ""
        except Exception as e:
            logger.warning(f"Error fetching article content: {e}")
            return ""
    
    def run_scraping(self, max_pages_per_site=5, use_google_news=True):
        """Jalankan scraping untuk semua keywords dan sumber"""
        logger.info("=" * 80)
        logger.info("MULAI SCRAPING DATA HARGA PANGAN JAWA BARAT (ENHANCED)")
        logger.info("=" * 80)
        
        for idx, keyword in enumerate(self.keywords, 1):
            logger.info(f"\n[{idx}/{len(self.keywords)}] Keyword: {keyword}")
            logger.info("-" * 80)
            
            # Scrape dari semua sumber
            self.scrape_detik(keyword, max_pages_per_site)
            time.sleep(2)
            
            self.scrape_kompas(keyword, max_pages_per_site)
            time.sleep(2)
            
            self.scrape_tribun(keyword, max_pages_per_site)
            time.sleep(2)
            
            self.scrape_antara(keyword, max_pages_per_site)
            time.sleep(2)
            
            self.scrape_pikiran_rakyat(keyword, max_pages_per_site)
            time.sleep(2)
            
            if use_google_news:
                self.scrape_google_news(keyword, max_results=20)
                time.sleep(2)
        
        # Remove duplicates based on URL
        logger.info("\nMenghapus duplikat...")
        unique_results = []
        seen_urls = set()
        for result in self.results:
            if result['url'] not in seen_urls:
                unique_results.append(result)
                seen_urls.add(result['url'])
        
        self.results = unique_results
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"SELESAI! Total artikel unik: {len(self.results)}")
        logger.info(f"{'=' * 80}\n")
    
    def save_to_json(self, filename='harga_pangan_jabar_enhanced.json'):
        """Simpan hasil ke file JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logger.info(f"✓ Data disimpan ke {filename}")
    
    def save_to_text(self, filename='harga_pangan_jabar_enhanced.txt'):
        """Simpan hasil ke file Text yang lebih detail"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write("DATA SCRAPING HARGA BERAS/PANGAN POKOK JAWA BARAT (ENHANCED VERSION)\n")
            f.write(f"Tanggal Scraping: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Artikel: {len(self.results)}\n")
            f.write("=" * 100 + "\n\n")
            
            for idx, article in enumerate(self.results, 1):
                f.write(f"\n{'=' * 100}\n")
                f.write(f"ARTIKEL #{idx}\n")
                f.write(f"{'=' * 100}\n")
                f.write(f"Sumber           : {article['source']}\n")
                f.write(f"Judul            : {article['title']}\n")
                f.write(f"URL              : {article['url']}\n")
                f.write(f"Keyword          : {article['keyword']}\n")
                f.write(f"Tanggal Scraping : {article['scraped_date']}\n")
                f.write(f"Tanggal Publikasi: {article.get('published_date', 'N/A')}\n")
                f.write(f"\nDeskripsi:\n{article['description']}\n")
                
                if article['content']:
                    f.write(f"\nKonten Lengkap:\n{article['content'][:1000]}...\n")
                
                f.write(f"\n{'-' * 100}\n")
                f.write(f"INFORMASI TERIDENTIFIKASI\n")
                f.write(f"{'-' * 100}\n")
                
                # Harga
                f.write(f"\n💰 HARGA:\n")
                prices = article['prices']
                
                # Beras Konsumen
                if prices['beras_konsumen']:
                    f.write(f"\n  🛒 BERAS KONSUMEN:\n")
                    for p in prices['beras_konsumen']:
                        normalized = f" (≈ Rp {p['normalized']:,})" if p['normalized'] else ""
                        f.write(f"    • {p['raw']}{normalized}\n")
                
                # Padi Produsen
                if prices['padi_produsen']:
                    f.write(f"\n  🌾 PADI/GABAH PRODUSEN:\n")
                    for p in prices['padi_produsen']:
                        normalized = f" (≈ Rp {p['normalized']:,})" if p['normalized'] else ""
                        f.write(f"    • {p['raw']}{normalized}\n")
                
                # Gabah Kering
                if prices['gabah_kering']:
                    f.write(f"\n  🌾 GABAH KERING GILING (GKG):\n")
                    for p in prices['gabah_kering']:
                        normalized = f" (≈ Rp {p['normalized']:,})" if p['normalized'] else ""
                        f.write(f"    • {p['raw']}{normalized}\n")
                
                # Tidak Terkategori
                if prices['tidak_terkategori']:
                    f.write(f"\n  ❓ HARGA LAINNYA:\n")
                    for p in prices['tidak_terkategori']:
                        normalized = f" (≈ Rp {p['normalized']:,})" if p['normalized'] else ""
                        f.write(f"    • {p['raw']}{normalized}\n")
                
                if not any([prices['beras_konsumen'], prices['padi_produsen'], 
                           prices['gabah_kering'], prices['tidak_terkategori']]):
                    f.write(f"  Tidak ditemukan\n")
                
                # Lokasi
                f.write(f"\n📍 LOKASI:\n")
                locs = article['locations']
                if locs['general']:
                    f.write(f"  General: {', '.join(locs['general'])}\n")
                if locs['kota']:
                    f.write(f"  Kota: {', '.join(locs['kota'])}\n")
                if locs['kabupaten']:
                    f.write(f"  Kabupaten: {', '.join(locs['kabupaten'])}\n")
                if locs['kecamatan']:
                    f.write(f"  Kecamatan: {', '.join(locs['kecamatan'])}\n")
                if not any([locs['general'], locs['kota'], locs['kabupaten'], locs['kecamatan']]):
                    f.write(f"  Tidak ditemukan\n")
                
                # Alamat Detail
                f.write(f"\n🏠 ALAMAT DETAIL:\n")
                if article['detailed_addresses']:
                    for addr in article['detailed_addresses']:
                        f.write(f"  • {addr}\n")
                else:
                    f.write(f"  Tidak ditemukan\n")
                
                # Kualitas
                f.write(f"\n⭐ KUALITAS BERAS:\n")
                if article['qualities']:
                    for quality in article['qualities']:
                        f.write(f"  • {quality}\n")
                else:
                    f.write(f"  Tidak ditemukan\n")
                
                f.write("\n")
        
        logger.info(f"✓ Data disimpan ke {filename}")
    
    def save_to_csv(self, filename='harga_pangan_jabar_enhanced.csv'):
        """Simpan hasil ke file CSV untuk analisis"""
        import csv
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'source', 'title', 'url', 'keyword', 'scraped_date', 'published_date',
                'harga_beras_konsumen', 'harga_padi_produsen', 'harga_gabah_kering',
                'harga_lainnya', 'locations_general', 'locations_kota', 'locations_kabupaten',
                'locations_kecamatan', 'detailed_addresses', 'qualities', 'description'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for article in self.results:
                locs = article['locations']
                prices = article['prices']
                
                # Format harga untuk CSV
                beras_konsumen = '; '.join([p['raw'] for p in prices['beras_konsumen']])
                padi_produsen = '; '.join([p['raw'] for p in prices['padi_produsen']])
                gabah_kering = '; '.join([p['raw'] for p in prices['gabah_kering']])
                harga_lainnya = '; '.join([p['raw'] for p in prices['tidak_terkategori']])
                
                writer.writerow({
                    'source': article['source'],
                    'title': article['title'],
                    'url': article['url'],
                    'keyword': article['keyword'],
                    'scraped_date': article['scraped_date'],
                    'published_date': article.get('published_date', ''),
                    'harga_beras_konsumen': beras_konsumen,
                    'harga_padi_produsen': padi_produsen,
                    'harga_gabah_kering': gabah_kering,
                    'harga_lainnya': harga_lainnya,
                    'locations_general': '; '.join(locs['general']),
                    'locations_kota': '; '.join(locs['kota']),
                    'locations_kabupaten': '; '.join(locs['kabupaten']),
                    'locations_kecamatan': '; '.join(locs['kecamatan']),
                    'detailed_addresses': '; '.join(article['detailed_addresses']),
                    'qualities': '; '.join(article['qualities']),
                    'description': article['description']
                })
        
        logger.info(f"✓ Data disimpan ke {filename}")kecamatan']),
                    'detailed_addresses': '; '.join(article['detailed_addresses']),
                    'qualities': '; '.join(article['qualities']),
                    'description': article['description']
                })
        
        logger.info(f"✓ Data disimpan ke {filename}")
    
    def generate_summary(self):
        """Generate ringkasan hasil scraping yang lebih detail"""
        total_with_price = sum(1 for r in self.results if r['prices'])
        total_with_location = sum(1 for r in self.results if any([
            r['locations']['kota'], 
            r['locations']['kabupaten'],
            r['locations']['kecamatan'],
            r['locations']['general']
        ]))
        total_with_address = sum(1 for r in self.results if r['detailed_addresses'])
        total_with_quality = sum(1 for r in self.results if r['qualities'])
        
        all_cities = []
        all_districts = []
        for r in self.results:
            all_cities.extend(r['locations']['kota'])
            all_districts.extend(r['locations']['kabupaten'])
        
        summary = {
            'total_articles': len(self.results),
            'articles_with_price': total_with_price,
            'articles_with_location': total_with_location,
            'articles_with_detailed_address': total_with_address,
            'articles_with_quality': total_with_quality,
            'scraping_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sources': list(set([r['source'] for r in self.results])),
            'cities_found': list(set(all_cities)),
            'districts_found': list(set(all_districts)),
            'sample_prices': list(set([p for r in self.results for p in r['prices']]))[:30],
            'sample_addresses': list(set([a for r in self.results for a in r['detailed_addresses']]))[:20]
        }
        
        return summary

# Main execution
if __name__ == "__main__":
    print("\n" + "=" * 100)
    print("SCRAPER HARGA BERAS DAN PANGAN POKOK JAWA BARAT - ENHANCED VERSION")
    print("=" * 100 + "\n")
    
    scraper = BeritaPanganScraperEnhanced()
    
    # Jalankan scraping (5 halaman per site, dengan Google News)
    scraper.run_scraping(max_pages_per_site=5, use_google_news=True)
    
    # Simpan hasil dalam berbagai format
    scraper.save_to_json('harga_pangan_jabar_enhanced.json')
    scraper.save_to_text('harga_pangan_jabar_enhanced.txt')
    scraper.save_to_csv('harga_pangan_jabar_enhanced.csv')
    
    # Tampilkan ringkasan
    summary = scraper.generate_summary()
    print("\n" + "=" * 100)
    print("RINGKASAN HASIL SCRAPING")
    print("=" * 100)
    print(f"Total Artikel              : {summary['total_articles']}")
    print(f"Artikel dengan Harga       : {summary['articles_with_price']}")
    print(f"Artikel dengan Lokasi      : {summary['articles_with_location']}")
    print(f"Artikel dengan Alamat Detail: {summary['articles_with_detailed_address']}")
    print(f"Artikel dengan Kualitas    : {summary['articles_with_quality']}")
    print(f"\nSumber: {', '.join(summary['sources'])}")
    print(f"\nKota yang ditemukan ({len(summary['cities_found'])}): ")
    print(f"  {', '.join(summary['cities_found'][:15])}")
    print(f"\nKabupaten yang ditemukan ({len(summary['districts_found'])}): ")
    print(f"  {', '.join(summary['districts_found'][:15])}")
    print(f"\nContoh harga yang ditemukan:")
    for i, price in enumerate(summary['sample_prices'][:10], 1):
        print(f"  {i}. {price}")
    print(f"\nContoh alamat detail yang ditemukan:")
    for i, addr in enumerate(summary['sample_addresses'][:10], 1):
        print(f"  {i}. {addr}")
    print("\n" + "=" * 100)
    print("SELESAI! File output:")
    print("  - harga_pangan_jabar_enhanced.json (format JSON)")
    print("  - harga_pangan_jabar_enhanced.txt (format Text detail)")
    print("  - harga_pangan_jabar_enhanced.csv (format CSV untuk Excel)")
    print("=" * 100 + "\n")