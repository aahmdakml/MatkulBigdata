export async function postJSON<T>(
  url: string,
  body: unknown
): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await r.text();
  if (!r.ok) {
    throw new Error(`HTTP ${r.status}: ${text}`);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    // biarkan FE yang menampilkan raw bila perlu
    return { ok: true, raw: text } as unknown as T;
  }
}
