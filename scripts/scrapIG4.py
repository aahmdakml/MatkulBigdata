"""
GOVERNMENT RICE PRICE SCRAPER
Fokus: Data resmi pemerintah tentang harga beras/padi di Jawa Barat
Sumber: Badan Pangan Nasional, PIHPS BI, BPS, Dashboard Jabar
Parameter: Harga, Kualitas, Lokasi (6-12 bulan terakhir)
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta
import logging
import time
from playwright.sync_api import sync_playwright
# import stadata as sta
import argparse
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GovernmentRicePriceScraper:
    def __init__(self):
        self.results = []
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    # ==========================================
    # 1. BADAN PANGAN NASIONAL - PANEL HARGA
    # ==========================================
    def scrape_panel_harga_bapanas(self):
        """
        Scrape Panel Harga dari Badan Pangan Nasional
        Data harga beras per provinsi (termasuk Jawa Barat)
        """
        logger.info("\n" + "="*80)
        logger.info("🏛️ SCRAPING: Badan Pangan Nasional - Panel Harga (via Playwright)")
        logger.info("="*80)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(user_agent=self.headers['User-Agent'])
                page = ctx.new_page()

                # Tabel dinamis berisi provinsi & komoditas per-periode
                page.goto("https://panelharga.badanpangan.go.id/tabel-dinamis", timeout=60_000)
                page.wait_for_selector("table", timeout=60_000)

                # Ambil semua baris pada tabel pertama yang terlihat
                rows = page.locator("table tbody tr")
                n = rows.count()
                for i in range(n):
                    cells = rows.nth(i).locator("td").all_inner_texts()
                    if len(cells) < 5:
                        continue
                    komoditas = cells[0].strip()
                    provinsi  = cells[-2].strip()  # perhatikan indeks sesuai struktur aktual
                    harga     = cells[1].strip()
                    tanggal   = datetime.now().strftime("%Y-%m-%d")

                    if not any(k in komoditas.lower() for k in ["beras", "gabah", "padi"]):
                        continue
                    if "jawa barat" not in provinsi.lower():
                        continue

                    kualitas = "Premium" if "premium" in komoditas.lower() else ("Medium" if "medium" in komoditas.lower() else "")
                    self.results.append({
                        'source': 'Badan Pangan Nasional',
                        'url': 'https://panelharga.badanpangan.go.id/tabel-dinamis',
                        'komoditas': komoditas,
                        'kualitas': kualitas,
                        'harga': harga,
                        'satuan': 'per kg',
                        'lokasi': provinsi,
                        'tanggal': tanggal,
                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })

                browser.close()
            logger.info("✓ Selesai scraping Panel Harga Bapanas")
        except Exception as e:
            logger.error(f"✗ Error scraping Panel Harga: {e}")
    
    # ==========================================
    # 2. PIHPS BANK INDONESIA
    # ==========================================
    def scrape_pihps_bi(self):
        logger.info("\n" + "="*80)
        logger.info("🏦 SCRAPING: PIHPS Bank Indonesia (XHR partial HTML)")
        logger.info("="*80)
        try:
            url = "https://www.bi.go.id/hargapangan/TabelHarga/GetGridHarga"
            headers = self.headers | {
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://www.bi.go.id",
                "Referer": "https://www.bi.go.id/hargapangan"
            }
            jabar_cities = {...}  # sama seperti punyamu
            komoditas_list = [{'id':'1','name':'Beras Premium'}, {'id':'2','name':'Beras Medium'}, {'id':'3','name':'Beras SPHP'}]

            for komoditas in komoditas_list:
                payload = f"ID_Komoditas={komoditas['id']}&ID_Provinsi=32&Periode=30"
                r = requests.post(url, data=payload, headers=headers, timeout=30)
                if r.status_code != 200:
                    logger.warning(f"  ⚠ {komoditas['name']}: HTTP {r.status_code}")
                    continue

                # Banyak implementasi mengembalikan HTML table/rows
                soup = BeautifulSoup(r.text, "html.parser")
                rows = soup.select("tr")
                count = 0
                for row in rows:
                    cols = [c.get_text(strip=True) for c in row.select("td")]
                    if len(cols) < 3:
                        continue
                    kota = cols[0].upper()
                    if not any(city in kota for city in jabar_cities):
                        continue
                    harga = cols[1]
                    tanggal = cols[2]
                    self.results.append({
                        'source': 'PIHPS Bank Indonesia',
                        'url': 'https://www.bi.go.id/hargapangan',
                        'komoditas': komoditas['name'],
                        'kualitas': komoditas['name'].replace('Beras ', ''),
                        'harga': harga if harga.startswith("Rp") else f"Rp {harga}",
                        'satuan': 'per kg',
                        'lokasi': kota.title(),
                        'tanggal': tanggal,
                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    count += 1
                logger.info(f"  ✓ {komoditas['name']}: {count} data")
            logger.info("✓ Selesai scraping PIHPS BI")
        except Exception as e:
            logger.error(f"✗ Error scraping PIHPS: {e}")
    
    # ==========================================
    # 3. BPS - HARGA PRODUSEN (PETANI)
    # ==========================================
    def scrape_bps_producer_price(self):
        """
        Scrape BPS - Harga produsen (petani) untuk gabah/padi
        """
        logger.info("\n" + "="*80)
        logger.info("📊 SCRAPING: BPS - Harga Produsen Gabah/Padi")
        logger.info("="*80)
        
        try:
            # BPS API untuk harga produsen
            url = "https://webapi.bps.go.id/v1/api/list/model/data/lang/ind/domain/0000/var/5504/key/aef50c3fa4b3aca659066f2f6d4c4d00"
            
            response = requests.get(url, headers=self.headers, timeout=20)
            
            if response.status_code == 200:
                try:
                    data_json = response.json()
                    
                    if 'data' in data_json:
                        count = 0
                        for item in data_json['data'][1]:  # Skip header
                            try:
                                # Parse data BPS
                                provinsi = item.get('label', '')
                                
                                # Filter Jawa Barat
                                if 'jawa barat' not in provinsi.lower():
                                    continue
                                
                                # Ambil data terbaru (12 bulan terakhir)
                                values = item.get('data', [])
                                
                                if values:
                                    # Ambil beberapa bulan terakhir
                                    for i, value in enumerate(values[-12:]):  # 12 bulan terakhir
                                        if value and value != '-':
                                            bulan_index = len(values) - 12 + i
                                            tanggal = f"2024-{bulan_index+1:02d}"  # Estimasi tanggal
                                            
                                            data = {
                                                'source': 'BPS - Badan Pusat Statistik',
                                                'url': 'https://www.bps.go.id',
                                                'komoditas': 'Gabah Kering Panen (GKP)',
                                                'kualitas': 'Tingkat Produsen',
                                                'harga': f"Rp {value}",
                                                'satuan': 'per kg',
                                                'lokasi': provinsi,
                                                'tanggal': tanggal,
                                                'jenis_harga': 'Harga Produsen (Petani)',
                                                'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                            }
                                            
                                            self.results.append(data)
                                            count += 1
                            
                            except Exception as e:
                                continue
                        
                        logger.info(f"  ✓ BPS: {count} data")
                
                except json.JSONDecodeError:
                    logger.warning("  ⚠ BPS: Invalid JSON")
            
            logger.info(f"✓ Selesai scraping BPS")
        
        except Exception as e:
            logger.error(f"✗ Error scraping BPS: {e}")
    
    # ==========================================
    # 4. DASHBOARD JABAR
    # ==========================================
    def scrape_dashboard_jabar(self):
        """
        Scrape Dashboard Pangan Pemprov Jawa Barat
        """
        logger.info("\n" + "="*80)
        logger.info("🗺️ SCRAPING: Dashboard Jabar - Data Pangan")
        logger.info("="*80)
        
        try:
            # Dashboard Jabar biasanya pakai API internal
            # Kita coba scrape halaman publiknya
            url = "https://opendata.jabarprov.go.id/id/dataset"
            
            response = requests.get(url, headers=self.headers, timeout=20)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Cari dataset tentang harga pangan
                datasets = soup.find_all('div', class_='dataset-item')
                
                count = 0
                for dataset in datasets:
                    try:
                        title_elem = dataset.find('h3')
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        
                        # Filter dataset tentang pangan/beras
                        if not any(word in title.lower() for word in ['pangan', 'beras', 'harga']):
                            continue
                        
                        link_elem = dataset.find('a', href=True)
                        link = link_elem['href'] if link_elem else ""
                        if link and not link.startswith('http'):
                            link = 'https://opendata.jabarprov.go.id' + link
                        
                        desc_elem = dataset.find('p')
                        desc = desc_elem.get_text(strip=True) if desc_elem else ""
                        
                        data = {
                            'source': 'Open Data Jabar',
                            'url': link,
                            'judul_dataset': title,
                            'deskripsi': desc,
                            'lokasi': 'Jawa Barat',
                            'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        
                        self.results.append(data)
                        count += 1
                        logger.info(f"  ✓ Dataset: {title[:50]}...")
                    
                    except Exception as e:
                        continue
                
                logger.info(f"✓ Dashboard Jabar: {count} datasets")
        
        except Exception as e:
            logger.error(f"✗ Error scraping Dashboard Jabar: {e}")

    # ==========================================
    # 5. TWITTER 
    # ==========================================
    def scrape_x_selenium(
        self,
        query='(beras OR "harga pangan") ("Jawa Barat" OR Jabar) lang:id',
        since_days=180,
        limit=300,
        headless=True,
        username=None,      # opsional: akun X untuk login jika perlu
        password=None       # opsional
    ):
        """
        Scrape X/Twitter via Selenium (tanpa API).
        - Akan membuka halaman pencarian, scroll bertahap, lalu ekstrak tweet yang muncul.
        - Bila tanpa login, X sering membatasi visibilitas. Isi username/password untuk login (opsional).
        """
        logger.info("\n" + "="*80)
        logger.info("🐦 SCRAPING: X/Twitter via Selenium")
        logger.info("="*80)

        import re
        import time
        from datetime import datetime, timedelta
        from urllib.parse import quote
        from langdetect import detect, LangDetectException

        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.service import Service as ChromeService
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

        # ------- Build URL pencarian -------
        if "since:" not in query:
            since_str = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")
            query = f'{query} since:{since_str}'

        # mode "Latest"
        q_url = f'https://x.com/search?q={quote(query)}&src=typed_query&f=live'
        logger.info(f"Search URL: {q_url}")

        # ------- Setup Chrome -------
        chrome_opts = webdriver.ChromeOptions()
        if headless:
            chrome_opts.add_argument("--headless=new")
        chrome_opts.add_argument("--disable-gpu")
        chrome_opts.add_argument("--no-sandbox")
        chrome_opts.add_argument("--window-size=1280,2000")
        chrome_opts.add_argument("--disable-dev-shm-usage")
        chrome_opts.add_argument("--lang=id-ID")

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_opts)
        wait = WebDriverWait(driver, 30)

        try:
            # ------- (Opsional) Login -------
            if username and password:
                driver.get("https://x.com/login")
                try:
                    # Masukkan username
                    user_box = wait.until(EC.presence_of_element_located((By.NAME, "text")))
                    user_box.send_keys(username)
                    next_btn = driver.find_element(By.XPATH, "//span[text()='Next']/ancestor::div[@role='button'] | //span[text()='Berikutnya']/ancestor::div[@role='button']")
                    next_btn.click()

                    # Ada beberapa akun diminta 'phone/email' lagi; biarkan selector umum ini menangani jika muncul
                    time.sleep(2)
                    try:
                        alt_box = driver.find_element(By.NAME, "text")
                        if alt_box.is_displayed():
                            # jika diminta ulang, isikan username lagi
                            alt_box.clear()
                            alt_box.send_keys(username)
                            driver.find_element(By.XPATH, "//span[text()='Next']/ancestor::div[@role='button'] | //span[text()='Berikutnya']/ancestor::div[@role='button']").click()
                    except NoSuchElementException:
                        pass

                    # Masukkan password
                    pwd_box = wait.until(EC.presence_of_element_located((By.NAME, "password")))
                    pwd_box.send_keys(password)
                    login_btn = driver.find_element(By.XPATH, "//span[text()='Log in']/ancestor::div[@role='button'] | //span[text()='Masuk']/ancestor::div[@role='button']")
                    login_btn.click()

                    # Tunggu landing
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "nav[role='navigation']")))
                    logger.info("✓ Login X sukses (indikatif).")
                except TimeoutException:
                    logger.warning("⚠ Gagal login (timeout). Lanjut coba tanpa login.")

            # ------- Buka halaman pencarian -------
            driver.get(q_url)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "main")))
            except TimeoutException:
                logger.error("✗ Halaman pencarian tidak termuat.")
                return

            # ------- Scroll & ekstraksi -------
            seen_urls = set()
            added = 0
            failures = 0
            last_height = 0

            def extract_from_article(article):
                # Ambil teks
                texts = []
                for e in article.find_elements(By.CSS_SELECTOR, "div[data-testid='tweetText'] span"):
                    t = e.text.strip()
                    if t:
                        texts.append(t)
                full_text = " ".join(texts).strip()

                # Username & url
                # Username biasanya ada di blok data-testid="User-Name"
                try:
                    uname_link = article.find_element(By.CSS_SELECTOR, "div[data-testid='User-Name'] a[href*='/']")
                    profile_href = uname_link.get_attribute("href") or ""
                    username = profile_href.rstrip("/").split("/")[-1]
                except Exception:
                    username = ""

                # Permalink & tanggal
                try:
                    time_link = article.find_element(By.CSS_SELECTOR, "a time")
                    dt_iso = time_link.get_attribute("datetime")  # ISO timestamp
                    tanggal = dt_iso[:10] if dt_iso else None
                    # parent anchor = permalink
                    parent_a = time_link.find_element(By.XPATH, "./ancestor::a[1]")
                    url = parent_a.get_attribute("href") or ""
                except Exception:
                    tanggal, url = None, ""

                # Filter bahasa Indonesia (opsional)
                is_id = True
                if full_text:
                    try:
                        is_id = (detect(full_text) == "id")
                    except LangDetectException:
                        is_id = True  # jika gagal deteksi, jangan dibuang

                # Ekstrak angka harga (heuristik)
                harga_hits = re.findall(r"Rp\s?[\d\.\,]+", full_text)
                harga_str = ", ".join(harga_hits) if harga_hits else ""

                return {
                    "text": full_text,
                    "username": username,
                    "url": url,
                    "tanggal": tanggal,
                    "harga": harga_str,
                    "is_id": is_id
                }

            # Loop scroll: kumpulkan sampai limit atau buntu
            while added < limit and failures < 10:
                time.sleep(1.5)

                # Ambil semua artikel (tweet) saat ini
                articles = driver.find_elements(By.CSS_SELECTOR, "article[role='article']")
                if not articles:
                    failures += 1
                    driver.execute_script("window.scrollBy(0, 1200);")
                    continue

                for art in articles:
                    try:
                        data = extract_from_article(art)
                    except StaleElementReferenceException:
                        continue

                    if not data["url"]:
                        continue
                    if data["url"] in seen_urls:
                        continue
                    if not data["text"]:
                        continue
                    if not data["is_id"]:
                        continue  # jaga hasil tetap Indonesia

                    # Simpan
                    self.results.append({
                        "source": "X (Selenium)",
                        "url": data["url"],
                        "komoditas": "Opini Publik (Teks)",
                        "kualitas": "",
                        "harga": data["harga"],
                        "satuan": "",
                        "lokasi": "",  # bisa ditingkatkan (heuristik dari teks/bio)
                        "tanggal": data["tanggal"],
                        "preview": data["text"][:300],
                        "scraped_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "author": f"@{data['username']}" if data["username"] else ""
                    })
                    seen_urls.add(data["url"])
                    added += 1
                    if added >= limit:
                        break

                # Scroll ke bawah untuk muat tweet baru
                driver.execute_script("window.scrollBy(0, 2000);")
                time.sleep(1.2)

                # Deteksi buntu (tak ada pertambahan tinggi halaman)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    failures += 1
                else:
                    failures = 0
                last_height = new_height

            logger.info(f"✓ X/Twitter (Selenium): {added} tweet ditambahkan")

        except Exception as e:
            logger.error(f"✗ Error scraping X/Twitter (Selenium): {e}")
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    # ==========================================
    # 6. WEBSITE BERITA GOV (BACKUP DATA)
    # ==========================================
    def scrape_news_kontan(self):
        """
        Scrape berita Kontan tentang harga pangan Jabar
        Sebagai backup data dengan context lebih lengkap
        """
        logger.info("\n" + "="*80)
        logger.info("📰 SCRAPING: Kontan.co.id - Berita Harga Pangan Jabar")
        logger.info("="*80)
        
        try:
            # Kontan sering publish data harian dari Bapanas
            search_queries = [
                'harga+pangan+jawa+barat',
                'harga+beras+jawa+barat',
            ]
            
            for query in search_queries:
                url = f"https://pusatdata.kontan.co.id/search?q={query}"
                
                response = requests.get(url, headers=self.headers, timeout=20)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    articles = soup.find_all('article', class_='list-berita')[:10]
                    
                    count = 0
                    for article in articles:
                        try:
                            title_elem = article.find('h1') or article.find('h2')
                            if not title_elem:
                                continue
                            
                            title = title_elem.get_text(strip=True)
                            
                            # Filter hanya 6 bulan terakhir
                            date_elem = article.find('span', class_='font-gray')
                            date_text = date_elem.get_text(strip=True) if date_elem else ""
                            
                            link_elem = article.find('a', href=True)
                            link = link_elem['href'] if link_elem else ""
                            
                            # Extract preview content
                            content_elem = article.find('p')
                            content = content_elem.get_text(strip=True) if content_elem else ""
                            
                            # Extract harga dari title atau content
                            full_text = f"{title} {content}"
                            prices = re.findall(r'Rp\s*[\d.,]+', full_text)
                            
                            # Extract komoditas
                            commodities = []
                            for word in ['beras premium', 'beras medium', 'beras sphp', 'gabah', 'padi']:
                                if word in full_text.lower():
                                    commodities.append(word.title())
                            
                            data = {
                                'source': 'Kontan.co.id (Media/Berita)',
                                'url': link,
                                'judul': title,
                                'tanggal_publikasi': date_text,
                                'preview': content[:300],
                                'harga_ditemukan': ', '.join(set(prices)),
                                'komoditas': ', '.join(set(commodities)),
                                'lokasi': 'Jawa Barat',
                                'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            
                            self.results.append(data)
                            count += 1
                            logger.info(f"  ✓ {title[:50]}...")
                        
                        except Exception as e:
                            continue
                    
                    logger.info(f"✓ Query '{query}': {count} articles")
                
                time.sleep(2)
        
        except Exception as e:
            logger.error(f"✗ Error scraping Kontan: {e}")
    
    # ==========================================
    # SAVE & EXPORT FUNCTIONS
    # ==========================================
    def save_to_json(self, filename='government_rice_data_jabar.json'):
        """Simpan ke JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        logger.info(f"\n✓ Data disimpan ke {filename}")
    
    def save_to_text(self, filename='government_rice_data_jabar.txt'):
        """Simpan ke Text dengan format lengkap"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write("DATA HARGA BERAS/PADI/GABAH JAWA BARAT\n")
            f.write("Sumber: Data Resmi Pemerintah\n")
            f.write(f"Total Records: {len(self.results)}\n")
            f.write(f"Tanggal Scraping: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 100 + "\n\n")
            
            # Group by source
            by_source = {}
            for item in self.results:
                source = item.get('source', 'Unknown')
                if source not in by_source:
                    by_source[source] = []
                by_source[source].append(item)
            
            for source, items in by_source.items():
                f.write(f"\n{'='*100}\n")
                f.write(f"SUMBER: {source}\n")
                f.write(f"Total: {len(items)} records\n")
                f.write(f"{'='*100}\n\n")
                
                for idx, item in enumerate(items, 1):
                    f.write(f"\n{'-'*100}\n")
                    f.write(f"RECORD #{idx}\n")
                    f.write(f"{'-'*100}\n")
                    
                    # Print all fields
                    for key, value in item.items():
                        if key not in ['source', 'scraped_date']:
                            f.write(f"{key.upper():20s}: {value}\n")
                    
                    f.write(f"\nScraped: {item.get('scraped_date', 'N/A')}\n")
        
        logger.info(f"✓ Data disimpan ke {filename}")
    
    def save_to_csv(self, filename='government_rice_data_jabar.csv'):
        """Simpan ke CSV untuk analisis"""
        import csv
        
        if not self.results:
            logger.warning("Tidak ada data untuk disimpan")
            return
        
        # Get all unique keys
        all_keys = set()
        for item in self.results:
            all_keys.update(item.keys())
        
        fieldnames = sorted(list(all_keys))
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for item in self.results:
                writer.writerow(item)
        
        logger.info(f"✓ Data disimpan ke {filename}")
    
    def generate_summary(self):
        if not self.results:
            return {
                'total_records': 0,
                'by_source': {},
                'by_commodity': {},
                'by_quality': {},
                'by_location': {},
                'unique_locations': [],
                'date_range': {'earliest': None, 'latest': None}
            }

        summary = {
            'total_records': len(self.results),
            'by_source': {},
            'by_commodity': {},
            'by_quality': {},
            'by_location': {},
            'unique_locations': set(),
            'date_range': {'earliest': None, 'latest': None}
        }

        parsed_dates = []
        for item in self.results:
            summary['by_source'][item.get('source','Unknown')] = summary['by_source'].get(item.get('source','Unknown'),0)+1
            commodity = item.get('komoditas') or item.get('judul_dataset')
            if commodity:
                summary['by_commodity'][commodity] = summary['by_commodity'].get(commodity,0)+1
            q = item.get('kualitas')
            if q:
                summary['by_quality'][q] = summary['by_quality'].get(q,0)+1
            loc = item.get('lokasi')
            if loc:
                summary['by_location'][loc] = summary['by_location'].get(loc,0)+1
                summary['unique_locations'].add(loc)

            # robust date parsing
            raw_date = item.get('tanggal') or item.get('tanggal_publikasi')
            if raw_date:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m", "%d-%m-%Y", "%d %b %Y"):
                    try:
                        parsed_dates.append(datetime.strptime(raw_date, fmt))
                        break
                    except:
                        pass

        if parsed_dates:
            parsed_dates.sort()
            summary['date_range']['earliest'] = parsed_dates[0].strftime("%Y-%m-%d")
            summary['date_range']['latest']   = parsed_dates[-1].strftime("%Y-%m-%d")

        summary['unique_locations'] = sorted(summary['unique_locations'])
        return summary


# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("\n" + "=" * 100)
    print("GOVERNMENT RICE PRICE SCRAPER - JAWA BARAT")
    print("Data Resmi: Beras, Padi, Gabah | Parameter: Harga, Kualitas, Lokasi")
    print("=" * 100 + "\n")
    
    # ---------- CLI ----------
    parser = argparse.ArgumentParser(description="Scraper Harga Beras Pemerintah + X/Twitter")
    parser.add_argument("--x-selenium", action="store_true", help="Scrape X/Twitter via Selenium")
    parser.add_argument("--x-query", type=str,
        default='(beras OR "harga pangan") ("Jawa Barat" OR Jabar) lang:id',
        help="Query X/Twitter")
    parser.add_argument("--x-since-days", type=int, default=180, help="Jika query belum punya since:, ambil N hari ke belakang")
    parser.add_argument("--x-limit", type=int, default=200, help="Batas jumlah tweet")
    parser.add_argument("--x-no-headless", action="store_true", help="Tampilkan browser (non-headless)")
    parser.add_argument("--x-user", type=str, default=None, help="Username X (opsional)")
    parser.add_argument("--x-pass", type=str, default=None, help="Password X (opsional)")

    args = parser.parse_args()

    scraper = GovernmentRicePriceScraper()
    
    print("🚀 Mulai scraping dari sumber resmi pemerintah...\n")
    
    # 1. Badan Pangan Nasional
    scraper.scrape_panel_harga_bapanas()
    time.sleep(3)
    
    # 2. PIHPS Bank Indonesia
    scraper.scrape_pihps_bi()
    time.sleep(3)
    
    # 3. BPS - Harga Produsen
    scraper.scrape_bps_producer_price()
    time.sleep(3)
    
    # 4. Dashboard Jabar
    scraper.scrape_dashboard_jabar()
    time.sleep(3)
    
    # 5. Berita Kontan (backup)
    scraper.scrape_news_kontan()

    if args.x_selenium:
        self_headless = not args.x_no_headless
        scraper.scrape_x_selenium(
            query=args.x_query,
            since_days=args.x_since_days,
            limit=args.x_limit,
            headless=self_headless,
            username=args.x_user,
            password=args.x_pass
        )

    
    # ==========================================
    # SAVE RESULTS
    # ==========================================
    print("\n" + "="*100)
    print("💾 MENYIMPAN HASIL...")
    print("="*100)
    
    scraper.save_to_json('government_rice_data_jabar.json')
    scraper.save_to_text('government_rice_data_jabar.txt')
    scraper.save_to_csv('government_rice_data_jabar.csv')
    
    # ==========================================
    # SUMMARY
    # ==========================================
    summary = scraper.generate_summary()
    
    print("\n" + "="*100)
    print("📊 RINGKASAN HASIL SCRAPING")
    print("="*100)
    print(f"Total Records           : {summary.get('total_records', 0)}")

    by_source = summary.get('by_source', {})
    if by_source:
        print(f"\n📁 Breakdown per Sumber:")
        for source, count in by_source.items():
            print(f"  • {source:50s}: {count:3d} records")

    by_commodity = summary.get('by_commodity', {})
    if by_commodity:
        print(f"\n📦 Komoditas:")
        for commodity, count in list(by_commodity.items())[:10]:
            print(f"  • {commodity:40s}: {count:3d} records")

    by_quality = summary.get('by_quality', {})
    if by_quality:
        print(f"\n⭐ Kualitas/Jenis:")
        for quality, count in by_quality.items():
            print(f"  • {quality:40s}: {count:3d} records")

    uniq_locs = summary.get('unique_locations', [])
    print(f"\n📍 Lokasi Ditemukan ({len(uniq_locs)}):")
    for loc in uniq_locs[:15]:
        print(f"  • {loc}")

    dr = summary.get('date_range', {})
    if dr.get('earliest') or dr.get('latest'):
        print(f"\n📅 Rentang Tanggal:")
        print(f"  Terlama : {dr.get('earliest')}")
        print(f"  Terbaru : {dr.get('latest')}")

    
    print("\n" + "="*100)
    print("✅ SELESAI!")
    print("="*100)
    print("\nFile output:")
    print("  - government_rice_data_jabar.json (format JSON)")
    print("  - government_rice_data_jabar.txt (format TXT)")
    print("  - government_rice_data_jabar.csv (format CSV)")
    print("\n" + "="*100 + "\n")