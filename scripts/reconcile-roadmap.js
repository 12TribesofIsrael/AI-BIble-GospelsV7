#!/usr/bin/env node
/**
 * reconcile-roadmap.js — keep the web dashboard in sync with the roadmap doc.
 *
 * Single source of truth: the "Status Board" table in docs/SAAS_ROADMAP.md.
 * This script parses that table and regenerates the `UPDATED` date + `ITEMS`
 * array inside landingpage/web/roadmap.html so the two never drift.
 *
 * Usage:
 *   node scripts/reconcile-roadmap.js          # rewrite html if out of sync
 *   node scripts/reconcile-roadmap.js --check   # exit 1 if out of sync (CI/session-end)
 *
 * Edit the markdown table ONLY. Run this to propagate to the dashboard.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const MD_PATH = path.join(ROOT, "docs", "SAAS_ROADMAP.md");
const HTML_PATH = path.join(ROOT, "landingpage", "web", "roadmap.html");

const checkOnly = process.argv.includes("--check");

// Phase a roadmap item belongs to, by its number. Mirrors the doc's phase headers.
function phaseFor(n) {
  if (n <= 3) return "Phase 1 · Quick Wins";
  if (n <= 6) return "Phase 2 · Foundation";
  if (n <= 8) return "Phase 3 · Monetization";
  return "Phase 4 · Scale & Polish";
}

// Map the Status column's emoji/word → the dashboard's status key.
function statusKey(cell) {
  const c = cell.toLowerCase();
  if (c.includes("✅") || c.includes("done")) return "done";
  if (c.includes("🟡") || c.includes("partial")) return "partial";
  if (c.includes("⏭️") || c.includes("skip")) return "skip";
  return "todo"; // ⬜ / "not started"
}

function parseStatusBoard(md) {
  // Grab the Status Board section (from its heading to the next "---" divider).
  const start = md.indexOf("## 📊 Status Board");
  if (start === -1) throw new Error("Could not find '## 📊 Status Board' in " + MD_PATH);
  const rest = md.slice(start);
  const end = rest.indexOf("\n---");
  const section = end === -1 ? rest : rest.slice(0, end);

  // Updated date from the heading: "## 📊 Status Board — updated 2026-06-12"
  const dateMatch = section.match(/updated\s+(\d{4}-\d{2}-\d{2})/i);
  const updated = dateMatch ? dateMatch[1] : "";

  // Table rows: | # | Item | Status | Shipped | Notes |
  const items = [];
  for (const line of section.split("\n")) {
    const t = line.trim();
    if (!t.startsWith("|")) continue;
    const cells = t.split("|").map((s) => s.trim());
    // cells[0] is "" (before first pipe). Data cols: 1=#, 2=Item, 3=Status, 4=Shipped, 5=Notes
    const n = parseInt(cells[1], 10);
    if (!Number.isInteger(n)) continue; // skips header + separator rows
    items.push({
      n,
      phase: phaseFor(n),
      title: cells[2],
      status: statusKey(cells[3]),
      ship: cells[4] === "—" || cells[4] === "-" ? "" : cells[4],
      note: cells[5],
      blocker: /blocker/i.test(cells[5]),
    });
  }
  if (!items.length) throw new Error("Parsed 0 rows from the Status Board table — check the table format.");
  return { updated, items };
}

// The dashboard renders notes as plain text, so strip markdown emphasis/code
// markers (**bold**, `code`) that would otherwise show as literal characters.
function mdToText(s) {
  return String(s)
    .replace(/\*\*/g, "")
    .replace(/`/g, "")
    .trim();
}

function buildItemsLiteral(items) {
  const esc = (s) => mdToText(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  const lines = items.map((i) => {
    const fields = [
      `n: ${i.n}`,
      `phase: "${esc(i.phase)}"`,
      `title: "${esc(i.title)}"`,
      `status: "${i.status}"`,
      `ship: "${esc(i.ship)}"`,
      `note: "${esc(i.note)}"`,
    ];
    if (i.blocker) fields.push("blocker: true");
    return `  { ${fields.join(", ")} },`;
  });
  return "const ITEMS = [\n" + lines.join("\n") + "\n];";
}

function main() {
  const md = fs.readFileSync(MD_PATH, "utf8");
  const { updated, items } = parseStatusBoard(md);

  const html = fs.readFileSync(HTML_PATH, "utf8");
  const newUpdated = `const UPDATED = "${updated}";`;
  const newItems = buildItemsLiteral(items);

  let out = html
    .replace(/const UPDATED = "[^"]*";/, newUpdated)
    .replace(/const ITEMS = \[[\s\S]*?\n\];/, newItems);

  if (out === html) {
    console.log("✓ Roadmap dashboard already in sync (" + items.length + " items, updated " + updated + ").");
    process.exit(0);
  }

  if (checkOnly) {
    console.error("✗ Roadmap dashboard is OUT OF SYNC with docs/SAAS_ROADMAP.md.");
    console.error("  Run: node scripts/reconcile-roadmap.js");
    process.exit(1);
  }

  fs.writeFileSync(HTML_PATH, out, "utf8");
  console.log("✓ Regenerated roadmap.html from the Status Board (" + items.length + " items, updated " + updated + ").");
}

main();
