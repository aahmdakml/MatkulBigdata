import "dotenv/config";
import express from "express";
import cors from "cors";

import ingestRoute from "./routes/ingest.js";
import analyzeRoute from "./routes/sentiment.js"; // ⬅️ baru

const app = express();
app.use(cors());
app.use(express.json({ limit: "25mb" }));
app.use(express.urlencoded({ extended: true, limit: "25mb" }));

app.use("/api", ingestRoute);
app.use("/api", analyzeRoute); // ⬅️ daftar

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`✅ Backend: http://localhost:${PORT}`));
