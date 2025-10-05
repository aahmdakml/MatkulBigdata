// scripts/scrape_arimbi_today.ts
import { chromium } from "playwright";
import dayjs from "dayjs";
import fs from "fs/promises";
import path from "path";

type Row = {
  source: "arimbi";
  url: string;
  region_text: "Kabupaten Bandung";
  date: string;                 // YYYY-MM-DD
  commodity: "Beras Medium" | "Beras Premium";
  price_value: number;          // Rp/kg
  price_unit: "Rp/kg";
};

const PAGE_URL = "https://arimbi.bandung.go.id/market"; // Halaman market menampilkan Beras Medium/Premium dgn harga. :contentReference[oaicite:6]{index=6}
const TODAY = dayjs().format("YYYY-MM-DD");

function parsePrice(s: string): number {
  const m = s.match(/(\d{1,3}(?:[.,]\d{3})+)/);
  return m ? parseInt(m[1].replace(/[^\d]/g, ""), 10) : 0;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(60_000);

  await page.goto(PAGE_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(800);

  const body = await page.evaluate(() => document.body.innerText || "");
  const out: Row[] = [];

  const premium = body.match(/Beras\s*Premium.*?Rp\s*[\d\.,]+/i);
  const medium  = body.match(/Beras\s*Medium.*?Rp\s*[\d\.,]+/i);

  if (premium) {
    out.push({
      source: "arimbi",
      url: PAGE_URL,
      region_text: "Kabupaten Bandung",
      date: TODAY,
      commodity: "Beras Premium",
      price_value: parsePrice(premium[0]),
      price_unit: "Rp/kg",
    });
  }
  if (medium) {
    out.push({
      source: "arimbi",
      url: PAGE_URL,
      region_text: "Kabupaten Bandung",
      date: TODAY,
      commodity: "Beras Medium",
      price_value: parsePrice(medium[0]),
      price_unit: "Rp/kg",
    });
  }

  await fs.mkdir("data", { recursive: true });
  await fs.writeFile(path.join("data", `arimbi_${TODAY}.json`), JSON.stringify(out, null, 2), "utf8");
  console.log(`ARIMBI ${TODAY} -> ${out.length} rows`);

  await browser.close();
})();
