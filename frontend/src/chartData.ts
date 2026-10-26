// The data of a ```chart block, shared by the chart drawing and by copying the answer as plain text
export type ChartSpec = {
  type: "bar" | "line" | "pie";
  title: string;
  labels: string[];
  series: { name: string; values: (number | null)[] }[];
  unit: string;
};

const MAX_LABELS = 50;
const MAX_SERIES = 5;
const PREFIX_UNITS = new Set(["rp", "$", "us$", "€", "£", "¥", "rm", "s$"]);
export const fullNumber = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 });
export const shortNumber = new Intl.NumberFormat("id-ID", { notation: "compact", maximumFractionDigits: 1 });

// Reads the JSON inside a ```chart block; anything that cannot be drawn safely returns null
export function parseChart(source: string): ChartSpec | null {
  let raw: unknown;
  try {
    raw = JSON.parse(source);
  } catch {
    return null;
  }
  if (typeof raw !== "object" || raw === null) return null;
  const data = raw as Record<string, unknown>;
  if (!Array.isArray(data.labels) || !Array.isArray(data.series)) return null;

  const labels = data.labels.slice(0, MAX_LABELS).map((label) => String(label));
  const series = data.series
    .slice(0, MAX_SERIES)
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null && Array.isArray(item.values))
    .map((item, index) => ({
      name: typeof item.name === "string" && item.name !== "" ? item.name : `Data ${index + 1}`,
      values: labels.map((_, i) => {
        const value = (item.values as unknown[])[i];
        const number = typeof value === "string" ? Number(value) : value;
        return typeof number === "number" && Number.isFinite(number) ? number : null;
      }),
    }));
  if (labels.length === 0 || !series.some((item) => item.values.some((value) => value !== null))) return null;

  let type: ChartSpec["type"] = data.type === "line" || data.type === "pie" ? data.type : "bar";
  // a pie needs one series of positive parts; anything else is drawn as bars
  if (type === "pie" && (series.length > 1 || series[0].values.some((value) => value !== null && value < 0))) type = "bar";
  return {
    type,
    title: typeof data.title === "string" ? data.title : "",
    labels,
    series,
    unit: typeof data.unit === "string" ? data.unit.trim() : "",
  };
}

export function formatValue(value: number | null, unit: string, short = false): string {
  if (value === null) return "-";
  const number = (short ? shortNumber : fullNumber).format(value);
  if (unit === "") return number;
  if (PREFIX_UNITS.has(unit.toLowerCase())) return `${unit}${number}`;
  return unit === "%" ? `${number}%` : `${number} ${unit}`;
}