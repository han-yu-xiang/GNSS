import fs from "node:fs/promises";
import crypto from "node:crypto";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const sharp = require("C:/Users/Jing_/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp");

const PROJECT_ROOT = "E:/GNSS_Multipath_Project";
const R3_DIR = path.join(
  PROJECT_ROOT,
  "dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3",
);
const DEFAULT_OUTPUT_DIR = path.join(
  PROJECT_ROOT,
  "dataset_generation_logs/channel_modeling/phase1_ppt_figures_20260831",
);
const OUTPUT_DIR = process.argv[2] || DEFAULT_OUTPUT_DIR;

const COLORS = {
  navy: "#0B1F33",
  ink: "#132333",
  muted: "#5D6B78",
  grid: "#D6E0E8",
  teal: "#0D8090",
  orange: "#E07A3F",
  white: "#FFFFFF",
};

const CONFIGS = [
  {
    key: "delay",
    field: "excess_delay_samples",
    title: "多径时延",
    xLabel: "多径时延 / samples",
    familyLabel: "对数正态",
    family: "lognormal",
    color: COLORS.teal,
    lineColor: COLORS.orange,
    edges: makeEdges(1.0, 4.4, 18),
  },
  {
    key: "doppler",
    field: "doppler_offset_hz",
    title: "相对多普勒",
    xLabel: "相对多普勒 / Hz",
    familyLabel: "正态",
    family: "normal",
    color: COLORS.teal,
    lineColor: COLORS.orange,
    edges: makeEdges(-150, 150, 17),
  },
  {
    key: "power",
    field: "relative_power_db",
    title: "相对功率",
    xLabel: "相对功率 / dB",
    familyLabel: "正态",
    family: "normal",
    color: COLORS.teal,
    lineColor: COLORS.orange,
    edges: makeEdges(-24, 4, 15),
  },
];

function makeEdges(start, end, count) {
  const step = (end - start) / count;
  return Array.from({ length: count + 1 }, (_, index) => start + index * step);
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        cell += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(cell);
      cell = "";
    } else if (char === "\n") {
      row.push(cell.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if (cell.length > 0 || row.length > 0) {
    row.push(cell.replace(/\r$/, ""));
    rows.push(row);
  }
  if (rows.length === 0) return [];
  const headers = rows[0];
  return rows.slice(1).filter((values) => values.some((value) => value !== "")).map((values) => {
    const record = {};
    headers.forEach((header, index) => {
      record[header] = values[index] ?? "";
    });
    return record;
  });
}

async function readCsv(filePath) {
  return parseCsv(await fs.readFile(filePath, "utf8"));
}

async function sha256(filePath) {
  const bytes = await fs.readFile(filePath);
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

function number(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`Non-finite numeric value: ${value}`);
  return parsed;
}

function weightedHistogram(values, weights, edges) {
  const binWeights = Array.from({ length: edges.length - 1 }, () => 0);
  let totalWeight = 0;
  for (let index = 0; index < values.length; index += 1) {
    const value = values[index];
    const weight = weights[index];
    totalWeight += weight;
    let bin = edges.findIndex((edge, edgeIndex) => edgeIndex < edges.length - 1 && value >= edge && value < edges[edgeIndex + 1]);
    if (value === edges[edges.length - 1]) bin = binWeights.length - 1;
    if (bin >= 0 && bin < binWeights.length) binWeights[bin] += weight;
  }
  const densities = binWeights.map((weight, index) => weight / (totalWeight * (edges[index + 1] - edges[index])));
  return { densities, totalWeight };
}

function evaluatePdf(family, params, x) {
  if (family === "lognormal") {
    const loc = number(params.loc);
    const scale = number(params.scale);
    const shape = number(params.shape);
    if (x <= loc || scale <= 0 || shape <= 0) return 0;
    const z = Math.log((x - loc) / scale) / shape;
    return Math.exp(-0.5 * z * z) / ((x - loc) * shape * Math.sqrt(2 * Math.PI));
  }
  const loc = number(params.loc);
  const scale = number(params.scale);
  if (scale <= 0) return 0;
  const z = (x - loc) / scale;
  return Math.exp(-0.5 * z * z) / (scale * Math.sqrt(2 * Math.PI));
}

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function formatTick(value, key) {
  if (key === "delay") return value.toFixed(1);
  if (key === "power") return value.toFixed(0);
  return value.toFixed(0);
}

function niceTicks(start, end, count = 5) {
  return Array.from({ length: count + 1 }, (_, index) => start + ((end - start) * index) / count);
}

function pathFromPoints(points) {
  return points.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
}

function createSvg(config, values, weights, fitParameters) {
  const width = 1600;
  const height = 360;
  const chart = { left: 90, top: 92, right: 1545, bottom: 258 };
  const { densities, totalWeight } = weightedHistogram(values, weights, config.edges);
  const curveSamples = 240;
  const curve = Array.from({ length: curveSamples }, (_, index) => {
    const x = config.edges[0] + ((config.edges[config.edges.length - 1] - config.edges[0]) * index) / (curveSamples - 1);
    return { x, y: evaluatePdf(config.family, fitParameters, x) };
  });
  const maxDensity = Math.max(...densities, ...curve.map((point) => point.y), 1e-6);
  const yMax = maxDensity * 1.18;
  const xMin = config.edges[0];
  const xMax = config.edges[config.edges.length - 1];
  const xToPx = (x) => chart.left + ((x - xMin) / (xMax - xMin)) * (chart.right - chart.left);
  const yToPx = (y) => chart.bottom - (y / yMax) * (chart.bottom - chart.top);
  const yTicks = niceTicks(0, yMax, 3);
  const xTicks = niceTicks(xMin, xMax, 5);

  const gridLines = yTicks.map((tick) => {
    const y = yToPx(tick);
    return `<line x1="${chart.left}" y1="${y.toFixed(2)}" x2="${chart.right}" y2="${y.toFixed(2)}" stroke="${COLORS.grid}" stroke-width="2"/>`;
  }).join("");
  const yLabels = yTicks.map((tick) => {
    const y = yToPx(tick) + 8;
    return `<text x="${chart.left - 18}" y="${y.toFixed(2)}" text-anchor="end" class="tick">${escapeXml(tick.toFixed(2))}</text>`;
  }).join("");
  const xLabels = xTicks.map((tick) => {
    const x = xToPx(tick);
    return `<line x1="${x.toFixed(2)}" y1="${chart.bottom}" x2="${x.toFixed(2)}" y2="${chart.bottom + 7}" stroke="${COLORS.navy}" stroke-width="2"/><text x="${x.toFixed(2)}" y="${chart.bottom + 29}" text-anchor="middle" class="tick">${escapeXml(formatTick(tick, config.key))}</text>`;
  }).join("");
  const bars = densities.map((density, index) => {
    const x = xToPx(config.edges[index]) + 2;
    const x2 = xToPx(config.edges[index + 1]) - 2;
    const y = yToPx(density);
    return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${Math.max(1, x2 - x).toFixed(2)}" height="${(chart.bottom - y).toFixed(2)}" rx="3" fill="${config.color}" opacity="0.72"/>`;
  }).join("");
  const curvePath = pathFromPoints(curve.map((point) => [xToPx(point.x), yToPx(point.y)]));
  const summary = `Stage3 全部有效观测 · n=${values.length} · 权重总和=${totalWeight.toFixed(0)}`;
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <style>
    text { font-family: "Microsoft YaHei", "微软雅黑", Arial, sans-serif; }
    .title { font-size: 52px; font-weight: 700; fill: ${COLORS.navy}; }
    .sub { font-size: 28px; fill: ${COLORS.muted}; }
    .tick { font-size: 27px; fill: ${COLORS.muted}; }
    .label { font-size: 32px; fill: ${COLORS.ink}; }
    .legend { font-size: 24px; fill: ${COLORS.ink}; }
  </style>
  <rect width="${width}" height="${height}" fill="${COLORS.white}"/>
  <text x="30" y="54" class="title">${escapeXml(`${config.title} · ${config.familyLabel}`)}</text>
  <text x="30" y="80" class="sub">${escapeXml(summary)}</text>
  <line x1="${chart.left}" y1="${chart.top}" x2="${chart.left}" y2="${chart.bottom}" stroke="${COLORS.navy}" stroke-width="3"/>
  <line x1="${chart.left}" y1="${chart.bottom}" x2="${chart.right}" y2="${chart.bottom}" stroke="${COLORS.navy}" stroke-width="3"/>
  ${gridLines}
  ${yLabels}
  ${xLabels}
  ${bars}
  <path d="${curvePath}" fill="none" stroke="${config.lineColor}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="${chart.right - 420}" y="44" width="18" height="18" rx="3" fill="${config.color}" opacity="0.72"/>
  <text x="${chart.right - 394}" y="62" class="legend">加权观测</text>
  <line x1="${chart.right - 238}" y1="53" x2="${chart.right - 198}" y2="53" stroke="${config.lineColor}" stroke-width="6" stroke-linecap="round"/>
  <text x="${chart.right - 187}" y="62" class="legend">拟合曲线</text>
  <text x="${(chart.left + chart.right) / 2}" y="346" text-anchor="middle" class="label">${escapeXml(config.xLabel)}</text>
</svg>`;
}

async function main() {
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const populationPath = path.join(R3_DIR, "source_population_audit.csv");
  const marginalPath = path.join(R3_DIR, "selected_marginal_models.csv");
  const population = (await readCsv(populationPath)).filter((row) => row.academic_eligible === "True" && row.persistence_pass === "1");
  if (population.length !== 783) throw new Error(`Expected 783 eligible persistent observations, got ${population.length}`);
  const marginalRows = await readCsv(marginalPath);
  const fitParameters = {};
  for (const config of CONFIGS) {
    const row = marginalRows.find((candidate) => candidate.scope === "global" && candidate.parameter === config.field);
    if (!row) throw new Error(`Missing global marginal model for ${config.field}`);
    if (row.family !== config.family) throw new Error(`Unexpected stored family for ${config.field}: ${row.family}`);
    fitParameters[config.key] = JSON.parse(row.fit_parameters_json);
  }

  const outputs = [];
  for (const config of CONFIGS) {
    const values = population.map((row) => number(row[config.field]));
    const weights = population.map((row) => number(row.track_weight));
    const svg = createSvg(config, values, weights, fitParameters[config.key]);
    const svgPath = path.join(OUTPUT_DIR, `${config.key}_fit_curve.svg`);
    const pngPath = path.join(OUTPUT_DIR, `${config.key}_fit_curve.png`);
    await fs.writeFile(svgPath, svg, "utf8");
    await sharp(Buffer.from(svg)).png().toFile(pngPath);
    outputs.push({
      key: config.key,
      png: pngPath,
      svg: svgPath,
      family: config.family,
      fit_parameters: fitParameters[config.key],
      observation_count: values.length,
      weight_sum: weights.reduce((sum, value) => sum + value, 0),
    });
  }

  const provenance = {
    purpose: "Phase-1 interview PPT fit-curve figures; read-only derived visuals",
    generated_utc: new Date().toISOString(),
    no_refit: true,
    no_matlab_sage_raw_iq: true,
    population_filter: "academic_eligible=True and persistence_pass=1",
    weighting: "track_weight from r3 source_population_audit.csv",
    histogram: "weighted density from r3 Stage3 source population",
    fit_curve: "evaluated from stored global fit_parameters_json in r3 selected_marginal_models.csv",
    source_files: {
      population_audit: { path: populationPath, sha256: await sha256(populationPath) },
      selected_marginal_models: { path: marginalPath, sha256: await sha256(marginalPath) },
    },
    outputs,
  };
  await fs.writeFile(path.join(OUTPUT_DIR, "plot_provenance.json"), JSON.stringify(provenance, null, 2), "utf8");
  console.log(JSON.stringify(provenance, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
