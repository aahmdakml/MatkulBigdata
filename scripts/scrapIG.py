import instaloader
import re
import json
from datetime import datetime, timedelta
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class InstagramPanganScraper:
    def __init__(self, username, password):
        """
        Initialize Instagram scraper
        
        Args:
            username: Instagram username
            password: Instagram password
        """
        self.L = instaloader.Instaloader(
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern='',
            max_connection_attempts=3
        )
        
        self.username = username
        self.password = password
        self.results = []
        
        # Pattern ekstraksi (sama dengan scraper web)
        self.jabar_locations = {
            'kota': ['bandung', 'bekasi', 'bogor', 'cirebon', 'depok', 'sukabumi', 
                     'tasikmalaya', 'banjar', 'cimahi'],
            'kabupaten': ['bandung barat', 'garut', 'indramayu', 'karawang', 'kuningan',
                         'majalengka', 'pangandaran', 'purwakarta', 'subang', 'sumedang',
                         'cianjur', 'ciamis', 'kabupaten bandung']
        }
    
    def login(self):
        """Login ke Instagram"""
        try:
            logger.info("Mencoba login ke Instagram...")
            self.L.login(self.username, self.password)
            logger.info("✓ Login berhasil!")
            return True
        except Exception as e:
            logger.error(f"✗ Login gagal: {e}")
            logger.info("Tips: Pastikan username dan password benar, atau Instagram mungkin meminta verifikasi")
            return False
    
    def extract_price_info(self, text):
        """Ekstrak informasi harga dari caption"""
        prices = []
        price_patterns = [
            r'Rp\s*[\d.,]+(?:\s*(?:ribu|rb|juta|jt))?\s*(?:per\s*kg|\/kg|per\s*kilogram)?',
            r'[\d.,]+(?:\s*ribu|rb|juta|jt)\s*(?:per\s*kg|\/kg|per\s*kilogram)?',
            r'harga\s+Rp?\s*[\d.,]+',
            r'berkisar\s+Rp?\s*[\d.,]+-+Rp?\s*[\d.,]+',
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            prices.extend(matches)
        
        return list(set(prices))
    
    def extract_location_info(self, text):
        """Ekstrak informasi lokasi"""
        locations = {'kota': [], 'kabupaten': []}
        text_lower = text.lower()
        
        for kota in self.jabar_locations['kota']:
            if kota in text_lower:
                locations['kota'].append(kota.title())
        
        for kab in self.jabar_locations['kabupaten']:
            if kab in text_lower:
                locations['kabupaten'].append(kab.title())
        
        for key in locations:
            locations[key] = list(set(locations[key]))
        
        return locations
    
    def extract_quality_info(self, text):
        """Ekstrak informasi kualitas"""
        qualities = []
        quality_keywords = [
            'premium', 'super', 'medium', 'IR 64', 'IR64', 'Ciherang', 
            'Pandan Wangi', 'Mentik', 'Rojolele', 'kualitas baik'
        ]
        
        text_lower = text.lower()
        for quality in quality_keywords:
            if quality.lower() in text_lower:
                qualities.append(quality)
        
        return list(set(qualities))
    
    def extract_commodities(self, text):
        """Ekstrak jenis komoditas pangan"""
        commodities = []
        commodity_list = [
            'beras', 'gula', 'minyak goreng', 'tepung', 'daging ayam', 
            'daging sapi', 'telur', 'cabai', 'bawang merah', 'bawang putih',
            'kedelai', 'jagung', 'garam', 'mie instan'
        ]
        
        text_lower = text.lower()
        for commodity in commodity_list:
            if commodity in text_lower:
                commodities.append(commodity.title())
        
        return list(set(commodities))
    
    def scrape_user_posts(self, username, max_posts=100, days_back=365):
        """
        Scrape posts dari user tertentu
        
        Args:
            username: Instagram username (tanpa @)
            max_posts: Maksimum jumlah post yang akan di-scrape
            days_back: Hanya ambil post dalam X hari terakhir
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Scraping posts dari @{username}")
        logger.info(f"{'='*80}")
        
        try:
            profile = instaloader.Profile.from_username(self.L.context, username)
            
            cutoff_date = datetime.now() - timedelta(days=days_back)
            count = 0
            
            for post in profile.get_posts():
                # Cek tanggal
                if post.date < cutoff_date:
                    logger.info(f"Mencapai batas tanggal ({days_back} hari)")
                    break
                
                if count >= max_posts:
                    logger.info(f"Mencapai batas maksimum post ({max_posts})")
                    break
                
                # Ekstrak data
                caption = post.caption if post.caption else ""
                
                # Filter: hanya ambil post yang relevan dengan pangan
                if not any(word in caption.lower() for word in ['harga', 'pangan', 'beras', 'sembako', 'pasar']):
                    continue
                
                locations = self.extract_location_info(caption)
                prices = self.extract_price_info(caption)
                qualities = self.extract_quality_info(caption)
                commodities = self.extract_commodities(caption)
                
                post_data = {
                    'source': 'Instagram',
                    'account': f"@{username}",
                    'post_url': f"https://www.instagram.com/p/{post.shortcode}/",
                    'caption': caption,
                    'date': post.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'likes': post.likes,
                    'comments': post.comments,
                    'hashtags': post.caption_hashtags if post.caption_hashtags else [],
                    'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'prices': prices,
                    'locations': locations,
                    'qualities': qualities,
                    'commodities': commodities
                }
                
                self.results.append(post_data)
                count += 1
                logger.info(f"✓ Post {count}/{max_posts} - {post.date.strftime('%Y-%m-%d')} - {len(caption)} chars")
                
                # Rate limiting
                time.sleep(2)
            
            logger.info(f"Selesai scraping @{username}: {count} posts")
            
        except Exception as e:
            logger.error(f"Error scraping @{username}: {e}")
    
    def scrape_hashtag(self, hashtag, max_posts=100):
        """
        Scrape posts dengan hashtag tertentu
        
        Args:
            hashtag: Hashtag tanpa #
            max_posts: Maksimum jumlah post
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Scraping hashtag #{hashtag}")
        logger.info(f"{'='*80}")
        
        try:
            count = 0
            
            for post in instaloader.Hashtag.from_name(self.L.context, hashtag).get_posts():
                if count >= max_posts:
                    logger.info(f"Mencapai batas maksimum post ({max_posts})")
                    break
                
                caption = post.caption if post.caption else ""
                
                # Filter: harus ada kata kunci Jawa Barat atau kota di Jabar
                locations = self.extract_location_info(caption)
                if not (locations['kota'] or locations['kabupaten'] or 
                       'jawa barat' in caption.lower() or 'jabar' in caption.lower()):
                    continue
                
                prices = self.extract_price_info(caption)
                qualities = self.extract_quality_info(caption)
                commodities = self.extract_commodities(caption)
                
                post_data = {
                    'source': 'Instagram',
                    'account': f"@{post.owner_username}",
                    'post_url': f"https://www.instagram.com/p/{post.shortcode}/",
                    'caption': caption,
                    'date': post.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'likes': post.likes,
                    'comments': post.comments,
                    'hashtags': post.caption_hashtags if post.caption_hashtags else [],
                    'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'prices': prices,
                    'locations': locations,
                    'qualities': qualities,
                    'commodities': commodities
                }
                
                self.results.append(post_data)
                count += 1
                logger.info(f"✓ Post {count}/{max_posts} dari @{post.owner_username}")
                
                # Rate limiting
                time.sleep(3)
            
            logger.info(f"Selesai scraping #{hashtag}: {count} posts")
            
        except Exception as e:
            logger.error(f"Error scraping #{hashtag}: {e}")
    
    def save_to_json(self, filename='instagram_pangan_jabar.json'):
        """Simpan hasil ke JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logger.info(f"✓ Data disimpan ke {filename}")
    
    def save_to_text(self, filename='instagram_pangan_jabar.txt'):
        """Simpan hasil ke Text"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write("DATA SCRAPING INSTAGRAM - HARGA PANGAN JAWA BARAT\n")
            f.write(f"Tanggal Scraping: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Posts: {len(self.results)}\n")
            f.write("=" * 100 + "\n\n")
            
            for idx, post in enumerate(self.results, 1):
                f.write(f"\n{'='*100}\n")
                f.write(f"POST #{idx}\n")
                f.write(f"{'='*100}\n")
                f.write(f"Akun         : {post['account']}\n")
                f.write(f"URL          : {post['post_url']}\n")
                f.write(f"Tanggal Post : {post['date']}\n")
                f.write(f"Likes        : {post['likes']}\n")
                f.write(f"Comments     : {post['comments']}\n")
                f.write(f"Hashtags     : {', '.join(post['hashtags'][:10])}\n")
                
                f.write(f"\nCaption:\n{post['caption']}\n")
                
                f.write(f"\n{'-'*100}\n")
                f.write(f"INFORMASI TERIDENTIFIKASI\n")
                f.write(f"{'-'*100}\n")
                
                f.write(f"\n💰 HARGA:\n")
                if post['prices']:
                    for price in post['prices']:
                        f.write(f"  • {price}\n")
                else:
                    f.write(f"  Tidak ditemukan\n")
                
                f.write(f"\n📦 KOMODITAS:\n")
                if post['commodities']:
                    for comm in post['commodities']:
                        f.write(f"  • {comm}\n")
                else:
                    f.write(f"  Tidak ditemukan\n")
                
                f.write(f"\n📍 LOKASI:\n")
                locs = post['locations']
                if locs['kota']:
                    f.write(f"  Kota: {', '.join(locs['kota'])}\n")
                if locs['kabupaten']:
                    f.write(f"  Kabupaten: {', '.join(locs['kabupaten'])}\n")
                if not (locs['kota'] or locs['kabupaten']):
                    f.write(f"  Tidak ditemukan\n")
                
                f.write(f"\n⭐ KUALITAS:\n")
                if post['qualities']:
                    for qual in post['qualities']:
                        f.write(f"  • {qual}\n")
                else:
                    f.write(f"  Tidak ditemukan\n")
                
                f.write("\n")
        
        logger.info(f"✓ Data disimpan ke {filename}")
    
    def generate_summary(self):
        """Generate ringkasan"""
        total_with_price = sum(1 for r in self.results if r['prices'])
        total_with_location = sum(1 for r in self.results if r['locations']['kota'] or r['locations']['kabupaten'])
        
        all_commodities = []
        all_accounts = []
        for r in self.results:
            all_commodities.extend(r['commodities'])
            all_accounts.append(r['account'])
        
        return {
            'total_posts': len(self.results),
            'posts_with_price': total_with_price,
            'posts_with_location': total_with_location,
            'unique_accounts': list(set(all_accounts)),
            'commodities_found': list(set(all_commodities)),
            'date_range': {
                'earliest': min([r['date'] for r in self.results]) if self.results else None,
                'latest': max([r['date'] for r in self.results]) if self.results else None
            }
        }

# Main execution
if __name__ == "__main__":
    print("\n" + "=" * 100)
    print("INSTAGRAM SCRAPER - HARGA PANGAN JAWA BARAT")
    print("=" * 100 + "\n")
    
    # ========================================
    # KONFIGURASI - GANTI DENGAN DATA ANDA
    # ========================================
    IG_USERNAME = "rndmgyinthekos"  # Ganti dengan username Anda
    IG_PASSWORD = "12345678abcdefg"  # Ganti dengan password Anda
    
    # Target scraping
    TARGET_ACCOUNT = "disperdagin_kabbdg"  # Akun target
    TARGET_HASHTAG = "hargapanganpokokpenting"  # Hashtag target (tanpa #)
    
    print("⚠️  PENTING: Ganti IG_USERNAME dan IG_PASSWORD di script ini!")
    print("=" * 100 + "\n")
    
    # Initialize scraper
    scraper = InstagramPanganScraper(IG_USERNAME, IG_PASSWORD)
    
    # Login
    if scraper.login():
        # Scrape dari akun target
        scraper.scrape_user_posts(TARGET_ACCOUNT, max_posts=100, days_back=365)
        
        # Scrape dari hashtag
        scraper.scrape_hashtag(TARGET_HASHTAG, max_posts=100)
        
        # Simpan hasil
        scraper.save_to_json('instagram_pangan_jabar.json')
        scraper.save_to_text('instagram_pangan_jabar.txt')
        
        # Tampilkan ringkasan
        summary = scraper.generate_summary()
        print("\n" + "=" * 100)
        print("RINGKASAN HASIL SCRAPING")
        print("=" * 100)
        print(f"Total Posts              : {summary['total_posts']}")
        print(f"Posts dengan Harga       : {summary['posts_with_price']}")
        print(f"Posts dengan Lokasi      : {summary['posts_with_location']}")
        print(f"\nAkun yang ditemukan: {', '.join(summary['unique_accounts'][:10])}")
        print(f"\nKomoditas: {', '.join(summary['commodities_found'][:15])}")
        if summary['date_range']['earliest']:
            print(f"\nRentang tanggal: {summary['date_range']['earliest']} s/d {summary['date_range']['latest']}")
        print("\n" + "=" * 100)
        print("SELESAI!")
        print("=" * 100 + "\n")
    else:
        print("\n✗ Gagal login. Scraping dibatalkan.")