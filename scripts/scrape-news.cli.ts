#!/usr/bin/env ts-node
/**
 * Scraper CLI – berita harga beras/gabah (Bandung/Jawa Barat)
 * - Seed: detik tags/listing Bandung (harga beras, daftar harga sembako)
 * - Fetch: artikel/AMP
 * - Parse: tarik harga Rp/kg utk Beras Medium/Premium (+ gabah bila ada)
 * - Output: NDJSON (1 item per harga-komoditas)
 *
 * Sumber & pola:
 * - detikJabar "Daftar Harga Sembako di Kota Bandung ..." memuat baris "Beras Medium / Beras Premium Rp ... / kg" :contentReference[oaicite:4]{index=4}
 * - Tag "harga beras di bandung" untuk seed URL :contentReference[oaicite:5]{index=5}
 * - HET referensi (normalisasi downstream): CNBC update 26 Aug 2025 (Medium zona Jawa 13.500), sebelumnya 12.500 nasional. :contentReference[oaicite:6]{index=6}
 */

import fs from "fs";
import path from "path";
import axios from "axios";
import * as cheerio from "cheerio";
import dayjs from "dayjs";
import pLimit from "p-limit";

// ------------------- CLI args -------------------
const args = process.argv.slice(2);
function getArg(name: string, def?: string) {
  const ix = args.findIndex(a => a === `--${name}`);
  if (ix >= 0 && args[ix + 1]) return args[ix + 1];
  const eq = args.find(a => a.startsWith(`--${name}=`));
  if (eq) return eq.split("=")[1];
  return def;
}
const OUT = getArg("out", "data/news_bandung.ndjson")!;
const PAGES = parseInt(getArg("pages", "3")!, 10);
const SINCE = getArg("since", ""); // ISO date (optional)
const SINCE_DJ = SINCE ? dayjs(SINCE) : null;

fs.mkdirSync(path.dirname(OUT), { recursive: true });

// ------------------- Constants -------------------
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36";

const DETIK_TAGS = [
  "https://www.detik.com/tag/harga-beras-di-bandung",           // :contentReference[oaicite:7]{index=7}
  "https://www.detik.com/tag/harga-beras-di-bandung-hari-ini",  // :contentReference[oaicite:8]{index=8}
  "https://www.detik.com/jabar/berita"                           // fallback kanal jabar (filter judul/lede)
];

const REGION_KEYWORDS = [
  /kota bandung/i, /kabupaten bandung/i, /bandung/i, /jawa barat/i,
  /karawang/i, /subang/i, /indramayu/i, /cirebon/i, /garut/i, /tasikmalaya/i, /cianjur/i,
  /sukabumi/i, /bogor/i, /bekasi/i, /sumedang/i, /majalengka/i, /purwakarta/i, /kuningan/i,
  /pangandaran/i, /depok/i, /cimahi/i, /banjar/i
];

// commodity regex
const RE_BERAS_MED = /\bberas[^.\n]{0,30}medium\b/i;
const RE_BERAS_PREM = /\bberas[^.\n]{0,30}premium\b/i;
const RE_BERAS_IR64 = /\bberas[^.\n]{0,40}(ir\.?\s*64|ir64|setra ramos)\b/i;
const RE_GABAH     = /\bgabah\b|\bgkp\b|\bgkg\b/i;

const RE_RP = /(?:Rp|IDR)\s*([0-9]{1,3}(?:[.,][0-9]{3})+)/i;
const RE_UNIT_NEAR = /(kg|kilogram|ltr|liter)/i;

// ------------------- Helpers -------------------
const sleep = (ms:number)=>new Promise(r=>setTimeout(r,ms));

async function fetchHtml(url: string): Promise<string> {
  const { data } = await axios.get(url, { headers: { "User-Agent": UA }, timeout: 20000 });
  return data as string;
}

function absoluteUrl(base: string, href?: string) {
  try {
    if (!href) return "";
    return new URL(href, base).toString();
  } catch { return href || ""; }
}

function unique<T>(arr: T[]) { return Array.from(new Set(arr)); }

function parseDate($: cheerio.CheerioAPI): string {
  const ogTime = $('meta[property="article:published_time"]').attr("content")
             || $('meta[itemprop="datePublished"]').attr("content")
             || $("time").attr("datetime") || "";
  return ogTime;
}

function guessRegion(text: string, fallback = "Bandung"): string {
  // try "Bandung - " lede
  const m = text.match(/^\s*([A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ\s\.]+)\s*-\s*/m);
  if (m) return m[1];
  // keyword pass
  for (const re of REGION_KEYWORDS) {
    if (re.test(text)) {
      const hit = (text.match(re) || [""])[0];
      if (/jawa barat/i.test(hit)) return "Jawa Barat";
      if (/bandung/i.test(hit))    return /kota bandung/i.test(text) ? "Kota Bandung" : (/kabupaten bandung/i.test(text) ? "Kabupaten Bandung" : "Bandung");
      return hit.replace(/\b(kota|kabupaten)\b/ig,"").trim();
    }
  }
  return fallback;
}

function parsePrice(line: string): { value: number, unit: string } | null {
  const m = line.match(RE_RP);
  if (!m) return null;
  const value = parseInt(m[1].replace(/[^\d]/g, ""), 10);
  // cari unit dekat angka
  const near = line.slice(Math.max(0, (m.index||0)-30), Math.min(line.length, (m.index||0)+m[0].length+30));
  const u = near.match(RE_UNIT_NEAR)?.[1] || "kg";
  return { value, unit: u.toLowerCase().startsWith("l") ? "ltr" : "kg" };
}

// ------------------- Detik seeding -------------------
async function seedDetikFromTag(tagUrl: string, pages=3): Promise<string[]> {
  const urls: string[] = [];
  for (let p = 1; p <= pages; p++) {
    const pageUrl = `${tagUrl}?page=${p}`;
    const html = await fetchHtml(pageUrl);
    const $ = cheerio.load(html);
    $("a[href*='/d-']").each((_, a) => {
      const href = $(a).attr("href");
      if (href && /\/d-\d+/.test(href)) urls.push(absoluteUrl(pageUrl, href.split("?")[0]));
    });
    await sleep(400); // rate-limit
  }
  return unique(urls);
}

async function seedDetikFallbackKanal(pages=1): Promise<string[]> {
  // simple: ambil listing pertama & filter judul yang mengandung "harga beras"/"daftar harga"/"Bandung"
  const base = "https://www.detik.com/jabar/berita";
  const urls:string[]=[];
  for (let p=1;p<=pages;p++){
    const pageUrl = `${base}?page=${p}`;
    const html = await fetchHtml(pageUrl);
    const $ = cheerio.load(html);
    $("a[href*='/d-']").each((_,a)=>{
      const href = $(a).attr("href")||"";
      const title = $(a).text() || "";
      if (/harga beras|daftar harga|sembako|bandung/i.test(title)) {
        urls.push(absoluteUrl(pageUrl, href.split("?")[0]));
      }
    });
    await sleep(400);
  }
  return unique(urls);
}

// ------------------- Detik parser -------------------
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

async function parseDetikArticle(url: string): Promise<Item[]> {
  // ------------------- Detik parser (REVISI) -------------------
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

async function parseDetikArticle(url: string): Promise<Item[]> {
  const html = await fetchHtml(url);
  const $ = cheerio.load(html);

  const headline = $("h1").first().text().trim();
  let time = parseDate($);

  // coba AMP karena struktur lebih bersih
  const ampHref = $('link[rel="amphtml"]').attr("href");
  let bodyText = "";
  if (ampHref) {
    try {
      const amp = await fetchHtml(absoluteUrl(url, ampHref));
      const $$ = cheerio.load(amp);
      bodyText = $$("article, .detail__body-text, body").text();
    } catch {
      bodyText = $("article, .detail__body-text, body").text();
    }
  } else {
    bodyText = $("article, .detail__body-text, body").text();
  }
  bodyText = bodyText.replace(/\u00A0/g, " ").replace(/\s+\n/g, "\n").trim();

  const region = guessRegion(`${headline}\n${bodyText}`, "Bandung");

  // ====== REVISI: pasangan baris (komoditas -> harga di baris berikutnya) ======
  const rawLines = bodyText.split(/\r?\n/).map(s => s.trim()).filter(Boolean);

  // normalisasi: gabung baris bullet yang terlalu pendek dengan baris berikutnya
  // contoh: "1. Beras Medium" + "Rp13.500 / kg" -> satu entri
  const lines: string[] = [];
  for (let i = 0; i < rawLines.length; i++) {
    const cur = rawLines[i];
    const next = rawLines[i + 1] || "";
    if (/(beras|gabah)/i.test(cur) && RE_RP.test(next)) {
      lines.push(`${cur} ${next}`);  // gabungkan agar regex harga & komoditas satu baris
      i++; // skip next
    } else {
      lines.push(cur);
    }
  }

  const items: Item[] = [];

  function pushIf(line: string, commodity: Item["commodity"], context: Item["context_type"]) {
    const p = parsePrice(line);
    if (!p) return;
    const unit = p.unit === "kg" ? "Rp/kg" : "Rp/ltr";
    items.push({
      source: "detik",
      url,
      date_published: time || "",
      region_text: region,
      commodity,
      price_value: p.value,
      price_unit: unit as Item["price_unit"],
      context_type: context,
      raw_text: line,
      headline
    });
  }

  for (const line of lines) {
    const low = line.toLowerCase();
    if (!/(beras|gabah)/.test(low)) continue;

    // konteks: gabah/penggilingan => produsen; lainnya => eceran
    const context: Item["context_type"] = /gabah|gkp|gkg|penggilingan|petani/i.test(line) ? "produsen" : "eceran";

    if (RE_BERAS_MED.test(line))        pushIf(line, "Beras Medium", context);
    else if (RE_BERAS_PREM.test(line))  pushIf(line, "Beras Premium", context);
    else if (RE_BERAS_IR64.test(line))  pushIf(line, "Beras IR64", context);
    else if (RE_GABAH.test(line))       pushIf(line, "Gabah", context);
    else if (/beras/i.test(line))       pushIf(line, "Beras", context);
  }

  // filter Bandung/Jabar
  const filtered = items.filter(it =>
    /bandung|jawa barat/i.test(`${it.region_text} ${headline} ${bodyText}`)
  );

  // filter by SINCE (kalau dipakai)
  const dated = filtered.filter(it => !SINCE_DJ || (it.date_published && dayjs(it.date_published).isAfter(SINCE_DJ)));

  // dedup
  const seen = new Set<string>();
  const final = dated.filter(it => {
    const k = `${it.url}|${it.commodity}|${it.price_value}`;
    if (seen.has(k)) return false; seen.add(k); return true;
  });

  return final;
}

// ------------------- Main -------------------
(async function main(){
  const limit = pLimit(4);

  // 1) seed URLs from detik tags
  const seedLists = await Promise.all([
    ...DETIK_TAGS.map(u => seedDetikFromTag(u, PAGES)),
    seedDetikFallbackKanal(1)
  ]);
  const urls = unique(seedLists.flat());

  console.log(`Seeded ${urls.length} detik URLs`);

  // 2) crawl & parse
  const all: Item[] = [];
  await Promise.all(urls.map(u => limit(async ()=>{
    try {
      const items = await parseDetikArticle(u);
      if (items.length) {
        all.push(...items);
        console.log(`+ ${items.length} from ${u}`);
      } else {
        console.log(`- 0 from ${u}`);
      }
      await sleep(250);
    } catch (e:any) {
      console.warn(`! fail ${u}: ${e?.message||e}`);
    }
  })));

  // 3) write NDJSON
  const out = fs.createWriteStream(OUT, { flags: "w", encoding: "utf8" });
  for (const it of all) out.write(JSON.stringify(it)+"\n");
  out.end();

  console.log(`DONE. Wrote ${all.length} rows → ${OUT}`);
})().catch(err => { console.error(err); process.exit(1); });
