// scripts/scrape_sibapokting_today.ts
import { chromium, Page } from "playwright";
import dayjs from "dayjs";
import fs from "fs/promises";
import path from "path";

type Row = {
  source: "sibapokting";
  url: string;
  region_text: "Kabupaten Bandung";
  date: string;                       // YYYY-MM-DD (hari ini)
  commodity: "Beras Premium" | "Beras Medium" | "Beras IR64";
  price_value: number;                // Rp/kg
  price_unit: "Rp/kg";
  het?: number | null;
  raw_source: "main" | "varians";
};

const TODAY = dayjs().format("YYYY-MM-DD");
const COMMODITIES = [
  { label: "Beras Premium" as const, aliases: [/BERAS\s+PREMIUM/i] },
  { label: "Beras Medium"  as const, aliases: [/BERAS\s+MEDIUM/i] },
  { label: "Beras IR64"    as const, aliases: [/BERAS\s+IR\.?\s*\.?\s*64/i, /BERAS\s+IR\s*64/i] },
];

function parseRp(s: string): number {
  const m = s.match(/Rp\s*([\d\.]+)/i);
  return m ? parseInt(m[1].replace(/\./g, ""), 10) : 0;
}
function pickHET(s: string): number | null {
  const m = s.match(/HET\s*:\s*Rp\s*([\d\.]+)/i);
  return m ? parseInt(m[1].replace(/\./g, ""), 10) : null;
}

async function grabBlock(page: Page, alias: RegExp): Promise<string | null> {
  const loc = page.locator(`:text-matches("${alias.source}", "${alias.flags || "i"}")`).first();
  if (await loc.count() === 0) return null;
  const handle = await loc.elementHandle();
  if (!handle) return null;
  const text = await handle.evaluate((node) => {
    let p: HTMLElement | null = node as any;
    for (let i = 0; i < 8 && p; i++) {
      p = p.parentElement as HTMLElement | null;
      const t = p?.innerText || "";
      if (t.includes("Saat ini")) return t.trim();
    }
    return (node as HTMLElement).closest("div")?.innerText?.trim() || node.textContent || null;
  });
  return (text || "").toString() || null;
}

async function scrapeMainToday(page: Page): Promise<Row[]> {
  await page.goto("https://sibapokting.bandungkab.go.id/", { waitUntil: "domcontentloaded", timeout: 60000 });

  // SIBAPOKTING menampilkan komoditas beras di beranda & punya "Pilih Tanggal".
  // Kita biarkan default (hari ini) lalu tunggu angka non-nol.
  await page.waitForSelector('text=/BERAS\\s+(PREMIUM|MEDIUM|IR\\.?\\s*64)/i', { timeout: 30000 }).catch(()=>{});
  await page.waitForFunction(
    () => /Saat ini\s*:\s*Rp\s*[1-9]/i.test(document.body.innerText || ""),
    { timeout: 8000 }
  ).catch(()=>{});
  await page.waitForTimeout(800);

  const rows: Row[] = [];
  for (const { label, aliases } of COMMODITIES) {
    let block: string | null = null;
    for (const a of aliases) { block = await grabBlock(page, a); if (block) break; }
    if (!block) continue;
    const price = parseRp(block);
    const het = pickHET(block);
    if (price > 0) {
      rows.push({
        source: "sibapokting",
        url: "https://sibapokting.bandungkab.go.id/",
        region_text: "Kabupaten Bandung",
        date: TODAY,
        commodity: label,
        price_value: price,
        price_unit: "Rp/kg",
        het: het ?? null,
        raw_source: "main",
      });
    }
  }
  return rows;
}

// fallback: /varians → hari ini vs kemarin (tanpa date picker)
async function scrapeVariansToday(page: Page): Promise<Row[]> {
  await page.goto("https://sibapokting.bandungkab.go.id/varians", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector('text=/PERBANDINGAN HARGA/i', { timeout: 15000 }).catch(()=>{});
  await page.waitForTimeout(800);

  const body = await page.evaluate(() => document.body.innerText || "");
  const rows: Row[] = [];

  for (const { label, aliases } of COMMODITIES) {
    let m: RegExpMatchArray | null = null;
    for (const a of aliases) {
      const re = new RegExp(`${a.source}[\\s\\S]*?(\\d{1,3}(?:\\.\\d{3})+)`, a.flags || "i");
      m = body.match(re);
      if (m) break;
    }
    if (!m) continue;
    const price = parseInt(m[1].replace(/\./g, ""), 10);
    if (Number.isFinite(price) && price > 0) {
      rows.push({
        source: "sibapokting",
        url: "https://sibapokting.bandungkab.go.id/varians",
        region_text: "Kabupaten Bandung",
        date: TODAY,
        commodity: label,
        price_value: price,
        price_unit: "Rp/kg",
        het: null,
        raw_source: "varians",
      });
    }
  }
  return rows;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(60_000);

  let rows = await scrapeMainToday(page);
  if (!rows.length) {
    await page.waitForTimeout(1000);
    rows = await scrapeMainToday(page);
  }
  if (!rows.length) {
    rows = await scrapeVariansToday(page);
  }

  await fs.mkdir("data", { recursive: true });
  await fs.writeFile(path.join("data", `sibapokting_${TODAY}.json`), JSON.stringify(rows, null, 2), "utf8");
  console.log(`SIBAPOKTING ${TODAY} -> ${rows.length} rows`);

  await browser.close();
})();
