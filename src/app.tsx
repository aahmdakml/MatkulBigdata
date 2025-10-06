import { useEffect, useMemo, useState } from "react";
import Papa, { type ParseResult } from "papaparse";
import { postJSON } from "./lib/api";
import "./style.css";

type Entry = {
  source?: string;
  region: string;
  harga: number;
  kualitas?: string;
  waktu?: string;
  url?: string;
  note?: string;
};

type Meta = {
  received: number;
  baseline: number;
  afterModel: number;
  final: number;
  note?: string;
  tookMs?: number;
};

type IngestResp =
  | { ok: true; data: Entry[]; meta?: Meta }
  | { ok: true; raw: string; meta?: Meta }
  | { ok: false; error: string };

type CloudResult = {
  svg: string;
  sentiments: { positive: number; neutral: number; negative: number; method?: string };
  summary: string;
  top_words?: { text: string; weight: number; sentiment?: "positive" | "neutral" | "negative" }[];
};

const STORAGE_KEY = "beras_mvp_snapshot_v2";

// ---------- Helpers ----------
function normQuality(q?: string) {
  return (q ?? "").toLowerCase().trim() || "unknown";
}
const QUALITY_PRIORITY = ["premium", "super", "medium", "ir64", "unknown"];

function buildRankingByQuality(entries: Entry[], topN = 10) {
  const byQ = new Map<string, Map<string, number>>();
  for (const e of entries) {
    const q = normQuality(e.kualitas);
    const r = (e.region ?? "").trim();
    if (!r || !Number.isFinite(e.harga)) continue;

    if (!byQ.has(q)) byQ.set(q, new Map());
    const m = byQ.get(q)!;
    const prev = m.get(r);
    if (prev == null || e.harga < prev) m.set(r, e.harga);
  }

  const out = new Map<string, { region: string; harga: number }[]>();
  for (const [q, m] of byQ) {
    const arr = [...m.entries()].map(([region, harga]) => ({ region, harga }));
    arr.sort((a, b) => a.harga - b.harga);
    out.set(q, arr.slice(0, topN));
  }
  return out;
}

function download(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---------- Komponen ----------
export default function App() {
  const [rows, setRows] = useState<any[]>([]);
  const [cleaned, setCleaned] = useState<Entry[]>([]);
  const [raw, setRaw] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [sortKey, setSortKey] = useState<"region" | "harga" | "kualitas">("harga");
  const [asc, setAsc] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [metas, setMetas] = useState<Meta[]>([]);

  // Word Cloud states
  const [cloudBy, setCloudBy] = useState<"harga" | "kualitas">("kualitas");
  const [cloudLoading, setCloudLoading] = useState(false);
  const [cloudErr, setCloudErr] = useState<string | null>(null);
  const [cloudResult, setCloudResult] = useState<CloudResult | null>(null);
  const [cloudRaw, setCloudRaw] = useState<string>("");

  // Restore snapshot
  useEffect(() => {
    try {
      const s = localStorage.getItem(STORAGE_KEY);
      if (!s) return;
      const snap = JSON.parse(s);
      if (Array.isArray(snap.rows)) setRows(snap.rows);
      if (Array.isArray(snap.cleaned)) setCleaned(snap.cleaned);
      if (Array.isArray(snap.metas)) setMetas(snap.metas);
      if (typeof snap.raw === "string") setRaw(snap.raw);
      if (snap.sortKey === "harga" || snap.sortKey === "region" || snap.sortKey === "kualitas") {
        setSortKey(snap.sortKey);
      }
      if (typeof snap.asc === "boolean") setAsc(snap.asc);
    } catch {}
  }, []);

  // Save snapshot
  useEffect(() => {
    if (cleaned.length > 0 || metas.length > 0 || raw) {
      const snapshot = { rows, cleaned, metas, raw, sortKey, asc };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
    }
  }, [rows, cleaned, metas, raw, sortKey, asc]);

  function handleFiles(files: FileList) {
    setErr(null);
    setProgress(null);

    const promises: Promise<any[]>[] = [];
    Array.from(files).forEach((file) => {
      const ext = file.name.split(".").pop()?.toLowerCase();

      if (ext === "json") {
        promises.push(
          new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = () => {
              try {
                const data = JSON.parse(String(reader.result));
                if (Array.isArray(data)) resolve(data);
                else if (data?.data && Array.isArray(data.data)) resolve(data.data);
                else resolve([data]);
              } catch (e: any) {
                setErr((prev) => (prev ? prev + "\n" : "") + `JSON invalid di ${file.name}: ${e.message}`);
                resolve([]);
              }
            };
            reader.readAsText(file);
          })
        );
      } else if (ext === "csv") {
        promises.push(
          new Promise((resolve) => {
            Papa.parse(file, {
              header: true,
              dynamicTyping: false,
              skipEmptyLines: true,
              complete: (res: ParseResult<any>) => resolve(res.data as any[]),
              error: (error) =>
                setErr((prev) => (prev ? prev + "\n" : "") + `CSV error di ${file.name}: ${error.message}`),
            });
          })
        );
      } else {
        setErr((prev) => (prev ? prev + "\n" : "") + `Format tidak didukung: ${file.name}`);
      }
    });

    Promise.all(promises).then((parts) => {
      const merged = parts.flat();
      setRows(merged);
    });
  }

  function chunk<T>(arr: T[], size: number): T[][] {
    const out: T[][] = [];
    for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
    return out;
  }

  async function runIngestChunked() {
    setLoading(true);
    setErr(null);
    setMetas([]);
    setProgress(null);

    const CHUNK_SIZE = 1000;
    const parts = chunk(rows, CHUNK_SIZE);
    if (parts.length === 0) {
      setLoading(false);
      return;
    }
    setProgress({ done: 0, total: parts.length });

    const all: Entry[] = [];
    let nextRaw = "";
    const nextMetas: Meta[] = [];

    for (let i = 0; i < parts.length; i++) {
      const body = { rows: parts[i], prompt, responseAsJson: true };

      try {
        const resp = await postJSON<IngestResp>("/api/ingest-file", body);
        if (!resp.ok) throw new Error((resp as any).error);

        if ("raw" in resp) {
          nextRaw += (nextRaw ? "\n\n" : "") + resp.raw;
          if (resp.meta) nextMetas.push(resp.meta);
        } else {
          if (resp.meta) nextMetas.push(resp.meta);
          all.push(...resp.data);
        }
      } catch (e: any) {
        setErr(`Gagal di chunk ${i + 1}/${parts.length}: ${e.message ?? e}`);
        break;
      }

      setProgress({ done: i + 1, total: parts.length });
      await new Promise((r) => setTimeout(r, 120));
    }

    if (!err) {
      const seen = new Set<string>();
      const deduped = all.filter((r) => {
        const key = `${r.region}|${r.harga}|${r.kualitas ?? "-"}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });

      setCleaned(deduped);
      setRaw(nextRaw);
      setMetas(nextMetas);
    }

    setLoading(false);
  }

  function resetSnapshot() {
    setCleaned([]);
    setRaw("");
    setMetas([]);
    setErr(null);
    setProgress(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
  }

  function exportJSON(data: Entry[]) {
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    download(`beras-jabar-${ts}.json`, blob);
  }

  function exportCSV(data: Entry[]) {
    const headers = ["region", "harga", "kualitas", "source", "waktu", "url", "note"] as const;
    const escape = (v: unknown) => {
      const s = v == null ? "" : String(v);
      const e = s.replace(/"/g, '""');
      return /[",\n]/.test(e) ? `"${e}"` : e;
    };
    const lines = [
      headers.join(","),
      ...data.map((r) =>
        [
          escape(r.region),
          escape(r.harga),
          escape(r.kualitas ?? ""),
          escape(r.source ?? ""),
          escape(r.waktu ?? ""),
          escape(r.url ?? ""),
          escape(r.note ?? ""),
        ].join(",")
      ),
    ].join("\n");

    const BOM = "\uFEFF";
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const blob = new Blob([BOM + lines], { type: "text/csv;charset=utf-8;" });
    download(`beras-jabar-${ts}.csv`, blob);
  }

  async function generateWordCloud() {
    try {
      setCloudLoading(true);
      setCloudErr(null);
      setCloudResult(null);
      setCloudRaw("");

      const payloadRows = rows.length > 0 ? rows : cleaned; // fallback
      const resp = await postJSON<{ ok: boolean; data?: CloudResult; raw?: string; error?: string }>(
        "/api/analyze-sentiment",
        { rows: payloadRows, by: cloudBy }
      );

      if (!resp.ok) throw new Error(resp.error || "Analyze failed");
      if (resp.data) setCloudResult(resp.data);
      else if (resp.raw) setCloudRaw(resp.raw);
      else setCloudErr("Tidak ada 'data' atau 'raw' pada respons.");
    } catch (e: any) {
      setCloudErr(e?.message ?? String(e));
    } finally {
      setCloudLoading(false);
    }
  }

  function exportSVG(svgString: string) {
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
    download(`wordcloud-${cloudBy}-${ts}.svg`, blob);
  }

  const sorted = useMemo(() => {
    const copy = [...cleaned];
    copy.sort((a, b) => {
      const A =
        sortKey === "harga"
          ? a.harga
          : sortKey === "region"
          ? (a.region || "").toLowerCase()
          : (a.kualitas || "").toLowerCase();
      const B =
        sortKey === "harga"
          ? b.harga
          : sortKey === "region"
          ? (b.region || "").toLowerCase()
          : (b.kualitas || "").toLowerCase();

      if (A < B) return asc ? -1 : 1;
      if (A > B) return asc ? 1 : -1;
      return 0;
    });
    return copy;
  }, [cleaned, sortKey, asc]);

  const rankingMap = useMemo(() => buildRankingByQuality(cleaned, 10), [cleaned]);

  return (
    <div className="app-wrap">
      <header className="app-header">
        <h1>Analitik Harga/Kualitas Beras – Jabar</h1>
        <p className="subtitle">
          Upload data (CSV/JSON) → Normalisasi (Gemini) → Tabel & Ranking → Word Cloud + Sentiment
        </p>
      </header>

      <main className="app-main">
        {/* Upload & Controls */}
        <section className="card">
          <h2 className="card-title">1) Data Input</h2>

          <div className="grid gap">
            <label className="stack gap-xs">
              <span className="label">Upload file (.csv / .json) — bisa lebih dari satu</span>
              <input
                className="input"
                type="file"
                accept=".csv,.json,application/json,text/csv"
                multiple
                onChange={(e) => {
                  const files = (e.target as HTMLInputElement).files;
                  if (files && files.length) handleFiles(files);
                }}
              />
            </label>

            <label className="stack gap-xs">
              <span className="label">Instruksi tambahan ke Gemini (opsional)</span>
              <textarea
                className="textarea"
                rows={3}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder='Contoh: "Normalisasi nama daerah ke kab/kota, abaikan baris tanpa harga. Konversi semua harga ke Rp/Kg bila memungkinkan."'
              />
            </label>

            <div className="row wrap gap-sm">
              <button className="btn primary" disabled={loading || rows.length === 0} onClick={runIngestChunked}>
                {loading ? "Memproses…" : `Bersihkan & Parse (${rows.length} baris)`}
              </button>
              <button className="btn ghost" disabled={loading} onClick={resetSnapshot}>
                Reset hasil
              </button>

              <button
                className="btn"
                disabled={sorted.length === 0}
                onClick={() => exportJSON(sorted)}
                title="Ekspor data tabel (urut sesuai tampilan) ke JSON"
              >
                Export JSON
              </button>
              <button
                className="btn"
                disabled={sorted.length === 0}
                onClick={() => exportCSV(sorted)}
                title="Ekspor data tabel (urut sesuai tampilan) ke CSV"
              >
                Export CSV
              </button>

              {progress && (
                <span className="badge info">
                  Progress: {progress.done}/{progress.total} chunk
                </span>
              )}
              {err && <span className="badge danger">Error: {err}</span>}
            </div>
          </div>

          {metas.length > 0 && (
            <div className="meta-box">
              <strong>Ringkasan proses:</strong>
              <ul>
                {metas.map((m, i) => (
                  <li key={i}>
                    Chunk {i + 1}: received=<b>{m.received}</b>, baseline=<b>{m.baseline}</b>, afterModel=
                    <b>{m.afterModel}</b>, final=<b>{m.final}</b>
                    {m.tookMs ? `, took=${m.tookMs}ms` : ""}
                    {m.note ? <em> — {m.note}</em> : null}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {raw && (
            <div className="stack">
              <h3 className="section-title">Raw (model tidak mengembalikan JSON murni)</h3>
              <pre className="pre">{raw}</pre>
            </div>
          )}
        </section>

        {/* Ranking */}
        {cleaned.length > 0 && (
          <section className="card">
            <h2 className="card-title">2) Rangkuman — Top 10 Daerah Termurah per Kualitas</h2>
            <div className="grid two gap">
              {Array.from(rankingMap.entries())
                .sort(([qa], [qb]) => {
                  const ia = QUALITY_PRIORITY.indexOf(qa);
                  const ib = QUALITY_PRIORITY.indexOf(qb);
                  const sa = ia === -1 ? Number.MAX_SAFE_INTEGER : ia;
                  const sb = ib === -1 ? Number.MAX_SAFE_INTEGER : ib;
                  return sa - sb || qa.localeCompare(qb);
                })
                .map(([q, list]) => (
                  <div key={q} className="panel">
                    <div className="panel-head">
                      <span className="badge">{q}</span>
                      <span className="muted">({list.length} daerah)</span>
                    </div>
                    {list.length === 0 ? (
                      <div className="muted">Tidak ada data</div>
                    ) : (
                      <ol className="ol">
                        {list.map((item, idx) => (
                          <li key={idx}>
                            <span className="bold">{item.region}</span>
                            <span className="muted"> — </span>
                            <span className="price">{item.harga.toLocaleString("id-ID")} Rp/kg</span>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                ))}
            </div>
          </section>
        )}

        {/* Tabel */}
        {sorted.length > 0 && (
          <section className="card">
            <h2 className="card-title">3) Tabel Hasil Normalisasi</h2>
            <div className="row gap-sm">
              <div className="stack gap-2xs">
                <span className="label sm">Urutkan</span>
                <select className="select" value={sortKey} onChange={(e) => setSortKey(e.target.value as any)}>
                  <option value="harga">Harga</option>
                  <option value="region">Region</option>
                  <option value="kualitas">Kualitas</option>
                </select>
              </div>
              <button className="btn" onClick={() => setAsc((v) => !v)}>
                {asc ? "A→Z / Kecil→Besar" : "Z→A / Besar→Kecil"}
              </button>
              <span className="badge">Total: {sorted.length}</span>
            </div>

            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Region</th>
                    <th className="num">Harga (Rp/kg)</th>
                    <th>Kualitas</th>
                    <th>Source</th>
                    <th>Waktu</th>
                    <th>URL</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((r, i) => (
                    <tr key={i}>
                      <td>{r.region}</td>
                      <td className="num">{r.harga.toLocaleString("id-ID")}</td>
                      <td><span className="pill">{r.kualitas ?? "-"}</span></td>
                      <td>{r.source ?? "-"}</td>
                      <td>{r.waktu ?? "-"}</td>
                      <td>
                        {r.url ? (
                          <a className="link" href={r.url} target="_blank" rel="noreferrer">
                            link
                          </a>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td>{r.note ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Word Cloud & Sentiment */}
        <section className="card">
          <h2 className="card-title">4) Word Cloud & Sentiment Analysis</h2>

          <div className="row wrap gap-sm">
            <label className="chip">
              <input
                type="radio"
                name="cloudBy"
                value="kualitas"
                checked={cloudBy === "kualitas"}
                onChange={() => setCloudBy("kualitas")}
              />
              <span>Berdasarkan Kualitas</span>
            </label>
            <label className="chip">
              <input
                type="radio"
                name="cloudBy"
                value="harga"
                checked={cloudBy === "harga"}
                onChange={() => setCloudBy("harga")}
              />
              <span>Berdasarkan Harga</span>
            </label>

            <button
              className="btn accent"
              disabled={cloudLoading || (rows.length === 0 && cleaned.length === 0)}
              onClick={generateWordCloud}
            >
              {cloudLoading
                ? "Menghitung di Gemini…"
                : `Generate Word Cloud (${rows.length > 0 ? rows.length : cleaned.length} baris)`}
            </button>

            {cloudResult?.svg && (
              <button className="btn" onClick={() => exportSVG(cloudResult.svg)}>
                Export Word Cloud (SVG)
              </button>
            )}

            {cloudErr && <span className="badge danger">Error: {cloudErr}</span>}
          </div>

          {cloudRaw && (
            <div className="stack">
              <div className="section-title">Raw (model tidak mengembalikan JSON murni)</div>
              <pre className="pre">{cloudRaw}</pre>
            </div>
          )}

          {cloudResult && (
            <div className="grid two gap" style={{ marginTop: 12 }}>
              <div className="panel scroll">
                <div
                  dangerouslySetInnerHTML={{ __html: cloudResult.svg }}
                  className="svgbox"
                />
              </div>

              <div className="panel">
                <strong className="section-title">Sentiment Summary</strong>
                <div className="row gap">
                  <span className="badge success">Positive: {cloudResult.sentiments?.positive ?? 0}</span>
                  <span className="badge warn">Neutral: {cloudResult.sentiments?.neutral ?? 0}</span>
                  <span className="badge danger">Negative: {cloudResult.sentiments?.negative ?? 0}</span>
                  {cloudResult.sentiments?.method ? (
                    <span className="badge info">method: {cloudResult.sentiments.method}</span>
                  ) : null}
                </div>

                {cloudResult.summary && (
                  <>
                    <div className="section-title" style={{ marginTop: 8 }}>Insight</div>
                    <div className="note">{cloudResult.summary}</div>
                  </>
                )}

                {cloudResult.top_words?.length ? (
                  <>
                    <div className="section-title" style={{ marginTop: 8 }}>Top Words</div>
                    <ul className="ol">
                      {cloudResult.top_words.map((w, i) => (
                        <li key={i}>
                          <span className="bold">{w.text}</span>
                          <span className="muted"> — weight {w.weight}</span>
                          {w.sentiment ? <em> ({w.sentiment})</em> : null}
                        </li>
                      ))}
                    </ul>
                  </>
                ) : null}
              </div>
            </div>
          )}
        </section>
      </main>

      <footer className="app-footer">
        <span>© {new Date().getFullYear()} Analitik Beras Jabar — MVP</span>
      </footer>
    </div>
  );
}
