import { Router } from "express";
import { askGeminiAsJson } from "../gemini.js";

const router = Router();

const FIXED_PROMPT = `
Kamu ETL assistant. Normalisasikan data beras/padi/gabah menjadi **JSON array of objects** dengan field PERSIS:
{ "source"?:string, "region":string, "harga":number, "kualitas"?:string, "waktu"?:string, "url"?:string, "note"?:string }

ATURAN WAJIB:
- "harga" adalah Rupiah per Kg (number murni). Jika satuan lain & bisa dikonversi, konversi ke per Kg; jika ambigu, SKIP baris tsb.
- "region" dinormalisasi ke nama kabupaten/kota di Jawa Barat (contoh: "Kota Bandung", "Kabupaten Garut"). Jika tidak jelas di Jabar, SKIP.
- "kualitas" dinormalisasi ke label sederhana (contoh umum: "premium", "medium", "ir64", dll). Gunakan lowercase.
- "source","waktu","url","note" opsional; isi bila ada.
- **Jawab HANYA JSON array valid** (tanpa teks lain, tanpa ringkasan, tanpa ranking).
`.trim();

router.post("/ingest-file", async (req, res) => {
  try {
    const { rows = [], prompt = "" } = req.body ?? {};
    if (!Array.isArray(rows)) {
      return res.status(400).json({ ok: false, error: "`rows` harus array" });
    }

    const fixedPrompt =
    FIXED_PROMPT +
    (prompt ? `\n\nInstruksi tambahan dari user:\n${prompt}` : "") + "\n\nData:\n```json\n" + JSON.stringify(rows, null, 2) + "\n```";

    let text: string;
    try {
      text = await askGeminiAsJson(fixedPrompt);
    } catch (e: any) {
      console.error("Gemini fetch error:", e?.message ?? e);
      return res.status(500).json({ ok: false, error: e?.message ?? "Gemini request failed" });
    }

    try {
      const parsed = JSON.parse(text);
      const arr = Array.isArray(parsed) ? parsed : [];
      return res.json({
        ok: true,
        data: arr,
        meta: { received: rows.length, baseline: rows.length, afterModel: arr.length, final: arr.length },
      });
    } catch {
      return res.json({
        ok: true,
        raw: text,
        meta: { received: rows.length, baseline: rows.length, afterModel: 0, final: 0, note: "Model tidak mengembalikan JSON murni" },
      });
    }
  } catch (err: any) {
    console.error("ingest-file error:", err?.message ?? err);
    return res.status(500).json({ ok: false, error: err?.message ?? "ingest failed" });
  }
});

export default router;
