"""
Simple Social Media Scraper - Metode Backup
Menggunakan pendekatan yang lebih sederhana tanpa browser automation

Dependencies:
pip install instagrapi snscrape pandas requests beautifulsoup4
"""

import json
import pandas as pd
from datetime import datetime, timedelta
import time
import re
from typing import List, Dict
import random

class SimpleSocialScraper:
    def __init__(self):
        self.all_data = []
        
    def scrape_with_instagrapi(self, username: str, password: str):
        """
        Scrape Instagram menggunakan Instagrapi (API wrapper yang lebih stable)
        """
        print("\n📱 Scraping Instagram dengan Instagrapi...")
        
        try:
            from instagrapi import Client
            
            cl = Client()
            cl.login(username, password)
            
            print("✅ Login berhasil!")
            
            # 1. Scrape profil target
            targets = [
                'disperdagin_kabbdg',
                # Tambahkan profil lain jika perlu
            ]
            
            instagram_data = []
            
            for target in targets:
                try:
                    user_id = cl.user_id_from_username(target)
                    medias = cl.user_medias(user_id, amount=50)
                    
                    print(f"\n🔍 @{target}: Ditemukan {len(medias)} posts")
                    
                    for media in medias:
                        if media.caption_text:
                            extracted = self.extract_data_from_text(
                                media.caption_text,
                                media.taken_at.isoformat(),
                                target,
                                'Instagram'
                            )
                            
                            if extracted['komoditas'] and extracted['harga']:
                                instagram_data.append(extracted)
                                print(f"   ✓ {extracted['komoditas']} - Rp {extracted['harga']:,}")
                        
                        time.sleep(1)
                    
                except Exception as e:
                    print(f"❌ Error @{target}: {e}")
            
            # 2. Scrape hashtags
            hashtags = [
                'hargapanganpokokpenting',
                'hargaberasjabar',
                'hargapadi',
                'gabahpetani'
            ]
            
            for tag in hashtags:
                try:
                    medias = cl.hashtag_medias_recent(tag, amount=30)
                    
                    print(f"\n🔍 #{tag}: Ditemukan {len(medias)} posts")
                    
                    for media in medias:
                        if media.caption_text:
                            extracted = self.extract_data_from_text(
                                media.caption_text,
                                media.taken_at.isoformat(),
                                media.user.username,
                                'Instagram'
                            )
                            
                            if extracted['komoditas'] and extracted['harga']:
                                instagram_data.append(extracted)
                                print(f"   ✓ {extracted['komoditas']} - Rp {extracted['harga']:,}")
                        
                        time.sleep(1)
                    
                except Exception as e:
                    print(f"❌ Error #{tag}: {e}")
            
            print(f"\n✅ Total Instagram data: {len(instagram_data)}")
            return instagram_data
            
        except ImportError:
            print("❌ Instagrapi belum terinstall")
            print("   Run: pip install instagrapi")
            return []
        except Exception as e:
            print(f"❌ Error Instagrapi: {e}")
            return []
    
    def scrape_twitter_snscrape(self, keywords: List[str], max_tweets: int = 200):
        """
        Scrape Twitter menggunakan snscrape (tanpa API key)
        """
        print("\n🐦 Scraping Twitter dengan snscrape...")
        
        try:
            import snscrape.modules.twitter as sntwitter
            
            twitter_data = []
            
            for keyword in keywords:
                print(f"\n🔍 Searching: {keyword}")
                
                query = f"{keyword} since:2024-01-01 lang:id"
                tweets = []
                
                for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
                    if i >= max_tweets:
                        break
                    
                    tweets.append(tweet)
                
                print(f"   Ditemukan {len(tweets)} tweets")
                
                for tweet in tweets:
                    extracted = self.extract_data_from_text(
                        tweet.rawContent,
                        tweet.date.isoformat(),
                        tweet.user.username,
                        'Twitter'
                    )
                    
                    if extracted['komoditas'] and extracted['harga']:
                        twitter_data.append(extracted)
                        print(f"   ✓ @{tweet.user.username}: {extracted['komoditas']} - Rp {extracted['harga']:,}")
                
                time.sleep(2)
            
            print(f"\n✅ Total Twitter data: {len(twitter_data)}")
            return twitter_data
            
        except ImportError:
            print("❌ snscrape belum terinstall")
            print("   Run: pip install snscrape")
            return []
        except Exception as e:
            print(f"❌ Error snscrape: {e}")
            return []
    
    def scrape_google_news(self, query: str = "harga beras jawa barat"):
        """
        Scrape Google News untuk artikel tentang harga beras
        """
        print(f"\n📰 Scraping Google News: {query}...")
        
        try:
            import requests
            from bs4 import BeautifulSoup
            from urllib.parse import quote
            
            news_data = []
            
            # Google News search URL
            url = f"https://news.google.com/search?q={quote(query)}&hl=id&gl=ID&ceid=ID:id"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                articles = soup.find_all('article')[:30]  # Max 30 artikel
                
                print(f"   Ditemukan {len(articles)} artikel")
                
                for article in articles:
                    try:
                        # Extract judul dan snippet
                        title_elem = article.find('h3') or article.find('h4')
                        title = title_elem.get_text(strip=True) if title_elem else ""
                        
                        # Cari text content
                        text = title
                        
                        if text:
                            extracted = self.extract_data_from_text(
                                text,
                                datetime.now().isoformat(),
                                'news_portal',
                                'Google News'
                            )
                            
                            if extracted['komoditas']:
                                news_data.append(extracted)
                    
                    except Exception as e:
                        continue
                
                print(f"✅ Berhasil extract {len(news_data)} artikel dengan data relevan")
            
            return news_data
            
        except Exception as e:
            print(f"❌ Error Google News: {e}")
            return []
    
    def extract_data_from_text(self, text: str, timestamp: str, username: str, platform: str) -> Dict:
        """
        Universal function untuk extract data dari text
        """
        data = {
            'id': f"{platform}_{username}_{int(time.time()*1000)}",
            'tanggal': timestamp,
            'username': username,
            'platform': platform,
            'text_original': text[:500],
            'komoditas': None,
            'harga': None,
            'satuan': None,
            'kualitas': None,
            'lokasi': None,
            'confidence_score': 0  # Scoring seberapa yakin data ini akurat
        }
        
        text_lower = text.lower()
        confidence = 0
        
        # 1. Deteksi komoditas
        komoditas_patterns = {
            'beras_premium': ['beras premium', 'premium rice', 'beras super', 'beras kualitas i'],
            'beras_medium': ['beras medium', 'beras sedang', 'medium rice', 'beras kualitas ii'],
            'beras_rendah': ['beras kualitas rendah', 'beras kualitas iii'],
            'beras': ['beras', 'rice'],
            'padi': ['padi', 'paddy'],
            'gabah': ['gabah', 'gabah kering', 'gkg', 'gabah kering giling']
        }
        
        for jenis, patterns in komoditas_patterns.items():
            if any(p in text_lower for p in patterns):
                data['komoditas'] = jenis
                confidence += 20
                break
        
        # 2. Extract harga dengan berbagai pattern
        harga_patterns = [
            (r'(?:rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})+)(?:\s*(?:/|per)\s*kg)?', 30),  # Rp 12.000/kg
            (r'harga[:\s]+(?:rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})+)', 25),  # harga: 12.000
            (r'@\s*(?:rp\.?\s*)?(\d{1,3}(?:[.,]\d{3})+)', 20),  # @ 12.000
            (r'(?:rp\.?\s*)?(\d{4,7})(?!\d)', 15),  # 12000
        ]
        
        harga_found = []
        best_confidence = 0
        
        for pattern, conf in harga_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                harga_clean = int(match.replace('.', '').replace(',', ''))
                # Filter harga masuk akal
                if 1000 <= harga_clean <= 100000:
                    harga_found.append((harga_clean, conf))
                    best_confidence = max(best_confidence, conf)
        
        if harga_found:
            # Ambil harga dengan confidence tertinggi
            data['harga'] = max(harga_found, key=lambda x: x[1])[0]
            confidence += best_confidence
        
        # 3. Deteksi satuan
        satuan_patterns = {
            'kg': ['kg', 'kilo', 'kilogram', '/kg', 'per kg'],
            'ton': ['ton', 'tonne', '/ton'],
            'kwintal': ['kwintal', 'kuintal', 'kw', '/kw']
        }
        
        for satuan, patterns in satuan_patterns.items():
            if any(p in text_lower for p in patterns):
                data['satuan'] = satuan
                confidence += 10
                break
        
        if not data['satuan']:
            data['satuan'] = 'kg'  # Default
        
        # 4. Deteksi kualitas
        kualitas_keywords = {
            'premium': ['premium', 'super', 'kualitas i', 'grade a', 'kelas 1'],
            'medium': ['medium', 'sedang', 'kualitas ii', 'grade b', 'kelas 2'],
            'rendah': ['rendah', 'kualitas iii', 'grade c', 'kelas 3']
        }
        
        for kualitas, keywords in kualitas_keywords.items():
            if any(k in text_lower for k in keywords):
                data['kualitas'] = kualitas
                confidence += 15
                break
        
        # 5. Deteksi lokasi Jawa Barat
        lokasi_jabar = {
            'bandung': ['bandung', 'kota bandung', 'kab bandung'],
            'bekasi': ['bekasi'],
            'bogor': ['bogor'],
            'cirebon': ['cirebon'],
            'depok': ['depok'],
            'sukabumi': ['sukabumi'],
            'tasikmalaya': ['tasikmalaya', 'tasik'],
            'banjar': ['banjar'],
            'cimahi': ['cimahi'],
            'indramayu': ['indramayu'],
            'karawang': ['karawang'],
            'kuningan': ['kuningan'],
            'majalengka': ['majalengka'],
            'pangandaran': ['pangandaran'],
            'purwakarta': ['purwakarta'],
            'subang': ['subang'],
            'sumedang': ['sumedang'],
            'garut': ['garut'],
            'ciamis': ['ciamis'],
            'cianjur': ['cianjur'],
            'bandung barat': ['bandung barat', 'kbb']
        }
        
        for lok, keywords in lokasi_jabar.items():
            if any(k in text_lower for k in keywords):
                data['lokasi'] = lok.title()
                confidence += 15
                break
        
        # Tambah confidence jika ada keyword "jawa barat" atau "jabar"
        if 'jawa barat' in text_lower or 'jabar' in text_lower:
            confidence += 10
        
        data['confidence_score'] = min(confidence, 100)  # Max 100
        
        return data
    
    def save_to_json(self, filename: str = "rice_data_sosmed.json"):
        """
        Save data ke JSON dengan struktur rapi
        """
        if not self.all_data:
            print("\n⚠️ Tidak ada data untuk disimpan")
            return
        
        # Filter data dengan confidence score > 30
        filtered_data = [d for d in self.all_data if d.get('confidence_score', 0) > 30]
        
        # Sort by confidence score
        filtered_data.sort(key=lambda x: x.get('confidence_score', 0), reverse=True)
        
        # Generate statistics
        df = pd.DataFrame(filtered_data)
        
        stats = {
            'total_entries': len(filtered_data),
            'avg_confidence': float(df['confidence_score'].mean()) if len(df) > 0 else 0,
            'by_platform': df['platform'].value_counts().to_dict() if 'platform' in df.columns else {},
            'by_komoditas': df['komoditas'].value_counts().to_dict() if 'komoditas' in df.columns else {},
            'by_lokasi': df['lokasi'].value_counts().to_dict() if 'lokasi' in df.columns else {},
            'harga_stats': {}
        }
        
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
                'target_area': 'Jawa Barat, Indonesia',
                'time_range': '6-12 bulan terakhir',
                'total_data_collected': len(self.all_data),
                'total_data_filtered': len(filtered_data),
                'filter_criteria': 'confidence_score > 30',
                'platforms_scraped': list(set([d['platform'] for d in self.all_data]))
            },
            'statistics': stats,
            'data': filtered_data
        }
        
        # Save JSON
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Data berhasil disimpan ke: {filename}")
        print(f"📊 Total data: {len(filtered_data)} (filtered from {len(self.all_data)})")
        
        # Save Excel backup
        excel_filename = filename.replace('.json', '.xlsx')
        df.to_excel(excel_filename, index=False)
        print(f"📊 Excel backup: {excel_filename}")
        
        # Create summary report
        self.create_summary_report(filtered_data, filename.replace('.json', '_summary.txt'))
        
        return output
    
    def create_summary_report(self, data: List[Dict], filename: str):
        """Create text summary report"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("LAPORAN SCRAPING DATA BERAS/PADI JAWA BARAT\n")
            f.write("="*60 + "\n\n")
            
            f.write(f"Tanggal Scraping: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Data: {len(data)}\n\n")
            
            df = pd.DataFrame(data)
            
            f.write("-"*60 + "\n")
            f.write("DISTRIBUSI DATA PER PLATFORM\n")
            f.write("-"*60 + "\n")
            for platform, count in df['platform'].value_counts().items():
                f.write(f"{platform:20s}: {count:4d} data\n")
            
            f.write("\n" + "-"*60 + "\n")
            f.write("DISTRIBUSI DATA PER KOMODITAS\n")
            f.write("-"*60 + "\n")
            if 'komoditas' in df.columns:
                for komoditas, count in df['komoditas'].value_counts().items():
                    f.write(f"{komoditas:20s}: {count:4d} data\n")
            
            f.write("\n" + "-"*60 + "\n")
            f.write("STATISTIK HARGA (Rp/kg)\n")
            f.write("-"*60 + "\n")
            if 'harga' in df.columns and df['harga'].notna().any():
                f.write(f"Rata-rata: Rp {df['harga'].mean():,.0f}\n")
                f.write(f"Median   : Rp {df['harga'].median():,.0f}\n")
                f.write(f"Minimum  : Rp {df['harga'].min():,.0f}\n")
                f.write(f"Maximum  : Rp {df['harga'].max():,.0f}\n")
            
            f.write("\n" + "-"*60 + "\n")
            f.write("COVERAGE LOKASI\n")
            f.write("-"*60 + "\n")
            if 'lokasi' in df.columns:
                for lokasi, count in df['lokasi'].value_counts().items():
                    if lokasi:
                        f.write(f"{lokasi:20s}: {count:4d} data\n")
            
            f.write("\n" + "="*60 + "\n")
        
        print(f"📝 Summary report: {filename}")
    
    def run_all(self, ig_username: str = None, ig_password: str = None):
        """
        Run semua scraping method
        """
        print("="*60)
        print("🚀 SIMPLE SOCIAL MEDIA SCRAPER")
        print("   Multi-Platform Data Collection")
        print("="*60)
        
        all_scraped_data = []
        
        # 1. Instagram (jika ada credentials)
        if ig_username and ig_password:
            print("\n" + "="*60)
            print("FASE 1: INSTAGRAM")
            print("="*60)
            
            ig_data = self.scrape_with_instagrapi(ig_username, ig_password)
            all_scraped_data.extend(ig_data)
            
            print(f"\n📊 Progress: {len(all_scraped_data)} data")
        else:
            print("\n⚠️ Instagram credentials tidak tersedia, skip Instagram")
        
        # 2. Twitter
        print("\n" + "="*60)
        print("FASE 2: TWITTER/X")
        print("="*60)
        
        twitter_keywords = [
            'harga beras jawa barat',
            'harga padi jabar',
            'gabah petani bandung',
            'harga beras bandung',
            'harga gabah indramayu',
            'panen padi subang'
        ]
        
        twitter_data = self.scrape_twitter_snscrape(twitter_keywords, max_tweets=100)
        all_scraped_data.extend(twitter_data)
        
        print(f"\n📊 Progress: {len(all_scraped_data)} data")
        
        # 3. Google News
        print("\n" + "="*60)
        print("FASE 3: GOOGLE NEWS")
        print("="*60)
        
        news_queries = [
            'harga beras jawa barat',
            'harga padi jawa barat',
            'gabah petani jawa barat'
        ]
        
        for query in news_queries:
            news_data = self.scrape_google_news(query)
            all_scraped_data.extend(news_data)
            time.sleep(2)
        
        print(f"\n📊 Total data terkumpul: {len(all_scraped_data)}")
        
        # Save all data
        self.all_data = all_scraped_data
        result = self.save_to_json()
        
        # Final summary
        print("\n" + "="*60)
        print("🎉 SCRAPING SELESAI!")
        print("="*60)
        print(f"Total data terkumpul: {len(all_scraped_data)}")
        print(f"Data dengan confidence > 30: {len([d for d in all_scraped_data if d.get('confidence_score', 0) > 30])}")
        print("\nFile output:")
        print("  - rice_data_sosmed.json (data utama)")
        print("  - rice_data_sosmed.xlsx (backup Excel)")
        print("  - rice_data_sosmed_summary.txt (laporan)")
        print("="*60)
        
        return result


def main():
    """Main entry point"""
    scraper = SimpleSocialScraper()
    
    print("\n🔐 Instagram Login (Optional)")
    print("Tekan Enter untuk skip jika tidak ingin scraping Instagram\n")
    
    ig_user = input("Instagram Username: ").strip()
    ig_pass = None
    
    if ig_user:
        ig_pass = input("Instagram Password: ").strip()
    
    # Run scraping
    scraper.run_all(ig_user, ig_pass)


if __name__ == "__main__":
    main()