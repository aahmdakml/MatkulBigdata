Analitik Harga/Kualitas Beras – Jabar (MVP)

Laporan lengkap + README bergaya GitHub untuk seluruh proyek yang sudah kita bangun: arsitektur, cara jalanin, endpoint, troubleshooting, dan best-practice. Cocok buat disimpan di repo sebagai README.md.

Ringkasan Proyek

Aplikasi ini membantu menormalkan data harga/kualitas beras/padi/gabah dari berbagai sumber (CSV/JSON hasil scraping atau media sosial), lalu menampilkan:

Tabel hasil normalisasi (region, harga Rp/kg, kualitas, dll)

Rangkuman ranking: Top 10 daerah termurah per kualitas

Word Cloud + Sentiment Analysis (dihitung oleh Gemini, FE hanya menampilkan SVG & ringkasan)

Export hasil (CSV/JSON, dan SVG untuk word cloud)

Persist snapshot hasil di localStorage agar tidak hilang saat refresh

Seluruh normalisasi dan word cloud + sentiment dilakukan via Google Gemini (Responses API). Frontend fokus ke UI & visualisasi, backend sebagai API gateway + prompt builder + payload limiter.

Teknologi & Framework

Frontend

Vite + React + TypeScript

PapaParse (parsing CSV)

CSS vanilla custom (tanpa framework, tema gelap elegan)

LocalStorage untuk snapshot

Backend

Node.js (ESM, module + moduleResolution: NodeNext)

Express + CORS + body-parser

Google Gemini (Responses API v1beta, via fetch bawaan Node 18+)

Bahasa & Tools

TypeScript (both FE & BE)

Nodemon untuk dev server backend

Fitur Utama

✅ Upload multi-file (.csv/.json)

✅ Chunking & payload limiting ke Gemini (stabil, anti timeouts)

✅ Normalisasi harga → Rp/kg, region → kab/kota Jawa Barat, kualitas → label konsisten

✅ Tabel + sorting (harga/region/kualitas)

✅ Ranking termurah per kualitas

✅ Word Cloud (SVG) + Sentiment by harga atau kualitas

✅ Export JSON/CSV (tabel) + SVG (word cloud)

✅ Snapshot hasil (persist di browser)


Struktur Proyek (Direkomendasikan)
/backend
  /src
    /routes
      ingest-file.ts
      analyze-sentiment.ts
    gemini.ts
    index.ts
  tsconfig.json
  nodemon.json
  .env

/frontend
  /src
    /lib/api.ts
    app.tsx
    main.tsx
    styles.css
  vite.config.ts
  tsconfig.json
  .env.development

Catatan: Karena pakai NodeNext, semua import relatif antar file TS di backend harus diakhiri .js (contoh: import route from "./routes/ingest-file.js"), meskipun file sumbernya .ts

Cara Menjalankan (Dev)
1) Backend

Install deps:

cd backend
npm i


Konfigurasi .env:

PORT=5000
GEMINI_API_KEY=YOUR_KEY_HERE
# Mulai dari model mainstream, helper akan menyesuaikan:
GEMINI_MODEL=gemini-1.5-flash
# (opsional) gunakan: gemini-1.5-flash-8b bila akun Anda mendukung


tsconfig.json backend (inti):

{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "lib": ["ES2022", "DOM"],
    "rootDir": "src",
    "outDir": "dist",
    "strict": true,
    "skipLibCheck": true,
    "esModuleInterop": true
  }
}


nodemon.json:

{
  "watch": ["src"],
  "ext": "ts",
  "ignore": ["../frontend/**", "**/*.json"]
}


Jalankan backend:

npm run dev
# typical: "nodemon --exec ts-node src/index.ts"


Health check:

GET http://localhost:5000/api/health → {ok:true,...}

2) Frontend

Install deps:

cd ../frontend
npm i


.env.development (bypass Vite proxy → paling stabil):

VITE_API_BASE=http://localhost:5000/api


vite.config.ts (opsional jika ingin proxy):

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:5000",
        changeOrigin: true,
        secure: false,
        timeout: 120000,
        proxyTimeout: 120000
      }
    }
  }
});


Jalankan FE:

npm run dev
# buka http://localhost:5173

Alur Pakai Aplikasi

Upload satu/lebih file .csv/.json (hasil scraping/media sosial).

(Opsional) Isi Instruksi tambahan untuk Gemini, mis:

Normalisasi nama daerah ke kab/kota, abaikan baris tanpa harga. Konversi semua harga ke Rp/kg bila memungkinkan.

Klik Bersihkan & Parse → backend melakukan prompt ke Gemini → hasil (array JSON) tampil sebagai tabel.

Lihat Rangkuman: Top 10 daerah termurah per kualitas.

(Opsional) Word Cloud & Sentiment

Pilih mode Berdasarkan Kualitas atau Berdasarkan Harga

Klik Generate Word Cloud → FE kirim data mentah (atau fallback cleaned) ke /api/analyze-sentiment → tampil SVG, summary, metrik sentimen, top_words.

Export:

Data tabel → JSON/CSV

Word cloud → SVG

Snapshot hasil (cleaned/metas/raw/sort) tersimpan di localStorage sehingga tidak hilang saat refresh halaman.

API Backend
POST /api/ingest-file

Body

{
  "rows": [ /* array of raw objects from CSV/JSON */ ],
  "prompt": "opsional string instruksi tambahan"
}


Response (sukses, JSON murni)

{
  "ok": true,
  "data": [
    {
      "source": "Twitter | CNN | Medium | ...",
      "region": "Kota Bandung",
      "harga": 13500,
      "kualitas": "premium",
      "waktu": "2025-10-05",
      "url": "https://...",
      "note": "opsional"
    }
  ],
  "meta": {
    "received": 527,
    "baseline": 527,
    "afterModel": 220,
    "final": 220,
    "tookMs": 8123
  }
}


Response (model tidak mengembalikan JSON murni)

{
  "ok": true,
  "raw": "…teks non-JSON dari model…",
  "meta": {
    "received": 527,
    "baseline": 527,
    "afterModel": 0,
    "final": 0,
    "note": "Model tidak mengembalikan JSON murni.",
    "tookMs": 9500
  }
}


Response (gagal)

{ "ok": false, "error": "Gemini(ResponsesAPI) timeout after 90000ms" }


Server akan memotong rows di sisi BE (mis. 400 item) agar stabil.

POST /api/analyze-sentiment

Body

{
  "rows": [ /* array raw rows (diproyeksi & dibatasi 300-400) */ ],
  "by": "kualitas", // atau "harga"
  "prompt": "opsional instruksi tambahan"
}


Response (sukses)

{
  "ok": true,
  "data": {
    "svg": "<svg ...>...</svg>",
    "sentiments": { "positive": 23, "neutral": 51, "negative": 12, "method": "lexicon+rule-based" },
    "summary": "Ringkasan 1-2 paragraf...",
    "top_words": [
      { "text": "premium", "weight": 38, "sentiment": "positive" },
      { "text": "mahal", "weight": 22, "sentiment": "negative" }
    ]
  }
}


Response (raw)

{ "ok": true, "raw": "…model reply…", "meta": { "note": "Model tidak mengembalikan 'svg' valid" } }


Response (gagal)

{ "ok": false, "error": "Responses API 404: {\"error\":{\"message\":\"Model not found: models/gemini-1.5-flash-8b\"...}}" }

Implementasi Gemini (Stabil)

Selalu gunakan Responses API v1beta/responses:generate dengan responseMimeType: application/json.

Helper askGeminiAsJson():

Mencoba 3 varian otomatis:

model "models/<id>" (kanon)

model "<id>" (plain)

Legacy :generateContent (fallback)

Retry dengan exponential backoff

Hard timeout (default 90s)

ENV:

GEMINI_API_KEY=...
GEMINI_MODEL=gemini-1.5-flash   # aman & cepat
# (opsional) gemini-1.5-flash-8b bila tersedia

Tips Performa & Keandalan

Batasi payload di FE dan BE (400–600 baris per request).

Hapus triple backticks di prompt (hemat token).

Simpan instruksi tetap (fixed prompt) singkat & jelas.

Gunakan model cepat (flash) saat eksplorasi; beralih ke -8b bila butuh kualitas lebih dan akun mendukung.

Hindari Vite proxy saat dev (set VITE_API_BASE=http://localhost:5000/api) untuk menghindari ECONNRESET.

nodemon.json untuk cegah restart tak perlu saat FE berubah/JSON besar.

Troubleshooting

1) 404 dari Gemini

GEMINI_MODEL salah/akun tidak punya akses.

Pastikan format benar: gemini-1.5-flash (helper akan coba models/… & plain).

Lihat pesan error lengkap (helper sekarang mengembalikan detail path yg gagal).

2) Timeout 60–90s

Payload kebesaran → kecilkan CHUNK_SIZE FE & MAX_ROWS BE.

Model lambat → coba gemini-1.5-flash biasa (tanpa -8b).

Koneksi lambat → naikkan timeoutMs ke 120s sementara.

3) Could not establish connection. Receiving end does not exist.

Itu pesan extension browser (bukan fetch kamu). Coba Incognito / disable extensions.

4) 413 PayloadTooLargeError

Tambahkan limit body di backend:

app.use(express.json({ limit: "25mb" }));
app.use(express.urlencoded({ extended: true, limit: "25mb" }));


Kecilkan file/upload atau chunk lebih kecil.

5) TypeScript rewel (FE)

PapaParse types:

import Papa, { type ParseResult } from "papaparse";


verbatimModuleSyntax aktif → import type-only untuk types, dan hindari undefined pada optional (exactOptionalPropertyTypes: true) → omit properti ketimbang set undefined.

6) ESM NodeNext

Seluruh import relatif antar berkas akhiri .js (walau file sumber TS).

Contoh: import analyzeRoute from "./routes/analyze-sentiment.js";

