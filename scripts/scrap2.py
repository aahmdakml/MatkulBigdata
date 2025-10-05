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

class BeritaPanganScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # EXPANDED: Lebih banyak variasi keyword
        self.keywords = [
            'harga beras jawa barat', 'harga beras jabar', 'harga beras bandung',
            'harga pangan jawa barat', 'harga sembako jabar', 'harga beras bekasi',
            'harga beras bogor', 'harga beras cirebon', 'harga beras depok',
            'inflasi pangan jawa barat', 'stok beras jawa barat',
            'harga gabah jawa barat', 'bulog jawa barat', 'pasar beras jawa barat',
            'harga beras ciherang', 'harga beras IR64', 'harga beras premium',
            'operasi pasar beras jawa barat', 'stabilitas harga pangan jabar'
        ]
        self.results = []
        
    def extract_price_info(self, text):
        """Ekstrak informasi harga dari teks"""
        prices = []
        # Pattern untuk mendeteksi harga (Rp 10.000, Rp10000, 10000, dll)
        price_patterns = [
            r'Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt|per kg|/kg))?',
            r'[\d.,]+\s*(?:ribu|rb|juta|jt)\s*(?:per kg|/kg)?',
            r'harga\s+[\d.,]+',
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            prices.extend(matches)
        
        return list(set(prices))  # Hilangkan duplikat
    
    def extract_location_info(self, text):
        """Ekstrak informasi lokasi di Jawa Barat"""
        locations = []
        # Daftar kota/kabupaten di Jawa Barat
        jabar_locations = [
            'bandung', 'bekasi', 'bogor', 'cirebon', 'depok', 'sukabumi', 'tasikmalaya',
            'banjar', 'cimahi', 'garut', 'indramayu', 'karawang', 'kuningan', 'majalengka',
            'pangandaran', 'purwakarta', 'subang', 'sumedang', 'cianjur', 'ciamis',
            'bandung barat', 'jawa barat', 'jabar'
        ]
        
        text_lower = text.lower()
        for loc in jabar_locations:
            if loc in text_lower:
                locations.append(loc.title())
        
        return list(set(locations))
    
    def extract_quality_info(self, text):
        """Ekstrak informasi kualitas beras"""
        qualities = []
        quality_keywords = [
            'premium', 'medium', 'kualitas', 'grade', 'super',
            'IR 64', 'IR64', 'Ciherang', 'Slyp', 'Pandan Wangi',
            'kualitas baik', 'kualitas sedang', 'kualitas rendah'
        ]
        
        text_lower = text.lower()
        for quality in quality_keywords:
            if quality.lower() in text_lower:
                qualities.append(quality)
        
        return list(set(qualities))
    
    def scrape_detik(self, keyword, max_pages=3):
        """Scrape berita dari Detik.com"""
        logger.info(f"Scraping Detik.com untuk keyword: {keyword}")
        
        for page in range(1, max_pages + 1):
            try:
                url = f"https://www.detik.com/search/searchall?query={quote(keyword)}&page={page}"
                response = requests.get(url, headers=self.headers, timeout=10)
                
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
                                
                                # Filter hanya berita tentang Jawa Barat
                                full_text = f"{title} {description}".lower()
                                if any(loc in full_text for loc in ['jawa barat', 'jabar', 'bandung', 'bekasi', 'bogor', 'cirebon']):
                                    
                                    # Ekstrak detail dari konten
                                    content = self.get_article_content(link)
                                    combined_text = f"{title} {description} {content}"
                                    
                                    article_data = {
                                        'source': 'Detik.com',
                                        'title': title,
                                        'url': link,
                                        'description': description,
                                        'content': content,
                                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'keyword': keyword,
                                        'prices': self.extract_price_info(combined_text),
                                        'locations': self.extract_location_info(combined_text),
                                        'qualities': self.extract_quality_info(combined_text)
                                    }
                                    
                                    self.results.append(article_data)
                                    logger.info(f"✓ Scraped: {title[:60]}...")
                        
                        except Exception as e:
                            logger.warning(f"Error parsing article: {e}")
                            continue
                    
                    time.sleep(1)  # Rate limiting
                    
            except Exception as e:
                logger.error(f"Error scraping Detik page {page}: {e}")
                continue
    
    def scrape_kompas(self, keyword, max_pages=3):
        """Scrape berita dari Kompas.com"""
        logger.info(f"Scraping Kompas.com untuk keyword: {keyword}")
        
        for page in range(1, max_pages + 1):
            try:
                url = f"https://search.kompas.com/search/?q={quote(keyword)}&page={page}"
                response = requests.get(url, headers=self.headers, timeout=10)
                
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
                                
                                # Filter Jawa Barat
                                full_text = f"{title} {description}".lower()
                                if any(loc in full_text for loc in ['jawa barat', 'jabar', 'bandung', 'bekasi', 'bogor', 'cirebon']):
                                    
                                    content = self.get_article_content(link)
                                    combined_text = f"{title} {description} {content}"
                                    
                                    article_data = {
                                        'source': 'Kompas.com',
                                        'title': title,
                                        'url': link,
                                        'description': description,
                                        'content': content,
                                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'keyword': keyword,
                                        'prices': self.extract_price_info(combined_text),
                                        'locations': self.extract_location_info(combined_text),
                                        'qualities': self.extract_quality_info(combined_text)
                                    }
                                    
                                    self.results.append(article_data)
                                    logger.info(f"✓ Scraped: {title[:60]}...")
                        
                        except Exception as e:
                            logger.warning(f"Error parsing article: {e}")
                            continue
                    
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error scraping Kompas page {page}: {e}")
                continue
    
    def scrape_tribun(self, keyword, max_pages=3):
        """Scrape berita dari Tribunnews (Jabar)"""
        logger.info(f"Scraping Tribunnews untuk keyword: {keyword}")
        
        for page in range(1, max_pages + 1):
            try:
                # Tribun Jabar spesifik
                url = f"https://www.tribunnews.com/search?q={quote(keyword)}&page={page}"
                response = requests.get(url, headers=self.headers, timeout=10)
                
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
                                
                                full_text = f"{title} {description}".lower()
                                if any(loc in full_text for loc in ['jawa barat', 'jabar', 'bandung', 'bekasi', 'bogor']):
                                    
                                    content = self.get_article_content(link)
                                    combined_text = f"{title} {description} {content}"
                                    
                                    article_data = {
                                        'source': 'Tribunnews',
                                        'title': title,
                                        'url': link,
                                        'description': description,
                                        'content': content,
                                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'keyword': keyword,
                                        'prices': self.extract_price_info(combined_text),
                                        'locations': self.extract_location_info(combined_text),
                                        'qualities': self.extract_quality_info(combined_text)
                                    }
                                    
                                    self.results.append(article_data)
                                    logger.info(f"✓ Scraped: {title[:60]}...")
                        
                        except Exception as e:
                            logger.warning(f"Error parsing article: {e}")
                            continue
                    
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error scraping Tribun page {page}: {e}")
                continue
    
    def scrape_antara(self, keyword, max_pages=3):
        """Scrape berita dari Antara News"""
        logger.info(f"Scraping Antara News untuk keyword: {keyword}")
        
        for page in range(1, max_pages + 1):
            try:
                url = f"https://www.antaranews.com/search?q={quote(keyword)}&page={page}"
                response = requests.get(url, headers=self.headers, timeout=10)
                
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
                                
                                full_text = f"{title} {description}".lower()
                                if any(loc in full_text for loc in ['jawa barat', 'jabar', 'bandung', 'bekasi']):
                                    
                                    content = self.get_article_content(link)
                                    combined_text = f"{title} {description} {content}"
                                    
                                    article_data = {
                                        'source': 'Antara News',
                                        'title': title,
                                        'url': link,
                                        'description': description,
                                        'content': content,
                                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'keyword': keyword,
                                        'prices': self.extract_price_info(combined_text),
                                        'locations': self.extract_location_info(combined_text),
                                        'qualities': self.extract_quality_info(combined_text)
                                    }
                                    
                                    self.results.append(article_data)
                                    logger.info(f"✓ Scraped: {title[:60]}...")
                        
                        except Exception as e:
                            logger.warning(f"Error parsing article: {e}")
                            continue
                    
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error scraping Antara page {page}: {e}")
                continue
    
    def get_article_content(self, url):
        """Ambil konten lengkap artikel"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Coba berbagai selector untuk konten artikel
                content_selectors = [
                    {'name': 'div', 'class_': 'detail__body-text'},
                    {'name': 'div', 'class_': 'read__content'},
                    {'name': 'div', 'class_': 'article-content'},
                    {'name': 'article'},
                    {'name': 'div', 'class_': 'content'}
                ]
                
                for selector in content_selectors:
                    content_elem = soup.find(selector['name'], class_=selector.get('class_'))
                    if content_elem:
                        paragraphs = content_elem.find_all('p')
                        return ' '.join([p.get_text(strip=True) for p in paragraphs[:10]])  # Ambil 10 paragraf pertama
                
                return ""
        except Exception as e:
            logger.warning(f"Error fetching article content from {url}: {e}")
            return ""
    
    def run_scraping(self, max_pages_per_site=3):
        """Jalankan scraping untuk semua keywords dan sumber"""
        logger.info("=" * 60)
        logger.info("MULAI SCRAPING DATA HARGA PANGAN JAWA BARAT")
        logger.info("=" * 60)
        
        for keyword in self.keywords:
            logger.info(f"\n--- Keyword: {keyword} ---")
            self.scrape_detik(keyword, max_pages_per_site)
            time.sleep(2)
            self.scrape_kompas(keyword, max_pages_per_site)
            time.sleep(2)
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"SELESAI! Total artikel terkumpul: {len(self.results)}")
        logger.info(f"{'=' * 60}\n")
    
    def save_to_json(self, filename='harga_pangan_jabar.json'):
        """Simpan hasil ke file JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logger.info(f"✓ Data disimpan ke {filename}")
    
    def save_to_text(self, filename='harga_pangan_jabar.txt'):
        """Simpan hasil ke file Text"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("DATA SCRAPING HARGA BERAS/PANGAN POKOK JAWA BARAT\n")
            f.write(f"Tanggal Scraping: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Artikel: {len(self.results)}\n")
            f.write("=" * 80 + "\n\n")
            
            for idx, article in enumerate(self.results, 1):
                f.write(f"\n{'=' * 80}\n")
                f.write(f"ARTIKEL #{idx}\n")
                f.write(f"{'=' * 80}\n")
                f.write(f"Sumber      : {article['source']}\n")
                f.write(f"Judul       : {article['title']}\n")
                f.write(f"URL         : {article['url']}\n")
                f.write(f"Keyword     : {article['keyword']}\n")
                f.write(f"Tanggal     : {article['scraped_date']}\n")
                f.write(f"\nDeskripsi:\n{article['description']}\n")
                
                if article['content']:
                    f.write(f"\nKonten:\n{article['content'][:500]}...\n")
                
                f.write(f"\n--- INFORMASI TERIDENTIFIKASI ---\n")
                f.write(f"Harga       : {', '.join(article['prices']) if article['prices'] else 'Tidak ditemukan'}\n")
                f.write(f"Lokasi      : {', '.join(article['locations']) if article['locations'] else 'Tidak ditemukan'}\n")
                f.write(f"Kualitas    : {', '.join(article['qualities']) if article['qualities'] else 'Tidak ditemukan'}\n")
                f.write("\n")
        
        logger.info(f"✓ Data disimpan ke {filename}")
    
    def generate_summary(self):
        """Generate ringkasan hasil scraping"""
        total_with_price = sum(1 for r in self.results if r['prices'])
        total_with_location = sum(1 for r in self.results if r['locations'])
        total_with_quality = sum(1 for r in self.results if r['qualities'])
        
        summary = {
            'total_articles': len(self.results),
            'articles_with_price': total_with_price,
            'articles_with_location': total_with_location,
            'articles_with_quality': total_with_quality,
            'scraping_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sources': list(set([r['source'] for r in self.results])),
            'all_locations': list(set([loc for r in self.results for loc in r['locations']])),
            'sample_prices': list(set([p for r in self.results for p in r['prices']]))[:20]
        }
        
        return summary

# Main execution
if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SCRAPER HARGA BERAS DAN PANGAN POKOK JAWA BARAT")
    print("=" * 80 + "\n")
    
    scraper = BeritaPanganScraper()
    
    # Jalankan scraping (max 3 halaman per site per keyword)
    scraper.run_scraping(max_pages_per_site=3)
    
    # Simpan hasil
    scraper.save_to_json('harga_pangan_jabar.json')
    scraper.save_to_text('harga_pangan_jabar.txt')
    
    # Tampilkan ringkasan
    summary = scraper.generate_summary()
    print("\n" + "=" * 80)
    print("RINGKASAN HASIL SCRAPING")
    print("=" * 80)
    print(f"Total Artikel          : {summary['total_articles']}")
    print(f"Artikel dengan Harga   : {summary['articles_with_price']}")
    print(f"Artikel dengan Lokasi  : {summary['articles_with_location']}")
    print(f"Artikel dengan Kualitas: {summary['articles_with_quality']}")
    print(f"\nSumber: {', '.join(summary['sources'])}")
    print(f"\nLokasi ditemukan: {', '.join(summary['all_locations'][:10])}")
    print(f"\nContoh harga: {', '.join(summary['sample_prices'][:10])}")
    print("\n" + "=" * 80)
    print("SELESAI! File output:")
    print("  - harga_pangan_jabar.json (format JSON)")
    print("  - harga_pangan_jabar.txt (format Text)")
    print("=" * 80 + "\n")