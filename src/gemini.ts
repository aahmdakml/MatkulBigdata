import { GoogleGenerativeAI } from "@google/generative-ai";

const API_KEY = process.env.GEMINI_API_KEY;
if (!API_KEY) throw new Error("GEMINI_API_KEY belum diset di .env");

// Model aman & cepat. Kamu bisa ganti via .env => GEMINI_MODEL=gemini-1.5-flash
export const MODEL_ID = process.env.GEMINI_MODEL ?? "gemini-2.5-flash";

// Inisialisasi client sekali
const client = new GoogleGenerativeAI(API_KEY);

/**
 * Panggil Gemini dan minta output JSON.
 * - Jika SDK baru: pakai Responses API.
 * - Jika SDK lama: fallback ke generateContent (v1beta).
 *   (NB: Pada beberapa region/akun, generateContent + model 1.5* bisa 404.
 *    Makanya upgrade SDK sangat disarankan.)
 */
export async function askGeminiAsJson(prompt: string): Promise<string> {
  const anyClient = client as any;

  // 1) Responses API tersedia? (SDK baru)
  if (anyClient.responses?.generate) {
    const resp = await anyClient.responses.generate({
      model: MODEL_ID,
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      response_mime_type: "application/json",
    });
    // SDK baru bisa resp.text() atau resp.response.text()
    return typeof resp.text === "function" ? resp.text() : resp.response.text();
  }

  // 2) Fallback: SDK lama (generateContent)
  const model = anyClient.getGenerativeModel({ model: MODEL_ID });
  const resp = await model.generateContent({
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: { responseMimeType: "application/json" },
  });
  return resp.response.text();
}
