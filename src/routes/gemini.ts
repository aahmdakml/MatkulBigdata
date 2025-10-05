import { Router } from "express";
import { askGeminiAsJson } from "../gemini.js";

const router = Router();

// Endpoint generik (prompt bebas)
router.post("/gemini", async (req, res) => {
  try {
    const { prompt = "", data, responseAsJson = true } = req.body ?? {};

    const userText =
      typeof data !== "undefined"
        ? `${prompt}\n\nData:\n\`\`\`json\n${JSON.stringify(data, null, 2)}\n\`\`\``
        : String(prompt);

    const text = await askGeminiAsJson(userText);

    if (responseAsJson) {
      try {
        const json = JSON.parse(text);
        return res.json({ ok: true, data: json });
      } catch {
        return res.json({ ok: true, raw: text });
      }
    }

    res.json({ ok: true, text });
  } catch (err: any) {
    console.error("Gemini error:", err?.message || err);
    res.status(500).json({ ok: false, error: err?.message ?? "Gemini request failed" });
  }
});

export default router;
