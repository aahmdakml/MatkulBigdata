"""
scrapIG_resilient.py
- Resilient scraper untuk profil + hashtag dengan Instaloader.
- Fitur: auto-load/save session, throttle ketat, retry + exponential backoff,
  skip aman saat login_required/forbidden, dan output JSON Lines (.json).
"""

import instaloader
import json
import re
import time
import random
from collections import Counter
from tqdm import tqdm

# ===================== KONFIG =====================
USERNAME = "rndmgyinthekos"          # <-- ganti username IG-mu
USE_LOGIN = True                   # set False jika benar2 mau tanpa login
TARGET_PROFILE = "disperdagin_kabbdg"
TARGET_HASHTAG = "hargapanganpokokpenting"

OUTPUT_FILE = "ig_crawl_result.json"  # JSON Lines (1 posting per baris)
MAX_EXPANDED_TAGS = 5                 # jumlah co-occurring tags untuk diperluas
MAX_POSTS_PER_SOURCE = None           # None = tanpa batas; atau angka (mis. 200)

# Throttle & Retry
DELAY_RANGE = (7.0, 14.0)     # delay acak antar post (lebih besar = lebih aman)
MAX_RETRIES = 6               # total percobaan per panggilan IG
BACKOFF_BASE = 2.5            # faktor backoff (detik * (BASE^attempt))
BACKOFF_JITTER = (0.5, 2.0)   # jitter acak untuk backoff

# (Opsional) set user agent yang lebih "browser-like"
CUSTOM_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
# =================================================


def log(msg):
    print(msg, flush=True)


def safe_json_write(item, file):
    with open(file, "a", encoding="utf-8") as f:
        json.dump(item, f, ensure_ascii=False)
        f.write("\n")


def extract_price(caption: str):
    """Cari pola 'Rp' di caption, hasilkan list integer (mis. [13500, 15000])."""
    if not caption:
        return None
    matches = re.findall(r"Rp\.?\s?([0-9\.,]+)", caption)
    prices = []
    for m in matches:
        val = m.replace(".", "").replace(",", "")
        try:
            prices.append(int(val))
        except:
            pass
    return prices or None


def backoff_sleep(attempt):
    # exponential backoff + jitter
    base = (BACKOFF_BASE ** attempt)
    jitter = random.uniform(*BACKOFF_JITTER)
    t = base + jitter
    log(f"[BACKOFF] Tidur {t:.1f}s (attempt {attempt})")
    time.sleep(t)


def robust_iter_posts(get_posts_iter, label, limit=None):
    """
    Jalankan iterasi post dengan retry saat query error (401/403/429).
    get_posts_iter: callable -> iterator (mis. profile.get_posts)
    label: label untuk log
    limit: batasi jumlah posts
    """
    posts = []
    attempt = 0
    while True:
        try:
            count = 0
            for post in tqdm(get_posts_iter(), desc=label):
                posts.append(post)
                count += 1
                if limit and count >= limit:
                    break
            return posts
        except instaloader.exceptions.LoginRequiredException as e:
            log(f"[ERR] {label}: LoginRequired -> {e}")
            return []  # tidak bisa lanjut tanpa login
        except instaloader.exceptions.QueryReturnedForbiddenException as e:
            log(f"[ERR] {label}: 403 Forbidden -> {e}")
        except instaloader.exceptions.QueryReturnedBadRequestException as e:
            log(f"[ERR] {label}: 400 Bad Request -> {e}")
        except instaloader.exceptions.QueryReturnedNotFoundException as e:
            log(f"[ERR] {label}: 404 Not Found -> {e}")
            return []
        except instaloader.exceptions.ConnectionException as e:
            log(f"[ERR] {label}: ConnectionException -> {e}")
        except instaloader.exceptions.QueryReturnedErrorException as e:
            # termasuk 401 Unauthorized / "Please wait a few minutes…" / 429
            log(f"[ERR] {label}: QueryReturnedError -> {e}")
        except Exception as e:
            log(f"[ERR] {label}: Unknown -> {e}")

        attempt += 1
        if attempt > MAX_RETRIES:
            log(f"[FAIL] {label}: Max retries tercapai. Skip.")
            return []
        backoff_sleep(attempt)


def post_to_dict(post, source_label, owner_override=None):
    return {
        "source": source_label,
        "owner": owner_override or post.owner_username,
        "shortcode": post.shortcode,
        "caption": post.caption or "",
        "hashtags": post.caption_hashtags or [],
        "mentions": post.caption_mentions or [],
        "prices": extract_price(post.caption or ""),
        "date": post.date_utc.isoformat() if post.date_utc else None,
        "url": post.url,
    }


def collect_profile(L, username):
    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except Exception as e:
        log(f"[ERR] Gagal akses profil {username}: {e}")
        return 0

    posts = robust_iter_posts(
        lambda: profile.get_posts(),
        label=f"profile:{username}",
        limit=MAX_POSTS_PER_SOURCE
    )

    n = 0
    for p in posts:
        d = post_to_dict(p, "profile", owner_override=username)
        safe_json_write(d, OUTPUT_FILE)
        n += 1
        time.sleep(random.uniform(*DELAY_RANGE))
    log(f"[INFO] Tersimpan dari profil {username}: {n}")
    return n


def collect_hashtag(L, tagname, source_tag):
    try:
        tag = instaloader.Hashtag.from_name(L.context, tagname)
    except instaloader.exceptions.LoginRequiredException as e:
        log(f"[ERR] Hashtag #{tagname}: butuh login -> {e}")
        return 0
    except Exception as e:
        log(f"[ERR] Gagal akses hashtag #{tagname}: {e}")
        return 0

    posts = robust_iter_posts(
        lambda: tag.get_posts(),
        label=f"hashtag:{tagname}",
        limit=MAX_POSTS_PER_SOURCE
    )

    n = 0
    for p in posts:
        d = post_to_dict(p, f"hashtag_{source_tag}")
        safe_json_write(d, OUTPUT_FILE)
        n += 1
        time.sleep(random.uniform(*DELAY_RANGE))
    log(f"[INFO] Tersimpan dari hashtag #{tagname}: {n}")
    return n


def discover_related_tags():
    ctr = Counter()
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            for line in f:
                j = json.loads(line)
                for t in (j.get("hashtags") or []):
                    if t:
                        ctr.update([t.lower()])
    except FileNotFoundError:
        pass
    common = [t for t, _ in ctr.most_common(MAX_EXPANDED_TAGS)]
    # buang duplikat target utama
    common = [t for t in common if t != TARGET_HASHTAG]
    log(f"[INFO] Related tags (top {MAX_EXPANDED_TAGS}): {common}")
    return common


def main():
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        save_metadata=False,
        compress_json=False,
        max_connection_attempts=1,  # biar kita yang handle retry/backoff
        request_timeout=30.0,
        quiet=False
    )

    # (opsional) Set UA mirip browser
    L.context.user_agent = CUSTOM_UA

    # ---- Session handling ----
    if USE_LOGIN:
        try:
            # coba load session kalau sudah ada
            L.load_session_from_file(USERNAME)
            log("[INFO] Session file ditemukan & dimuat.")
        except Exception:
            log("[INFO] Session belum ada. Login interaktif…")
            try:
                L.interactive_login(USERNAME)    # prompt password
                L.save_session_to_file()         # simpan session
                log("[INFO] Session disimpan.")
            except Exception as e:
                log(f"[WARN] Login gagal: {e}. Lanjut tanpa login.")
    else:
        log("[INFO] Mode tanpa login (bisa kurang stabil untuk hashtag).")

    total = 0
    total += collect_profile(L, TARGET_PROFILE)
    total += collect_hashtag(L, TARGET_HASHTAG, "main")

    # expand dari co-occurring tags yang sudah terkumpul
    for tag in discover_related_tags():
        total += collect_hashtag(L, tag, "expanded")

    log(f"[DONE] Total post disimpan: {total}")
    log(f"[SAVED] File: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
