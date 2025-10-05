"""
SAFE SOCIAL MEDIA SCRAPER
Fokus: Instagram + Twitter + Government Data
Compliance: Public data only, respect rate limits
"""

import instaloader
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta
import logging
import time
import subprocess

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SafeSocialMediaScraper:
    def __init__(self):
        self.results = []
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Jabar locations for filtering
        self.jabar_keywords = [
            'jawa barat', 'jabar', 'bandung', 'bekasi', 'bogor', 'cirebon', 
            'depok', 'sukabumi', 'tasikmalaya', 'garut', 'karawang'
        ]
    
    # ==========================================
    # UTILITY FUNCTIONS
    # ==========================================
    def extract_price_info(self, text):
        """Ekstrak harga dari teks"""
        prices = []
        patterns = [
            r'Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?\s*(?:per\s*kg|\/kg)?',
            r'[\d.,]+\s*(?:ribu|rb|juta|jt)\s*(?:per\s*kg|\/kg)?',
        ]
        for pattern in patterns:
            prices.extend(re.findall(pattern, text, re.IGNORECASE))
        return list(set(prices))
    
    def extract_locations(self, text):
        """Ekstrak lokasi Jabar"""
        locations = []
        text_lower = text.lower()
        for keyword in self.jabar_keywords:
            if keyword in text_lower:
                locations.append(keyword.title())
        return list(set(locations))
    
    def extract_commodities(self, text):
        """Ekstrak komoditas pangan"""
        commodities = []
        commodity_list = [
            'beras', 'gula', 'minyak goreng', 'tepung', 'daging ayam', 
            'daging sapi', 'telur', 'cabai', 'bawang merah', 'bawang putih'
        ]
        text_lower = text.lower()
        for commodity in commodity_list:
            if commodity in text_lower:
                commodities.append(commodity.title())
        return list(set(commodities))
    
    # ==========================================
    # 1. INSTAGRAM SCRAPER (INSTALOADER)
    # ==========================================
    def scrape_instagram(self, username, password, targets):
        """
        Scrape Instagram menggunakan Instaloader
        
        Args:
            username: Instagram username
            password: Instagram password
            targets: Dict dengan format:
                {
                    'accounts': ['account1', 'account2'],
                    'hashtags': ['hashtag1', 'hashtag2']
                }
        """
        logger.info("\n" + "="*80)
        logger.info("📸 SCRAPING INSTAGRAM (PUBLIC DATA ONLY)")
        logger.info("="*80)
        
        try:
            # Initialize Instaloader
            L = instaloader.Instaloader(
                download_videos=False,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False
            )
            
            # Login
            logger.info(f"Login ke Instagram sebagai @{username}...")
            try:
                L.login(username, password)
                logger.info("✓ Login berhasil!")
            except Exception as e:
                logger.error(f"✗ Login gagal: {e}")
                logger.info("Tips: Pastikan username/password benar. IG mungkin minta verifikasi.")
                return
            
            # Scrape from accounts
            for account in targets.get('accounts', []):
                logger.info(f"\n→ Scraping @{account}...")
                try:
                    profile = instaloader.Profile.from_username(L.context, account)
                    count = 0
                    cutoff_date = datetime.now() - timedelta(days=365)
                    
                    for post in profile.get_posts():
                        if post.date < cutoff_date:
                            break
                        if count >= 100:  # Max 100 posts per account
                            break
                        
                        caption = post.caption if post.caption else ""
                        
                        # Filter: must be about pangan/harga
                        if not any(word in caption.lower() for word in ['harga', 'pangan', 'beras', 'sembako']):
                            continue
                        
                        data = {
                            'source': 'Instagram',
                            'account': f"@{account}",
                            'url': f"https://www.instagram.com/p/{post.shortcode}/",
                            'caption': caption,
                            'date': post.date.strftime('%Y-%m-%d'),
                            'likes': post.likes,
                            'comments': post.comments,
                            'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'prices': self.extract_price_info(caption),
                            'locations': self.extract_locations(caption),
                            'commodities': self.extract_commodities(caption)
                        }
                        
                        self.results.append(data)
                        count += 1
                        logger.info(f"  ✓ Post {count} - {post.date.strftime('%Y-%m-%d')}")
                        time.sleep(5)  # Rate limiting
                    
                    logger.info(f"✓ Selesai @{account}: {count} posts")
                
                except Exception as e:
                    logger.error(f"✗ Error scraping @{account}: {e}")
                
                time.sleep(5)  # Delay antar akun
            
            
            # Scrape from hashtags
            for hashtag in targets.get('hashtags', []):
                logger.info(f"\n→ Scraping #{hashtag}...")
                try:
                    count = 0
                    for post in instaloader.Hashtag.from_name(L.context, hashtag).get_posts():
                        if count >= 50:  # Max 50 posts per hashtag
                            break
                        
                        caption = post.caption if post.caption else ""
                        
                        # Filter: must mention Jabar
                        locations = self.extract_locations(caption)
                        if not locations:
                            continue
                        
                        data = {
                            'source': 'Instagram',
                            'account': f"@{post.owner_username}",
                            'url': f"https://www.instagram.com/p/{post.shortcode}/",
                            'caption': caption,
                            'date': post.date.strftime('%Y-%m-%d'),
                            'likes': post.likes,
                            'comments': post.comments,
                            'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'prices': self.extract_price_info(caption),
                            'locations': locations,
                            'commodities': self.extract_commodities(caption)
                        }
                        
                        self.results.append(data)
                        count += 1
                        logger.info(f"  ✓ Post {count} dari @{post.owner_username}")
                        time.sleep(5)  # Rate limiting
                    
                    logger.info(f"✓ Selesai #{hashtag}: {count} posts")
                
                except Exception as e:
                    logger.error(f"✗ Error scraping #{hashtag}: {e}")
                
                time.sleep(5)
        
        except Exception as e:
            logger.error(f"✗ Error Instagram scraping: {e}")
    
    # ==========================================
    # 2. TWITTER/X SCRAPER (SNSCRAPE)
    # ==========================================
    def scrape_twitter_snscrape(self, keywords, max_tweets=100):
        """
        Scrape Twitter menggunakan snscrape (legal, no API needed)
        
        Args:
            keywords: List of keywords to search
            max_tweets: Maximum tweets per keyword
        """
        logger.info("\n" + "="*80)
        logger.info("🐦 SCRAPING TWITTER/X (PUBLIC TWEETS ONLY)")
        logger.info("="*80)
        
        try:
            import snscrape.modules.twitter as sntwitter
            
            for keyword in keywords:
                logger.info(f"\n→ Searching: {keyword}")
                
                query = f"{keyword} jawa barat OR bandung OR bekasi lang:id"
                count = 0
                
                try:
                    for tweet in sntwitter.TwitterSearchScraper(query).get_items():
                        if count >= max_tweets:
                            break
                        
                        # Filter: must contain location
                        locations = self.extract_locations(tweet.content)
                        if not locations:
                            continue
                        
                        data = {
                            'source': 'Twitter/X',
                            'account': f"@{tweet.user.username}",
                            'url': tweet.url,
                            'content': tweet.content,
                            'date': tweet.date.strftime('%Y-%m-%d'),
                            'likes': tweet.likeCount,
                            'retweets': tweet.retweetCount,
                            'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'prices': self.extract_price_info(tweet.content),
                            'locations': locations,
                            'commodities': self.extract_commodities(tweet.content)
                        }
                        
                        self.results.append(data)
                        count += 1
                        logger.info(f"  ✓ Tweet {count} dari @{tweet.user.username}")
                    
                    logger.info(f"✓ Selesai keyword '{keyword}': {count} tweets")
                
                except Exception as e:
                    logger.error(f"✗ Error searching '{keyword}': {e}")
                
                time.sleep(3)
        
        except ImportError:
            logger.error("✗ snscrape tidak terinstall. Install dengan: pip install snscrape")
            logger.info("Alternatif: Gunakan Twitter API atau skip Twitter scraping")
    
    # ==========================================
    # 3. GOVERNMENT WEBSITES SCRAPER
    # ==========================================
    def scrape_government_data(self):
        """
        Scrape dari website pemerintah (100% legal)
        """
        logger.info("\n" + "="*80)
        logger.info("🏛️ SCRAPING GOVERNMENT WEBSITES (OPEN DATA)")
        logger.info("="*80)
        
        gov_sources = [
            {
                'name': 'PIHPS Nasional',
                'url': 'https://pihps.kemendag.go.id/ajax/harga',
                'method': 'api'
            },
            {
                'name': 'Disperindag Jabar',
                'url': 'https://disperindag.jabarprov.go.id',
                'method': 'scrape'
            },
            {
                'name': 'Jabar Open Data',
                'url': 'https://opendata.jabarprov.go.id',
                'method': 'scrape'
            }
        ]
        
        for source in gov_sources:
            logger.info(f"\n→ Scraping {source['name']}...")
            
            try:
                if source['method'] == 'api':
                    self._scrape_pihps_api()
                else:
                    self._scrape_gov_website(source['url'], source['name'])
                
                time.sleep(2)
            
            except Exception as e:
                logger.error(f"✗ Error scraping {source['name']}: {e}")
    
    def _scrape_pihps_api(self):
        """Scrape PIHPS (Panel Harga Pangan Strategis)"""
        try:
            # PIHPS memiliki API terbuka
            url = "https://pihps.kemendag.go.id/ajax/harga"
            
            # Komoditas pangan strategis
            commodities = ['beras', 'gula', 'minyak goreng', 'daging ayam', 'telur']
            
            for commodity in commodities:
                payload = {
                    'komoditas': commodity,
                    'provinsi': '32',  # Kode Jawa Barat
                }
                
                response = requests.post(url, data=payload, headers=self.headers, timeout=15)
                
                if response.status_code == 200:
                    try:
                        data_json = response.json()
                        
                        if 'data' in data_json:
                            for item in data_json['data']:
                                data = {
                                    'source': 'PIHPS Kemendag',
                                    'commodity': commodity.title(),
                                    'location': item.get('kota', 'Jawa Barat'),
                                    'price': item.get('harga', ''),
                                    'unit': 'per kg',
                                    'date': item.get('tanggal', ''),
                                    'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'prices': [item.get('harga', '')],
                                    'locations': [item.get('kota', 'Jawa Barat')],
                                    'commodities': [commodity.title()]
                                }
                                
                                self.results.append(data)
                        
                        logger.info(f"  ✓ {commodity}: OK")
                    
                    except json.JSONDecodeError:
                        logger.warning(f"  ⚠ {commodity}: Invalid JSON response")
            
            logger.info(f"✓ PIHPS scraping complete")
        
        except Exception as e:
            logger.error(f"✗ Error scraping PIHPS: {e}")
    
    def _scrape_gov_website(self, url, name):
        """Scrape government website"""
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Cari artikel tentang harga pangan
                articles = soup.find_all(['article', 'div'], class_=re.compile('(post|article|news|berita)', re.I))
                
                count = 0
                for article in articles[:20]:
                    try:
                        title_elem = article.find(['h1', 'h2', 'h3', 'h4'])
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        
                        # Filter: harus tentang harga/pangan
                        if not any(word in title.lower() for word in ['harga', 'pangan', 'beras', 'sembako']):
                            continue
                        
                        link_elem = article.find('a', href=True)
                        link = link_elem['href'] if link_elem else ""
                        if link and not link.startswith('http'):
                            link = url.rstrip('/') + '/' + link.lstrip('/')
                        
                        content_elem = article.find('p')
                        content = content_elem.get_text(strip=True) if content_elem else ""
                        
                        full_text = f"{title} {content}"
                        
                        data = {
                            'source': name,
                            'title': title,
                            'url': link,
                            'content': content[:500],
                            'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'prices': self.extract_price_info(full_text),
                            'locations': self.extract_locations(full_text),
                            'commodities': self.extract_commodities(full_text)
                        }
                        
                        self.results.append(data)
                        count += 1
                    
                    except Exception as e:
                        continue
                
                logger.info(f"  ✓ Found {count} articles")
        
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")
    
    # ==========================================
    # SAVE FUNCTIONS
    # ==========================================
    def save_to_json(self, filename='social_gov_data_jabar.json'):
        """Simpan ke JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logger.info(f"\n✓ Data disimpan ke {filename}")
    
    def save_to_text(self, filename='social_gov_data_jabar.txt'):
        """Simpan ke Text"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write("DATA SCRAPING - SOSIAL MEDIA & GOVERNMENT DATA\n")
            f.write("Sumber: Instagram, Twitter/X, Government Websites\n")
            f.write(f"Total Records: {len(self.results)}\n")
            f.write(f"Tanggal: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 100 + "\n\n")
            
            for idx, item in enumerate(self.results, 1):
                f.write(f"\n{'='*100}\n")
                f.write(f"RECORD #{idx}\n")
                f.write(f"{'='*100}\n")
                f.write(f"Sumber     : {item.get('source', 'N/A')}\n")
                
                if 'account' in item:
                    f.write(f"Akun       : {item['account']}\n")
                if 'url' in item:
                    f.write(f"URL        : {item['url']}\n")
                if 'title' in item:
                    f.write(f"Judul      : {item['title']}\n")
                
                f.write(f"Tanggal    : {item.get('date', 'N/A')}\n")
                
                # Content
                content_key = 'caption' if 'caption' in item else 'content'
                if content_key in item:
                    f.write(f"\nKonten:\n{item[content_key][:500]}\n")
                
                # Extracted info
                f.write(f"\n{'-'*100}\n")
                f.write(f"INFORMASI TEREKSTRAK\n")
                f.write(f"{'-'*100}\n")
                f.write(f"💰 Harga     : {', '.join(item['prices']) if item['prices'] else 'N/A'}\n")
                f.write(f"📍 Lokasi    : {', '.join(item['locations']) if item['locations'] else 'N/A'}\n")
                f.write(f"📦 Komoditas : {', '.join(item['commodities']) if item['commodities'] else 'N/A'}\n")
                f.write("\n")
        
        logger.info(f"✓ Data disimpan ke {filename}")
    
    def generate_summary(self):
        """Generate summary statistics"""
        if not self.results:
            return {
                'total': 0,
                'by_source': {},
                'with_price': 0,
                'with_location': 0
            }
        
        summary = {
            'total': len(self.results),
            'by_source': {},
            'with_price': 0,
            'with_location': 0,
            'with_commodity': 0,
            'unique_locations': set(),
            'unique_commodities': set()
        }
        
        for item in self.results:
            # Count by source
            source = item.get('source', 'Unknown')
            summary['by_source'][source] = summary['by_source'].get(source, 0) + 1
            
            # Count with data
            if item.get('prices'):
                summary['with_price'] += 1
            if item.get('locations'):
                summary['with_location'] += 1
                summary['unique_locations'].update(item['locations'])
            if item.get('commodities'):
                summary['with_commodity'] += 1
                summary['unique_commodities'].update(item['commodities'])
        
        summary['unique_locations'] = list(summary['unique_locations'])
        summary['unique_commodities'] = list(summary['unique_commodities'])
        
        return summary

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("\n" + "=" * 100)
    print("SAFE SOCIAL MEDIA & GOVERNMENT DATA SCRAPER")
    print("Fokus: Instagram + Twitter/X + Government Websites")
    print("=" * 100 + "\n")
    
    # ==========================================
    # KONFIGURASI
    # ==========================================
    print("⚙️ KONFIGURASI:")
    print("="*100)
    
    # Instagram credentials
    IG_USERNAME = "rndmgyinthekos"  # Ganti dengan username Anda
    IG_PASSWORD = "abcdefg12345678abcdefg"  # Ganti dengan password Anda
    
    # Instagram targets
    INSTAGRAM_TARGETS = {
        'accounts': [
            'disperdagin_kabbdg',
            # Tambahkan akun lain jika ada
        ],
        'hashtags': [
            'hargapanganpokokpenting',
            # Tambahkan hashtag lain jika ada
        ]
    }
    
    # Twitter keywords
    TWITTER_KEYWORDS = [
        'harga pangan',
        'harga beras',
        'harga sembako'
    ]
    
    print("\n" + "="*100)
    print("🚀 MULAI SCRAPING...")
    print("="*100)
    
    scraper = SafeSocialMediaScraper()
    
    # 1. Instagram
    scraper.scrape_instagram(IG_USERNAME, IG_PASSWORD, INSTAGRAM_TARGETS)
    
    # 2. Twitter/X
    scraper.scrape_twitter_snscrape(TWITTER_KEYWORDS, max_tweets=100)
    
    # 3. Government Data
    scraper.scrape_government_data()
    
    # ==========================================
    # SAVE RESULTS
    # ==========================================
    print("\n" + "="*100)
    print("💾 MENYIMPAN HASIL...")
    print("="*100)
    
    scraper.save_to_json('social_gov_data_jabar.json')
    scraper.save_to_text('social_gov_data_jabar.txt')
    
    # ==========================================
    # SUMMARY
    # ==========================================
    summary = scraper.generate_summary()
    
    print("\n" + "="*100)
    print("📊 RINGKASAN HASIL")
    print("="*100)
    print(f"Total Records          : {summary['total']}")
    print(f"Records dengan Harga   : {summary['with_price']}")
    print(f"Records dengan Lokasi  : {summary['with_location']}")
    print(f"Records dengan Komoditas: {summary['with_commodity']}")
    
    print(f"\n📁 Breakdown per Sumber:")
    for source, count in summary['by_source'].items():
        print(f"  • {source:30s}: {count:3d} records")
    
    print(f"\n📍 Lokasi Ditemukan ({len(summary['unique_locations'])}):")
    print(f"  {', '.join(summary['unique_locations'][:15])}")
    
    print(f"\n📦 Komoditas Ditemukan ({len(summary['unique_commodities'])}):")
    print(f"  {', '.join(summary['unique_commodities'][:15])}")
    
    print("\n" + "="*100)
    print("✅ SELESAI!")
    print("="*100)
    print("\nFile output:")
    print("  - social_gov_data_jabar.json")
    print("  - social_gov_data_jabar.txt")
    print("\n" + "="*100 + "\n")