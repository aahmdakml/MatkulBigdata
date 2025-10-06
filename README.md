# Analitik Harga/Kualitas Beras – Jabar (MVP)

Aplikasi untuk **menormalkan** data harga/kualitas beras/padi/gabah dari berbagai sumber (CSV/JSON hasil scraping atau media sosial), lalu menampilkan:

- **Tabel hasil normalisasi** (region, harga Rp/kg, kualitas, dll)
- **Ranking**: Top 10 daerah termurah per kualitas
- **Word Cloud (SVG) + Sentiment Analysis** — dihitung oleh **Google Gemini**
- **Export** hasil (CSV/JSON & SVG), **persist** snapshot di browser

> Normalisasi & analitik dilakukan via **Gemini Responses API**. Frontend fokus UI, backend menjadi API gateway + prompt builder + payload limiter.

---

## 🧱 Teknologi

**Frontend**
- Vite + React + TypeScript
- PapaParse (parsing CSV)
- CSS murni (tema gelap)

**Backend**
- Node.js (ESM: `module`/`moduleResolution` = `NodeNext`)
- Express + CORS + body parser
- Google Gemini Responses API (v1beta, `fetch` bawaan Node ≥ 18)

---

## 📁 Struktur Proyek (disarankan)

```
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
```

> Karena **NodeNext**, seluruh import relatif antar berkas **akhiri `.js`** saat impor (meski berkas sumber `.ts`).  
> Contoh: `import ingestRoute from "./routes/ingest-file.js"`.

---

## ⚙️ Setup & Menjalankan

### 1) Backend

Install:
```bash
cd backend
npm i
```

`.env`:
```env
PORT=5000
GEMINI_API_KEY=YOUR_KEY_HERE
# mulai dari model yang paling aman & cepat:
GEMINI_MODEL=gemini-1.5-flash
# (opsional) gunakan gemini-1.5-flash-8b bila akun Anda mendukung
```

`tsconfig.json` (inti):
```json
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
```

`nodemon.json` (hindari restart karena perubahan FE/berkas besar):
```json
{
  "watch": ["src"],
  "ext": "ts",
  "ignore": ["../frontend/**", "**/*.json"]
}
```

Jalankan:
```bash
npm run dev
# biasanya: nodemon --config nodemon.json --exec ts-node src/index.ts
```

Health check:
```
GET http://localhost:5000/api/health   ->  { "ok": true, "ts": 1730... }
```

### 2) Frontend

Install:
```bash
cd ../frontend
npm i
```

`.env.development` (hindari Vite proxy → paling stabil):
```env
VITE_API_BASE=http://localhost:5000/api
```

Jalankan:
```bash
npm run dev
# buka http://localhost:5173
```

> Alternatif proxy (opsional, bila tidak pakai `VITE_API_BASE`): set proxy di `vite.config.ts` → `/api -> http://localhost:5000`

---

## 🚀 Alur Penggunaan

1. **Upload** satu/lebih file `.csv`/`.json`.  
2. (Opsional) Isi **Instruksi tambahan** untuk Gemini (contoh: *“Normalisasi nama daerah ke kab/kota, abaikan baris tanpa harga. Konversi semua harga ke Rp/kg.”*).  
3. Klik **Bersihkan & Parse** → backend memanggil Gemini → hasil tampil di tabel.  
4. Lihat **Ranking**: Top 10 daerah termurah per kualitas.  
5. **Word Cloud & Sentiment**  
   - Pilih mode: **Berdasarkan Kualitas** atau **Berdasarkan Harga**  
   - Klik **Generate Word Cloud** → tampil SVG + ringkasan + metrik sentimen + top words  
6. **Export** data tabel (JSON/CSV) & **SVG** word cloud.  
7. Snapshot hasil disimpan di **localStorage** (tidak hilang saat refresh).

---

## 🔌 API Backend

### `POST /api/ingest-file`
**Body**
```json
{
  "rows": [ /* array of raw objects from CSV/JSON */ ],
  "prompt": "opsional instruksi tambahan"
}
```

**Response (berhasil, JSON murni)**
```json
{
  "ok": true,
  "data": [
    {
      "source": "Twitter | CNN | ...",
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
```

**Response (model tidak mengembalikan JSON murni)**
```json
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
```

**Response (gagal)**
```json
{ "ok": false, "error": "Gemini(ResponsesAPI) timeout after 90000ms" }
```

> Backend **membatasi** jumlah baris (mis. 400) untuk stabilitas & kecepatan.

---

### `POST /api/analyze-sentiment`
**Body**
```json
{
  "rows": [ /* array raw rows; server memproyeksikan kolom teks penting */ ],
  "by": "kualitas", // atau "harga"
  "prompt": "opsional instruksi tambahan"
}
```

**Response (berhasil)**
```json
{
  "ok": true,
  "data": {
    "svg": "<svg ...>...</svg>",
    "sentiments": { "positive": 23, "neutral": 51, "negative": 12, "method": "lexicon+rule-based" },
    "summary": "Ringkasan 1–2 paragraf...",
    "top_words": [
      { "text": "premium", "weight": 38, "sentiment": "positive" },
      { "text": "mahal", "weight": 22, "sentiment": "negative" }
    ]
  }
}
```

**Response (raw)**
```json
{ "ok": true, "raw": "…model reply…", "meta": { "note": "Model tidak mengembalikan 'svg' valid" } }
```

**Response (gagal)**
```json
{ "ok": false, "error": "Responses API 404: {\"error\":{\"message\":\"Model not found: models/gemini-1.5-flash-8b\"...}}" }
```

---

## 🧠 Implementasi Gemini (Stabil)

- Gunakan **Responses API**: `v1beta/responses:generate` + `generationConfig.responseMimeType = "application/json"`.
- Helper `askGeminiAsJson()`:
  - Mencoba otomatis:
    - **Responses API** dengan `models/<id>`
    - **Responses API** dengan `<id>` plain
    - **Legacy** `:generateContent` (fallback)
  - **Retry** exponential backoff + **hard timeout** (default 90s)
- ENV:
  ```env
  GEMINI_API_KEY=...
  GEMINI_MODEL=gemini-1.5-flash  # aman & cepat
  # atau gemini-1.5-flash-8b bila akun Anda mendukung
  ```

**Payload hygiene**
- Server-side **limit** (ingest: 300–400 baris / request).  
- **Hapus** triple backticks ``` dari prompt (hemat token).  
- Prompt tetap **singkat & tegas** (hindari duplikasi aturan).

---

## 🎛️ UI/UX (FE)

- Tema gelap elegan (CSS murni)
- Upload multi-file, progress per chunk, badge info/error
- Tabel zebra, sorting (harga/region/kualitas)
- **Ranking** per kualitas (Top 10 termurah)
- **Word Cloud** (SVG inline), **Sentiment** & Insight
- **Export** CSV/JSON (tabel) & SVG (word cloud)
- Snapshot ke **localStorage** (rows/cleaned/metas/raw/sort)

---

## 🧪 Troubleshooting

**404 dari Gemini**
- `GEMINI_MODEL` tidak cocok/akun tidak punya akses.  
- Pastikan model umum dulu: `gemini-1.5-flash`.  
- Helper akan mencoba `models/<id>` → `<id>` → legacy; baca pesan error lengkap.

**Timeout 60–90s**
- Kecilkan `CHUNK_SIZE` (FE) & `MAX_ROWS` (BE).  
- Ganti model ke `gemini-1.5-flash` (lebih cepat).  
- Naikkan sementara `timeoutMs` di helper (mis. 120_000).

**“Could not establish connection. Receiving end does not exist.”**
- Pesan **extension browser** (bukan fetch kamu). Gunakan Incognito / matikan extension.

**413 PayloadTooLargeError**
- Naikkan limit:
  ```ts
  app.use(express.json({ limit: "25mb" }));
  app.use(express.urlencoded({ extended: true, limit: "25mb" }));
  ```
- Kecilkan file/chunk.

**TypeScript rewel (FE)**
- Type-only import:
  ```ts
  import Papa, { type ParseResult } from "papaparse";
  ```
- Dengan `exactOptionalPropertyTypes: true` → **omit** properti alih-alih set `undefined`.

**ESM NodeNext**
- Selalu impor relatif dengan **akhiran `.js`**.  
  `import route from "./routes/ingest-file.js"`

---

## 🧾 Skrip NPM (Contoh)

**backend/package.json**
```json
{
  "scripts": {
    "dev": "nodemon --config nodemon.json --exec ts-node src/index.ts",
    "build": "tsc -p tsconfig.json",
    "start": "node dist/index.js"
  }
}
```

**frontend/package.json**
```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }
}
```

---

## 🔐 Keamanan

- Jangan commit `.env`
- Batasi ukuran input (server)
- Validasi & sanitasi output (khususnya `svg` bila aplikasi dipublikasikan)

---

## 🗺️ Roadmap (Opsional)

- Persist hasil ke database
- Filter lanjutan per kualitas/region
- Peta (choropleth) harga per kab/kota
- Multi-SVG word cloud per kualitas
- Auth + multi-user workspace

---

## 📝 Lisensi

Pilih lisensi (MIT/Apache-2.0) dan tambahkan berkas `LICENSE`.

---

## 🙌 Kredit

Dikembangkan untuk analitik cepat harga/kualitas beras di Jawa Barat.  
Teknologi: React, Express, Google Gemini (Responses API).
