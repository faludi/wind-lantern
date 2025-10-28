// A simple Node.js + Express server to serve the HTML page and handle updates.

import express from "express";
import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const app = express();
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Middleware
app.use(express.json());
app.use(express.static(__dirname)); // serve index.html and settings.json

// Endpoint: update_settings
app.post("/update_settings", async (req, res) => {
  const { address } = req.body;
  if (typeof address !== "string" || !address.trim()) {
    return res.status(400).json({ error: "Invalid address" });
  }

  const jsonPath = path.join(__dirname, "settings.json");

  try {
    const data = JSON.parse(await fs.readFile(jsonPath, "utf8"));
    data.address = address.trim();
    await fs.writeFile(jsonPath, JSON.stringify(data, null, 2), "utf8");
    res.json({ success: true, message: "Address updated" });
  } catch (err) {
    console.error("Error updating settings:", err);
    res.status(500).json({ error: "Failed to update settings" });
  }
});

// Start the server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}/`);
});