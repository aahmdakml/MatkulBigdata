#!/usr/bin/env ts-node
/**
 * Scraper CLI — Detik (Bandung / Jawa Barat) for beras/gabah prices
 * Output: NDJSON rows — one price per commodity per article
 *
 * Catatan struktur:
 * - Banyak artikel detikJabar “Daftar Harga … Bandung” menulis:
 *   "1. Beras Medium"  (baris ini)
 *   "Rp13.000 / kg ..." (baris berikutnya)  ← penting!  :contentReference[oaicite:2]{index=2}
 * - Artikel lain mirip (Medium/Premium di baris terpisah).  :contentReference[oaicite:3]{index=3}
 */

import fs from "fs";
import path from "path";
import axios from "axios";
import * as cheerio from "cheerio";
import dayjs from "dayjs";

// ------------------- CLI args -------------------
const args = process.argv.slice(2);
function getArg(name: string, def?: string) {
  const i = args.findIndex(a => a === `--${name}`);
  if (i >= 0 && args[i + 1]) return args[i + 1];
  const eq = args.find(a => a.startsWith(`--${name}=`));
  if (eq) return eq.split("=")[1];
  return def;
}
const OUT = getArg("out", "data/news_bandung.ndjson")!;
const PAGES = Math.max(1, parseInt(getArg("pages", "3")!, 10));
const SINCE = getArg("since", ""); // ISO date optional
const SINCE_DJ = SINCE ? dayjs(SINCE) : null;

fs.mkdirSync(path.dirname(OUT), { recursive: true });

// ------------------- Constants -------------------
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36";

const DETIK_TAGS = [
  "https://www.detik.com/tag/harga-beras-di-bandung",           // tag list (byk “Daftar Harga … Bandung”)  :contentReference[oaicite:4]{index=4}
  "https://www.detik.com/tag/harga-beras-di-bandung-hari-ini",
];

const DETIK_JABAR_LISTING = "https://www.detik.com/jabar/berita"; // fallback list

const REGION_KEYWORDS = [
  /kota bandung/i, /kabupaten bandung/i, /bandung/i, /jawa barat/i,
  /karawang/i, /subang/i, /indramayu/i, /cirebon/i, /garut/i, /tasikmalaya/i, /cianjur/i,
  /sukabumi/i, /bogor/i, /bekasi/i, /sumedang/i, /majalengka/i, /purwakarta/i, /kuningan/i,
  /pangandaran/i, /depok/i, /cimahi/i, /banjar/i
];

const RE_BERAS_MED = /\bberas[^.\n]{0,40}medium\b/i;
const RE_BERAS_PREM = /\bberas[^.\n]{0,40}premium\b/i;
const RE_BERAS_IR64 = /\bberas[^.\n]{0,60}(ir\.?\s*64|ir64|setra ramos)\b/i;
const RE_GABAH      = /\bgabah\b|\bgkp\b|\bgkg\b/i;

const RE_RP = /(?:Rp|IDR)\s*([0-9]{1,3}(?:[.,][0-9]{3})+)/i;
const RE_UNIT_NEAR = /(kg|kilogram|ltr|liter)/i;

// ------------------- Utils -------------------
const sleep = (ms: number) => new Promise(res => setTimeout(res, ms));

async function fetchHtml(url: string): Promise<string> {
  const { data } = await axios.get(url, {
    headers: { "User-Agent": UA },
    timeout: 20000,
  });
  return data as string;
}

function absoluteUrl(base: string, href?: string) {
  try {
    if (!href) return "";
    return new URL(href, base).toString();
  } catch {
    return href || "";
  }
}

function unique<T>(arr: T[]) {
  return Array.from(new Set(arr));
}

function parseDate($: cheerio.CheerioAPI): string {
  const meta = $('meta[property="article:published_time"]').attr("content")
    || $('meta[itemprop="datePublished"]').attr("content")
    || $("time").attr("datetime") || "";
  return meta;
}

function guessRegion(text: string, fallback = "Bandung"): string {
  const m = text.match(/^\s*([A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ\s\.]+)\s*-\s*/m);
  if (m) return m[1];

  for (const re of REGION_KEYWORDS) {
    const mm = text.match(re);
    if (mm) {
      const hit = mm[0];
      if (/jawa barat/i.test(hit)) return "Jawa Barat";
      if (/bandung/i.test(hit)) {
        if (/kota bandung/i.test(text)) return "Kota Bandung";
        if (/kabupaten bandung/i.test(text)) return "Kabupaten Bandung";
        return "Bandung";
      }
      return hit.replace(/\b(kota|kabupaten)\b/ig, "").trim();
    }
  }
  return fallback;
}

function parsePrice(lineOrBlock: string): { value: number; unit: "kg" | "ltr" } | null {
  const m = lineOrBlock.match(RE_RP);
  if (!m) return null;
  const value = parseInt(m[1].replace(/[^\d]/g, ""), 10);
  const idx = m.index || 0;
  const near = lineOrBlock.slice(Math.max(0, idx - 40), Math.min(lineOrBlock.length, idx + m[0].length + 40));
  const unitRaw = near.match(RE_UNIT_NEAR)?.[1] || "kg";
  const unit = unitRaw.toLowerCase().startsWith("l") ? "ltr" : "kg";
  return { value, unit };
}

// ------------------- Seeding -------------------
async function seedDetikFromTag(tagUrl: string, pages = 3): Promise<string[]> {
  const urls: string[] = [];
  for (let p = 1; p <= pages; p++) {
    const pageUrl = `${tagUrl}?page=${p}`;
    const html = await fetchHtml(pageUrl);
    const $ = cheerio.load(html);
    $("a[href*='/d-']").each((_, a) => {
      const href = ($(a).attr("href") || "").split("?")[0];
      if (/\/d-\d+/.test(href)) urls.push(absoluteUrl(pageUrl, href));
    });
    await sleep(300);
  }
  return unique(urls);
}

async function seedDetikJabarListing(pages = 1): Promise<string[]> {
  const base = DETIK_JABAR_LISTING;
  const urls: string[] = [];
  for (let p = 1; p <= pages; p++) {
    const pageUrl = `${base}?page=${p}`;
    const html = await fetchHtml(pageUrl);
    const $ = cheerio.load(html);
    $("a[href*='/d-']").each((_, a) => {
      const href = ($(a).attr("href") || "").split("?")[0];
      const title = $(a).text() || "";
      if (/harga beras|daftar harga|sembako|bandung/i.test(title)) {
        urls.push(absoluteUrl(pageUrl, href));
      }
    });
    await sleep(300);
  }
  return unique(urls);
}

// ------------------- Parser -------------------
type Item = {
  source: "detik";
  url: string;
  date_published: string;
  region_text: string;
  commodity: "Beras Medium" | "Beras Premium" | "Beras IR64" | "Gabah" | "Beras";
  price_value: number;
  price_unit: "Rp/kg" | "Rp/ltr";
  context_type: "eceran" | "produsen";
  raw_text: string;
  headline?: string;
};

function classifyCommodity(text: string): Item["commodity"] {
  if (RE_BERAS_MED.test(text)) return "Beras Medium";
  if (RE_BERAS_PREM.test(text)) return "Beras Premium";
  if (RE_BERAS_IR64.test(text)) return "Beras IR64";
  if (RE_GABAH.test(text)) return "Gabah";
  if (/beras/i.test(text)) return "Beras";
  return "Beras";
}

function classifyContext(text: string): Item["context_type"] {
  return /gabah|gkp|gkg|penggilingan|petani/i.test(text) ? "produsen" : "eceran";
}

async function parseDetikArticle(url: string): Promise<Item[]> {
  const html = await fetchHtml(url);
  const $ = cheerio.load(html);

  const headline = $("h1").first().text().trim();
  const published = parseDate($);

  // Prefer AMP (lebih bersih), fallback ke body normal
  const ampHref = $('link[rel="amphtml"]').attr("href");
  let bodyText = "";
  if (ampHref) {
    try {
      const ampHtml = await fetchHtml(absoluteUrl(url, ampHref));
      const $$ = cheerio.load(ampHtml);
      bodyText = $$("article, .detail__body-text, body").text();
    } catch {
      bodyText = $("article, .detail__body-text, body").text();
    }
  } else {
    bodyText = $("article, .detail__body-text, body").text();
  }

  bodyText = bodyText.replace(/\u00A0/g, " ").replace(/\s+\n/g, "\n").trim();
  const region = guessRegion(`${headline}\n${bodyText}`, "Bandung");

  // -------------- KUNCI PERBAIKAN: window 3-baris --------------
  const lines = bodyText.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const blocks: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    const a = lines[i];
    const b = lines[i + 1] || "";
    const c = lines[i + 2] || "";
    // gabungkan untuk menangkap pola "Beras Medium" (a) + "Rp..." (b)
    blocks.push([a, b].join(" | "));
    blocks.push([a, b, c].join(" | "));
  }
  // plus satu blok utuh (untuk artikel yang menulis dalam paragraf)
  blocks.push(bodyText);

  const items: Item[] = [];

  for (const block of blocks) {
    if (!/(beras|gabah)/i.test(block)) continue;
    if (!RE_RP.test(block)) continue; // harus ada rupiah

    const commodity = classifyCommodity(block);
    const ctx = classifyContext(block);
    const price = parsePrice(block);
    if (!price) continue;

    items.push({
      source: "detik",
      url,
      date_published: published || "",
      region_text: region,
      commodity,
      price_value: price.value,
      price_unit: (price.unit === "kg" ? "Rp/kg" : "Rp/ltr"),
      context_type: ctx,
      raw_text: block,
      headline,
    });
  }

  // Simpan hanya Bandung / Jabar (artikel bandung jelas mengandung kata ini)  :contentReference[oaicite:5]{index=5}
  const scoped = items.filter(it =>
    /bandung|jawa barat/i.test(`${it.region_text} ${headline} ${bodyText}`)
  );

  // Filter by SINCE (jika disediakan)
  const final = scoped.filter(it =>
    !SINCE_DJ || (it.date_published && dayjs(it.date_published).isAfter(SINCE_DJ))
  );

  // Dedup by (url|commodity|value)
  const seen = new Set<string>();
  return final.filter(it => {
    const k = `${it.url}|${it.commodity}|${it.price_value}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

// ------------------- Main -------------------
(async function main() {
  // Seed from tags
  const seedFromTags = (await Promise.all(DETIK_TAGS.map(u => seedDetikFromTag(u, PAGES)))).flat();

  // Fallback list (ambil judul yang relevan)
  const seedFromListing = await seedDetikJabarListing(1);

  const urls = unique([...seedFromTags, ...seedFromListing]);
  console.log(`Seeded ${urls.length} detik URLs`);

  const outStream = fs.createWriteStream(OUT, { flags: "w", encoding: "utf8" });
  let total = 0;

  for (const u of urls) {
    try {
      const items = await parseDetikArticle(u);
      if (items.length) {
        for (const it of items) {
          outStream.write(JSON.stringify(it) + "\n");
          total++;
        }
        console.log(`+ ${items.length} from ${u}`);
      } else {
        console.log(`- 0 from ${u}`);
      }
      await sleep(150);
    } catch (e: any) {
      console.warn(`! fail ${u}: ${e?.message || e}`);
    }
  }

  outStream.end();
  console.log(`DONE. Wrote ${total} rows -> ${OUT}`);
})().catch(err => {
  console.error(err);
  process.exit(1);
});
