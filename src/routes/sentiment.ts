import { Router } from "express";
import { askGeminiAsJson } from "../gemini.js";

// tipe hasil dari Gemini
type CloudResult = {
  svg: string; // inline SVG string starting with <svg...
  sentiments: { positive: number; neutral: number; negative: number; method?: string };
  summary: string;
  top_words?: { text: string; weight: number; sentiment?: "positive" | "neutral" | "negative" }[];
};

const router = Router();

type AnalyzeReq = {
  rows: unknown[];
  by?: "harga" | "kualitas";      // patokan analisis (konteks)
  prompt?: string;                 // instruksi tambahan opsional
};

function sanitizeText(s: unknown, max = 500): string {
  const txt = typeof s === "string" ? s : s == null ? "" : String(s);
  return txt.length > max ? txt.slice(0, max) + "…" : txt;
}

// Ekstrak kolom-kolom teks yang relevan agar payload hemat
function projectRowsForNLP(rows: any[], maxRows = 400) {
  const out: Array<{
    text: string;
    harga?: number;
    kualitas?: string;
    region?: string;
    source?: string;
    waktu?: string;
  }> = [];

  for (const r of rows.slice(0, maxRows)) {
    // ambil ragam field teks umum dari 2 dialek
    const text =
      [
        r?.title,
        r?.description,
        r?.content,
        r?.caption,
        r?.text_original,
        r?.keywords,
        r?.note
      ]
        .filter(Boolean)
        .map((x: any) => sanitizeText(x))
        .join(" | ");

    const harga = r?.harga ?? r?.price ?? r?.harga_value ?? r?.prices?.normalized;
    const kualitas = r?.kualitas ?? r?.quality ?? r?.mutu ?? r?.grade;
    const region = r?.region ?? r?.lokasi ?? r?.location ?? r?.kota ?? r?.kabupaten;
    const source = r?.source ?? r?.platform ?? r?.username;
    const waktu = r?.scraped_date ?? r?.published_date ?? r?.tanggal;

    const item: { text: string } & Partial<{
        harga: number;
        kualitas: string;
        region: string;
        source: string;
        waktu: string;
        }> = { text: text || "" };

        if (typeof harga === "number") item.harga = harga;
        if (typeof kualitas === "string") item.kualitas = kualitas;
        if (typeof region === "string") item.region = region;
        if (typeof source === "string") item.source = source;
        if (typeof waktu === "string") item.waktu = waktu;

        out.push(item);
        }
  return out;
}

const BASE_PROMPT = `
Anda adalah analis NLP. Buat **WORD CLOUD** dan **SENTIMEN** dari kumpulan dokumen teks yang berhubungan dengan harga/kualitas beras/padi/gabah.

KELUARAN HANYA JSON VALID dengan format:
{
  "svg": "<svg ...>...</svg>",
  "sentiments": { "positive": number, "neutral": number, "negative": number, "method": string? },
  "summary": string,
  "top_words": [ { "text": string, "weight": number, "sentiment": "positive" | "neutral" | "negative"? }, ... ]?
}

ATURAN:
- "svg" adalah inline SVG word cloud (tanpa resource eksternal), lebar minimal 900px, tinggi 600px, gunakan variasi ukuran font sesuai "weight" (kata lebih penting = lebih besar). Pastikan <svg> diawali tag pembuka yang valid.
- Pertimbangkan konteks **BY_CONTEXT** (ditulis di bawah) saat menilai sentimen dan bobot kata.
- Sentimen dievaluasi dari "text" tiap item; gunakan skala kasar 3 kelas: positive/neutral/negative.
- "summary" ringkas (<= 120 kata) memuat insight utama (kualitas apa yang cenderung mahal/murah, wilayah dominan bila terdeteksi).
- Jangan keluarkan teks lain di luar JSON.
`.trim();

router.post("/analyze-sentiment", async (req, res) => {
  try {
    const { rows = [], by = "kualitas", prompt = "" } = (req.body ?? {}) as AnalyzeReq;
    if (!Array.isArray(rows)) {
      return res.status(400).json({ ok: false, error: "`rows` harus array" });
    }

    const skinny = projectRowsForNLP(rows, 400);

    const byContext =
      by === "harga"
        ? `BY_CONTEXT: Fokuskan analisis pada persepsi harga (mahal/murah), tren, dan sebutan/angka terkait harga.`
        : `BY_CONTEXT: Fokuskan analisis pada persepsi kualitas (premium/medium/IR64/dll) dan kaitannya dengan harga bila disebutkan.`;

    const userText =
      BASE_PROMPT +
      `

${byContext}

${prompt ? `Instruksi tambahan:\n${prompt}\n` : ""}

DATA (format ringkas):
\`\`\`json
${JSON.stringify(skinny, null, 2)}
\`\`\`
`;

    let text: string;
    try {
      text = await askGeminiAsJson(userText);
    } catch (e: any) {
      console.error("Gemini fetch error:", e?.message ?? e);
      return res.status(500).json({ ok: false, error: e?.message ?? "Gemini request failed" });
    }

    // parse hasil
    try {
      const parsed = JSON.parse(text) as CloudResult;
      if (!parsed || typeof parsed.svg !== "string" || !parsed.svg.trim().startsWith("<svg")) {
        return res.json({
          ok: true,
          raw: text,
          meta: { note: "Model tidak mengembalikan JSON dengan 'svg' yang valid." }
        });
      }
      return res.json({ ok: true, data: parsed });
    } catch {
      return res.json({
        ok: true,
        raw: text,
        meta: { note: "Model tidak mengembalikan JSON murni." }
      });
    }
  } catch (err: any) {
    console.error("analyze-sentiment error:", err?.message ?? err);
    return res.status(500).json({ ok: false, error: err?.message ?? "analyze failed" });
  }
});

export default router;
