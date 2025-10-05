"""
Twitter Scraper menggunakan Selenium untuk Data Beras/Padi Jawa Barat
Target: 1000 tweets dengan informasi harga beras/padi
Output: JSON format yang rapi dan terstruktur

Features:
- Scraping tanpa API key
- Auto-scroll untuk load lebih banyak tweets
- Extract data: harga, kualitas, lokasi
- Confidence scoring system
- Export ke JSON & Excel

Dependencies:
pip install selenium webdriver-manager pandas openpyxl
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
import pandas as pd
from datetime import datetime, timedelta
import re
from typing import List, Dict
import random

class TwitterSeleniumScraper:
    def __init__(self, headless: bool = False):
        """
        Initialize Twitter scraper dengan Selenium
        
        Args:
            headless: True untuk run di background, False untuk lihat browser
        """
        self.all_tweets = []
        self.scraped_tweet_ids = set()  # Track duplicate
        self.setup_driver(headless)
        
    def setup_driver(self, headless: bool):
        """Setup Selenium WebDriver dengan Chrome"""
        print("🔧 Setting up Chrome WebDriver...")
        
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument('--headless')
        
        # Anti-detection options
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Disable notifications
        prefs = {
            "profile.default_content_setting_values.notifications": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            self.wait = WebDriverWait(self.driver, 10)
            print("✅ Chrome WebDriver berhasil diinisialisasi")
        except Exception as e:
            print(f"❌ Error setup driver: {e}")
            raise
    
    def login_twitter(self, username: str, password: str):
        """
        Login ke Twitter/X
        
        Args:
            username: Twitter username atau email
            password: Twitter password
        """
        print("\n🔐 Logging in to Twitter...")
        
        try:
            self.driver.get("https://twitter.com/i/flow/login")
            time.sleep(3)
            
            # Input username
            print("   Memasukkan username...")
            username_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
            )
            username_input.send_keys(username)
            username_input.send_keys(Keys.RETURN)
            time.sleep(2)
            
            # Cek jika ada unusual activity check (phone/email verification)
            try:
                verification_input = self.driver.find_element(By.CSS_SELECTOR, 'input[data-testid="ocfEnterTextTextInput"]')
                print("   ⚠️ Twitter meminta verifikasi tambahan!")
                print("   Silakan masukkan email/phone Anda:")
                verification = input("   Verification (email/phone): ").strip()
                verification_input.send_keys(verification)
                verification_input.send_keys(Keys.RETURN)
                time.sleep(2)
            except:
                pass
            
            # Input password
            print("   Memasukkan password...")
            password_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
            )
            password_input.send_keys(password)
            password_input.send_keys(Keys.RETURN)
            time.sleep(5)
            
            # Verify login success
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="AppTabBar_Home_Link"]'))
                )
                print("✅ Login berhasil!")
                return True
            except:
                print("❌ Login gagal atau memerlukan verifikasi tambahan")
                return False
                
        except Exception as e:
            print(f"❌ Error saat login: {e}")
            return False
    
    def search_twitter(self, query: str, max_tweets: int = 200):
        """
        Search Twitter dengan query tertentu
        
        Args:
            query: Search query (e.g., "harga beras jawa barat")
            max_tweets: Maximum tweets to scrape
        """
        print(f"\n🔍 Searching Twitter: '{query}'")
        print(f"   Target: {max_tweets} tweets")
        
        try:
            # Navigate to search
            search_url = f"https://twitter.com/search?q={query.replace(' ', '%20')}&src=typed_query&f=live"
            self.driver.get(search_url)
            time.sleep(5)
            
            tweets_data = []
            scroll_attempts = 0
            max_scroll_attempts = 50  # Maksimal scroll
            no_new_tweets_count = 0
            
            while len(tweets_data) < max_tweets and scroll_attempts < max_scroll_attempts:
                # Extract tweets dari halaman saat ini
                new_tweets = self.extract_tweets_from_page()
                
                # Tambahkan hanya tweets yang belum ada
                for tweet in new_tweets:
                    if tweet['id'] not in self.scraped_tweet_ids and len(tweets_data) < max_tweets:
                        tweets_data.append(tweet)
                        self.scraped_tweet_ids.add(tweet['id'])
                
                print(f"   Progress: {len(tweets_data)}/{max_tweets} tweets", end='\r')
                
                # Cek jika tidak ada tweet baru
                if len(new_tweets) == 0:
                    no_new_tweets_count += 1
                    if no_new_tweets_count >= 3:
                        print(f"\n   ⚠️ Tidak ada tweet baru setelah 3x scroll")
                        break
                else:
                    no_new_tweets_count = 0
                
                # Scroll down
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))  # Random delay
                scroll_attempts += 1
            
            print(f"\n✅ Berhasil scrape {len(tweets_data)} tweets untuk query: '{query}'")
            return tweets_data
            
        except Exception as e:
            print(f"\n❌ Error saat search: {e}")
            return tweets_data
    
    def extract_tweets_from_page(self) -> List[Dict]:
        """
        Extract semua tweets dari halaman yang sedang ditampilkan
        """
        tweets = []
        
        try:
            # Find all tweet articles
            tweet_elements = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
            
            for tweet_elem in tweet_elements:
                try:
                    tweet_data = self.extract_single_tweet(tweet_elem)
                    if tweet_data:
                        tweets.append(tweet_data)
                except Exception as e:
                    continue
                    
        except Exception as e:
            pass
        
        return tweets
    
    def extract_single_tweet(self, tweet_element) -> Dict:
        """
        Extract data dari single tweet element
        """
        try:
            # Generate unique ID dari tweet element
            tweet_id = str(hash(tweet_element.text))
            
            # Extract username
            try:
                username = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="User-Name"] a').get_attribute('href').split('/')[-1]
            except:
                username = "unknown"
            
            # Extract tweet text
            try:
                tweet_text = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="tweetText"]').text
            except:
                return None  # Skip jika tidak ada text
            
            # Extract timestamp
            try:
                time_element = tweet_element.find_element(By.CSS_SELECTOR, 'time')
                timestamp = time_element.get_attribute('datetime')
            except:
                timestamp = datetime.now().isoformat()
            
            # Extract engagement metrics
            try:
                replies = self.extract_metric(tweet_element, 'reply')
                retweets = self.extract_metric(tweet_element, 'retweet')
                likes = self.extract_metric(tweet_element, 'like')
            except:
                replies = retweets = likes = 0
            
            # Extract URL
            try:
                tweet_url = tweet_element.find_element(By.CSS_SELECTOR, 'a[href*="/status/"]').get_attribute('href')
            except:
                tweet_url = None
            
            tweet_data = {
                'id': tweet_id,
                'username': username,
                'text': tweet_text,
                'timestamp': timestamp,
                'url': tweet_url,
                'replies': replies,
                'retweets': retweets,
                'likes': likes,
                'platform': 'Twitter'
            }
            
            return tweet_data
            
        except Exception as e:
            return None
    
    def extract_metric(self, tweet_element, metric_type: str) -> int:
        """Extract engagement metric (replies, retweets, likes)"""
        try:
            selector = f'[data-testid="{metric_type}"]'
            metric_elem = tweet_element.find_element(By.CSS_SELECTOR, selector)
            metric_text = metric_elem.get_attribute('aria-label')
            
            # Extract number dari text
            numbers = re.findall(r'\d+', metric_text)
            if numbers:
                return int(numbers[0])
            return 0
        except:
            return 0
    
    def extract_data_from_tweet(self, tweet: Dict) -> Dict:
        """
        Extract informasi harga, kualitas, lokasi dari tweet text
        """
        text = tweet['text']
        text_lower = text.lower()
        
        # Mulai dengan data tweet original
        extracted = {
            'id': tweet['id'],
            'tanggal': tweet['timestamp'],
            'username': tweet['username'],
            'platform': tweet['platform'],
            'text_original': text,
            'url': tweet['url'],
            'engagement': {
                'replies': tweet['replies'],
                'retweets': tweet['retweets'],
                'likes': tweet['likes']
            },
            'komoditas': None,
            'harga': None,
            'satuan': None,
            'kualitas': None,
            'lokasi': None,
            'confidence_score': 0
        }
        
        confidence = 0
        
        # 1. Deteksi komoditas
        komoditas_patterns = {
            'beras_premium': ['beras premium', 'premium rice', 'beras super', 'beras kualitas i', 'beras grade a'],
            'beras_medium': ['beras medium', 'beras sedang', 'medium rice', 'beras kualitas ii', 'beras grade b'],
            'beras_rendah': ['beras kualitas rendah', 'beras kualitas iii', 'beras grade c'],
            'beras': ['beras', 'rice', '#beras'],
            'padi': ['padi', 'paddy', '#padi'],
            'gabah': ['gabah', 'gabah kering', 'gkg', 'gabah kering giling', '#gabah']
        }
        
        for jenis, patterns in komoditas_patterns.items():
            if any(p in text_lower for p in patterns):
                extracted['komoditas'] = jenis
                confidence += 25
                break
        
        # 2. Extract harga (multiple patterns untuk akurasi lebih baik)
        harga_patterns = [
            # Pattern: Rp 12.000/kg, Rp12.000/kg
            (r'(?:rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})+)\s*(?:/\s*kg|per\s*kg)', 35),
            # Pattern: harga: Rp 12.000
            (r'harga[:\s]+(?:rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})+)', 30),
            # Pattern: @ Rp 12.000
            (r'@\s*(?:rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})+)', 25),
            # Pattern: Rp 12.000 saja
            (r'(?:rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})+)', 20),
            # Pattern: 12000 atau 12.000 tanpa Rp
            (r'\b(\d{4,7})\b', 15),
        ]
        
        harga_found = []
        best_confidence = 0
        
        for pattern, conf in harga_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                # Clean dan convert
                harga_clean = int(match.replace('.', '').replace(',', ''))
                
                # Filter harga yang masuk akal (1000 - 100000 per kg untuk beras/padi)
                if 1000 <= harga_clean <= 100000:
                    harga_found.append((harga_clean, conf))
                    best_confidence = max(best_confidence, conf)
        
        if harga_found:
            # Ambil harga dengan confidence tertinggi
            # Jika ada multiple dengan confidence sama, ambil yang paling sering muncul
            extracted['harga'] = max(harga_found, key=lambda x: x[1])[0]
            confidence += best_confidence
        
        # 3. Deteksi satuan
        satuan_patterns = {
            'kg': ['kg', 'kilo', 'kilogram', '/kg', 'per kg', 'per kilo'],
            'ton': ['ton', 'tonne', '/ton', 'per ton'],
            'kwintal': ['kwintal', 'kuintal', 'kw', 'kwintal', '/kw']
        }
        
        for satuan, patterns in satuan_patterns.items():
            if any(p in text_lower for p in patterns):
                extracted['satuan'] = satuan
                confidence += 10
                break
        
        if not extracted['satuan']:
            extracted['satuan'] = 'kg'  # Default satuan
        
        # 4. Deteksi kualitas
        kualitas_keywords = {
            'premium': ['premium', 'super', 'kualitas i', 'grade a', 'kelas 1', 'a+', 'terbaik'],
            'medium': ['medium', 'sedang', 'kualitas ii', 'grade b', 'kelas 2', 'menengah'],
            'rendah': ['rendah', 'kualitas iii', 'grade c', 'kelas 3', 'ekonomis']
        }
        
        for kualitas, keywords in kualitas_keywords.items():
            if any(k in text_lower for k in keywords):
                extracted['kualitas'] = kualitas
                confidence += 15
                break
        
        # 5. Deteksi lokasi Jawa Barat
        lokasi_jabar = {
            'bandung': ['bandung', 'kota bandung', 'kab bandung', '#bandung'],
            'bekasi': ['bekasi', '#bekasi'],
            'bogor': ['bogor', '#bogor'],
            'cirebon': ['cirebon', '#cirebon'],
            'depok': ['depok', '#depok'],
            'sukabumi': ['sukabumi', '#sukabumi'],
            'tasikmalaya': ['tasikmalaya', 'tasik', '#tasikmalaya'],
            'banjar': ['banjar', 'kota banjar'],
            'cimahi': ['cimahi', '#cimahi'],
            'indramayu': ['indramayu', '#indramayu'],
            'karawang': ['karawang', '#karawang'],
            'kuningan': ['kuningan', '#kuningan'],
            'majalengka': ['majalengka', '#majalengka'],
            'pangandaran': ['pangandaran', '#pangandaran'],
            'purwakarta': ['purwakarta', '#purwakarta'],
            'subang': ['subang', '#subang'],
            'sumedang': ['sumedang', '#sumedang'],
            'garut': ['garut', '#garut'],
            'ciamis': ['ciamis', '#ciamis'],
            'cianjur': ['cianjur', '#cianjur'],
            'bandung barat': ['bandung barat', 'kbb', '#bandungbarat']
        }
        
        for lok, keywords in lokasi_jabar.items():
            if any(k in text_lower for k in keywords):
                extracted['lokasi'] = lok.title()
                confidence += 15
                break
        
        # Bonus confidence jika mention "jawa barat" atau "jabar"
        if 'jawa barat' in text_lower or 'jabar' in text_lower or '#jabar' in text_lower:
            confidence += 10
        
        # Bonus confidence untuk engagement tinggi (credibility)
        total_engagement = tweet['likes'] + tweet['retweets']
        if total_engagement > 100:
            confidence += 10
        elif total_engagement > 50:
            confidence += 5
        
        extracted['confidence_score'] = min(confidence, 100)  # Max 100
        
        return extracted
    
    def scrape_multiple_queries(self, queries: List[str], tweets_per_query: int = 200):
        """
        Scrape multiple search queries
        """
        print("\n" + "="*60)
        print("🚀 MEMULAI SCRAPING MULTIPLE QUERIES")
        print("="*60)
        
        all_tweets = []
        
        for idx, query in enumerate(queries, 1):
            print(f"\n[{idx}/{len(queries)}] Query: '{query}'")
            
            tweets = self.search_twitter(query, max_tweets=tweets_per_query)
            
            # Extract data dari setiap tweet
            for tweet in tweets:
                extracted = self.extract_data_from_tweet(tweet)
                all_tweets.append(extracted)
            
            print(f"   Total terkumpul: {len(all_tweets)} tweets")
            
            # Delay antar query
            if idx < len(queries):
                delay = random.uniform(5, 10)
                print(f"   ⏳ Menunggu {delay:.1f} detik sebelum query berikutnya...")
                time.sleep(delay)
        
        self.all_tweets = all_tweets
        
        print("\n" + "="*60)
        print(f"✅ SCRAPING SELESAI: {len(all_tweets)} tweets total")
        print("="*60)
        
        return all_tweets
    
    def save_to_json(self, filename: str = "twitter_rice_data.json"):
        """
        Save data ke JSON dengan format rapi
        """
        if not self.all_tweets:
            print("\n⚠️ Tidak ada data untuk disimpan")
            return
        
        # Filter berdasarkan confidence score
        filtered_data = [t for t in self.all_tweets if t['confidence_score'] > 30]
        
        # Sort by confidence score
        filtered_data.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        # Generate statistics
        df = pd.DataFrame(filtered_data)
        
        stats = {
            'total_tweets_scraped': len(self.all_tweets),
            'total_tweets_filtered': len(filtered_data),
            'filter_threshold': 'confidence_score > 30',
            'avg_confidence': float(df['confidence_score'].mean()) if len(df) > 0 else 0,
            'tweets_with_price': len(df[df['harga'].notna()]) if len(df) > 0 else 0,
            'tweets_with_location': len(df[df['lokasi'].notna()]) if len(df) > 0 else 0
        }
        
        if len(df) > 0:
            if 'komoditas' in df.columns:
                stats['by_komoditas'] = df['komoditas'].value_counts().to_dict()
            if 'lokasi' in df.columns:
                stats['by_lokasi'] = df[df['lokasi'].notna()]['lokasi'].value_counts().to_dict()
            if 'harga' in df.columns and df['harga'].notna().any():
                stats['harga_stats'] = {
                    'mean': float(df['harga'].mean()),
                    'median': float(df['harga'].median()),
                    'min': float(df['harga'].min()),
                    'max': float(df['harga'].max()),
                    'std': float(df['harga'].std())
                }
        
        # Output structure
        output = {
            'metadata': {
                'scraping_date': datetime.now().isoformat(),
                'platform': 'Twitter/X',
                'target_area': 'Jawa Barat, Indonesia',
                'scraper_type': 'Selenium WebDriver',
                'data_collection_period': '2024-2025'
            },
            'statistics': stats,
            'data': filtered_data
        }
        
        # Save JSON
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Data berhasil disimpan ke: {filename}")
        print(f"📊 Total tweets: {len(filtered_data)} (filtered from {len(self.all_tweets)})")
        
        # Save Excel backup
        excel_filename = filename.replace('.json', '.xlsx')
        
        # Flatten engagement dict untuk Excel
        df_excel = df.copy()
        if 'engagement' in df_excel.columns:
            df_excel['replies'] = df_excel['engagement'].apply(lambda x: x.get('replies', 0) if isinstance(x, dict) else 0)
            df_excel['retweets'] = df_excel['engagement'].apply(lambda x: x.get('retweets', 0) if isinstance(x, dict) else 0)
            df_excel['likes'] = df_excel['engagement'].apply(lambda x: x.get('likes', 0) if isinstance(x, dict) else 0)
            df_excel = df_excel.drop('engagement', axis=1)
        
        df_excel.to_excel(excel_filename, index=False)
        print(f"📊 Excel backup: {excel_filename}")
        
        # Create summary report
        self.create_summary_report(filtered_data, filename.replace('.json', '_summary.txt'))
        
        return output
    
    def create_summary_report(self, data: List[Dict], filename: str):
        """Create text summary report"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("LAPORAN SCRAPING TWITTER - DATA BERAS/PADI JAWA BARAT\n")
            f.write("="*70 + "\n\n")
            
            f.write(f"Tanggal Scraping  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Tweets      : {len(data)}\n")
            f.write(f"Platform          : Twitter/X\n")
            f.write(f"Target Area       : Jawa Barat\n\n")
            
            df = pd.DataFrame(data)
            
            f.write("-"*70 + "\n")
            f.write("DISTRIBUSI DATA PER KOMODITAS\n")
            f.write("-"*70 + "\n")
            if 'komoditas' in df.columns and df['komoditas'].notna().any():
                for komoditas, count in df['komoditas'].value_counts().items():
                    if komoditas:
                        f.write(f"{komoditas:25s}: {count:4d} tweets\n")
            else:
                f.write("Tidak ada data komoditas terdeteksi\n")
            
            f.write("\n" + "-"*70 + "\n")
            f.write("STATISTIK HARGA (Rp/kg)\n")
            f.write("-"*70 + "\n")
            if 'harga' in df.columns and df['harga'].notna().any():
                f.write(f"Jumlah data harga : {df['harga'].notna().sum()}\n")
                f.write(f"Rata-rata         : Rp {df['harga'].mean():,.0f}\n")
                f.write(f"Median            : Rp {df['harga'].median():,.0f}\n")
                f.write(f"Minimum           : Rp {df['harga'].min():,.0f}\n")
                f.write(f"Maximum           : Rp {df['harga'].max():,.0f}\n")
                f.write(f"Std Deviation     : Rp {df['harga'].std():,.0f}\n")
            else:
                f.write("Tidak ada data harga terdeteksi\n")
            
            f.write("\n" + "-"*70 + "\n")
            f.write("COVERAGE LOKASI (Top 10)\n")
            f.write("-"*70 + "\n")
            if 'lokasi' in df.columns and df['lokasi'].notna().any():
                for lokasi, count in df['lokasi'].value_counts().head(10).items():
                    if lokasi:
                        f.write(f"{lokasi:25s}: {count:4d} tweets\n")
            else:
                f.write("Tidak ada data lokasi terdeteksi\n")
            
            f.write("\n" + "-"*70 + "\n")
            f.write("KUALITAS DATA\n")
            f.write("-"*70 + "\n")
            f.write(f"Avg Confidence Score: {df['confidence_score'].mean():.1f}/100\n")
            f.write(f"Data dengan harga   : {df['harga'].notna().sum()} ({df['harga'].notna().sum()/len(df)*100:.1f}%)\n")
            f.write(f"Data dengan lokasi  : {df['lokasi'].notna().sum()} ({df['lokasi'].notna().sum()/len(df)*100:.1f}%)\n")
            
            f.write("\n" + "="*70 + "\n")
        
        print(f"📝 Summary report: {filename}")
    
    def close(self):
        """Close browser"""
        if self.driver:
            self.driver.quit()
            print("\n✅ Browser ditutup")


def main():
    """Main function"""
    print("="*70)
    print("🐦 TWITTER SELENIUM SCRAPER - RICE DATA JAWA BARAT")
    print("   Target: 1000 tweets | Output: JSON Format")
    print("="*70)
    
    # Configuration
    print("\n⚙️ KONFIGURASI")
    print("-"*70)
    
    headless_input = input("Run headless (tanpa tampil browser)? (y/n) [n]: ").strip().lower()
    headless = headless_input == 'y'
    
    print("\n🔐 TWITTER LOGIN")
    print("-"*70)
    print("⚠️ Gunakan akun Twitter yang valid")
    print("💡 Tip: Gunakan akun dummy/testing untuk keamanan\n")
    
    twitter_username = input("Twitter Username/Email: ").strip()
    twitter_password = input("Twitter Password: ").strip()
    
    if not twitter_username or not twitter_password:
        print("\n❌ Username dan password harus diisi!")
        return
    
    # Initialize scraper
    scraper = TwitterSeleniumScraper(headless=headless)
    
    # Login
    login_success = scraper.login_twitter(twitter_username, twitter_password)
    
    if not login_success:
        print("\n❌ Login gagal! Program dihentikan.")
        scraper.close()
        return
    
    # Define search queries
    queries = [
        # Akun pemerintah dan institusi
        "from:BulogJabar harga beras",
        "from:pertanianjabar padi OR beras",
        "from:InfoJabar harga pangan",
        
        # Variasi umum dengan engagement tinggi
        "(harga beras OR harga padi) jawa barat min_faves:10",
        "(gabah OR GKP) karawang min_retweets:5",
        "beras premium (bandung OR bekasi) min_faves:5",
        "panen padi (subang OR indramayu OR karawang)",
        
        # Hashtag combinations
        "#HargaBeras #JawaBarat",
        "#Gabah #Petani jawa barat",
        "#PanenPadi subang OR indramayu"
    ]
    
    print("\n📋 SEARCH QUERIES:")
    for i, q in enumerate(queries, 1):
        print(f"   {i}. {q}")
    
    # Start scraping
    input("\n⏸️ Tekan Enter untuk mulai scraping...")
    
    tweets_per_query = 100  # 100 tweets per query = 1000 total
    all_tweets = scraper.scrape_multiple_queries(queries, tweets_per_query)
    
    # Save results
    scraper.save_to_json()
    
    # Close browser
    scraper.close()
    
    # Final summary
    print("\n" + "="*70)
    print("🎉 SCRAPING SELESAI!")
    print("="*70)
    print(f"Total tweets scraped: {len(all_tweets)}")
    print(f"File output:")
    print("  - twitter_rice_data.json (data utama)")
    print("  - twitter_rice_data.xlsx (backup Excel)")
    print("  - twitter_rice_data_summary.txt (laporan)")
    print("="*70)
    
    return scraper


if __name__ == "__main__":
    main()