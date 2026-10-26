import { useEffect, useRef, useState, type PointerEvent } from "react";
import { formatValue, fullNumber, parseChart, type ChartSpec } from "./chartData";

// series colors live in index.css (--series-1 ... --series-5), checked for color-blind safety on the chart panel
const SERIES_COLORS = [1, 2, 3, 4, 5].map((n) => `var(--series-${n})`);
const OTHER_COLOR = "var(--series-other)";

// Round tick steps (1, 2, 2.5, 5 x 10^n) so the axis reads easily
function niceTicks(min: number, max: number, count = 5): number[] {
  if (min === max) {
    max = min === 0 ? 1 : min + Math.abs(min) * 0.1;
  }
  const rough = (max - min) / count;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((n) => n * power).find((n) => n >= rough) ?? rough;
  const ticks: number[] = [];
  for (let tick = Math.floor(min / step) * step; tick <= max + step * 0.001; tick += step) {
    ticks.push(Number(tick.toPrecision(12)));
  }
  if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
  return ticks;
}

function shorten(text: string, length: number): string {
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

// A bar with a 4px rounded end away from the baseline
function barPath(x: number, base: number, end: number, width: number): string {
  const r = Math.min(4, width / 2, Math.abs(end - base));
  if (end <= base) {
    return `M${x},${base}V${end + r}Q${x},${end} ${x + r},${end}H${x + width - r}Q${x + width},${end} ${x + width},${end + r}V${base}Z`;
  }
  return `M${x},${base}V${end - r}Q${x},${end} ${x + r},${end}H${x + width - r}Q${x + width},${end} ${x + width},${end - r}V${base}Z`;
}

type Tip = { x: number; y: number; title: string; rows: { color: string; name: string; value: string }[] };

function Tooltip({ tip }: { tip: Tip }) {
  return (
    <div className="chart-tooltip" style={{ left: tip.x, top: tip.y }} role="status">
      <strong>{tip.title}</strong>
      {tip.rows.map((row) => (
        <span key={row.name}>
          <i style={{ background: row.color }} />
          {row.name}: {row.value}
        </span>
      ))}
    </div>
  );
}

function AxisChart({ spec, width }: { spec: ChartSpec; width: number }) {
  const [active, setActive] = useState<number | null>(null);
  const height = Math.round(Math.min(320, Math.max(200, width * 0.55)));
  const values = spec.series.flatMap((item) => item.values).filter((value): value is number => value !== null);
  // bars start at zero so their length is honest; a line zooms in on its range so the change is visible
  const ticks = spec.type === "bar" ? niceTicks(Math.min(0, ...values), Math.max(0, ...values)) : niceTicks(Math.min(...values), Math.max(...values));
  const low = ticks[0];
  const high = ticks[ticks.length - 1];
  const axisLabels = ticks.map((tick) => formatValue(tick, spec.unit, true));
  const left = Math.min(90, 12 + Math.max(...axisLabels.map((label) => label.length)) * 7);
  const top = 12;
  const bottom = 30;
  const plotWidth = width - left - 12;
  const plotHeight = height - top - bottom;
  const band = plotWidth / spec.labels.length;
  const y = (value: number) => top + ((high - value) / (high - low)) * plotHeight;
  const xCenter = (i: number) => left + band * (i + 0.5);
  const labelEvery = Math.ceil(spec.labels.length / Math.max(1, Math.floor(plotWidth / 70)));
  const labelLength = Math.max(4, Math.floor((band * labelEvery) / 7));

  function point(event: PointerEvent<SVGRectElement>, index: number) {
    if (event.pointerType === "touch" && active === index) {
      setActive(null);
      return;
    }
    setActive(index);
  }

  const tip: Tip | null =
    active === null
      ? null
      : {
          x: Math.min(Math.max(xCenter(active), 70), width - 70),
          y: top,
          title: spec.labels[active],
          rows: spec.series.map((item, s) => ({ color: SERIES_COLORS[s], name: item.name, value: formatValue(item.values[active], spec.unit) })),
        };

  const groupWidth = band * (spec.type === "bar" ? 0.72 : 0);
  const barWidth = Math.max(1, groupWidth / spec.series.length - (spec.series.length > 1 ? 2 : 0));

  return (
    <div className="chart-area" onPointerLeave={(event) => event.pointerType !== "touch" && setActive(null)}>
      <svg width={width} height={height} role="img" aria-label={spec.title || "Grafik"}>
        {ticks.map((tick, i) => (
          <g key={tick}>
            <line x1={left} x2={width - 12} y1={y(tick)} y2={y(tick)} className={tick === 0 || (i === 0 && low > 0) ? "chart-baseline" : "chart-grid"} />
            <text x={left - 6} y={y(tick)} dy="0.32em" textAnchor="end" className="chart-axis">
              {axisLabels[i]}
            </text>
          </g>
        ))}
        {spec.labels.map((label, i) =>
          i % labelEvery === 0 ? (
            <text key={i} x={xCenter(i)} y={height - 10} textAnchor="middle" className="chart-axis">
              {shorten(label, labelLength)}
            </text>
          ) : null,
        )}
        {active !== null && spec.type === "line" && <line x1={xCenter(active)} x2={xCenter(active)} y1={top} y2={top + plotHeight} className="chart-crosshair" />}
        {spec.type === "bar" &&
          spec.series.map((item, s) =>
            item.values.map((value, i) =>
              value === null ? null : (
                <path
                  key={`${s}-${i}`}
                  d={barPath(xCenter(i) - groupWidth / 2 + s * (barWidth + (spec.series.length > 1 ? 2 : 0)), y(0), y(value), barWidth)}
                  fill={SERIES_COLORS[s]}
                  opacity={active === null || active === i ? 1 : 0.45}
                />
              ),
            ),
          )}
        {spec.type === "line" &&
          spec.series.map((item, s) => {
            const segments: string[] = [];
            let path = "";
            item.values.forEach((value, i) => {
              if (value === null) {
                if (path) segments.push(path);
                path = "";
              } else {
                path += `${path ? "L" : "M"}${xCenter(i)},${y(value)}`;
              }
            });
            if (path) segments.push(path);
            return (
              <g key={s}>
                {segments.map((d, k) => (
                  <path key={k} d={d} fill="none" stroke={SERIES_COLORS[s]} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                ))}
                {item.values.map((value, i) =>
                  value !== null && (active === i || band >= 24) ? (
                    <circle key={i} cx={xCenter(i)} cy={y(value)} r={active === i ? 5 : 4} fill={SERIES_COLORS[s]} className="chart-dot" />
                  ) : null,
                )}
              </g>
            );
          })}
        {spec.labels.map((_, i) => (
          <rect
            key={i}
            x={left + band * i}
            y={top}
            width={band}
            height={plotHeight}
            fill="transparent"
            onPointerEnter={(event) => event.pointerType !== "touch" && setActive(i)}
            onPointerDown={(event) => point(event, i)}
          />
        ))}
      </svg>
      {tip && <Tooltip tip={tip} />}
    </div>
  );
}

function PieChart({ spec, width }: { spec: ChartSpec; width: number }) {
  const [active, setActive] = useState<number | null>(null);
  const parts = spec.labels
    .map((label, i) => ({ label, value: spec.series[0].values[i] ?? 0 }))
    .filter((part) => part.value > 0)
    .sort((a, b) => b.value - a.value);
  // past the first slices, small parts fold into "Lainnya" so every color stays distinct
  const colored = SERIES_COLORS.length;
  const slices =
    parts.length > colored
      ? [...parts.slice(0, colored), { label: "Lainnya", value: parts.slice(colored).reduce((sum, part) => sum + part.value, 0) }]
      : parts;
  const total = slices.reduce((sum, part) => sum + part.value, 0);
  const size = Math.min(220, width);
  const radius = size / 2 - 4;
  const inner = radius * 0.55;
  const color = (i: number) => SERIES_COLORS[i] ?? OTHER_COLOR;

  const starts = slices.map((_, i) => -Math.PI / 2 + (slices.slice(0, i).reduce((sum, part) => sum + part.value, 0) / total) * Math.PI * 2);
  const arcs = slices.map((part, i) => {
    const sweep = (part.value / total) * Math.PI * 2;
    const start = starts[i];
    const end = start + sweep - (slices.length === 1 ? 0.0001 : 0);
    const large = sweep > Math.PI ? 1 : 0;
    const at = (r: number, a: number) => `${size / 2 + r * Math.cos(a)},${size / 2 + r * Math.sin(a)}`;
    const d = `M${at(radius, start)}A${radius},${radius} 0 ${large} 1 ${at(radius, end)}L${at(inner, end)}A${inner},${inner} 0 ${large} 0 ${at(inner, start)}Z`;
    return { d, i, mid: (start + end) / 2 };
  });

  const tip: Tip | null =
    active === null
      ? null
      : {
          x: size / 2,
          y: size / 2 - 30,
          title: slices[active].label,
          rows: [{ color: color(active), name: `${fullNumber.format((slices[active].value / total) * 100)}%`, value: formatValue(slices[active].value, spec.unit) }],
        };

  return (
    <div className="chart-pie">
      <div className="chart-area" style={{ width: size }} onPointerLeave={(event) => event.pointerType !== "touch" && setActive(null)}>
        <svg width={size} height={size} role="img" aria-label={spec.title || "Grafik lingkaran"}>
          {arcs.map((arc) => (
            <path
              key={arc.i}
              d={arc.d}
              fill={color(arc.i)}
              className="chart-slice"
              opacity={active === null || active === arc.i ? 1 : 0.45}
              onPointerEnter={(event) => event.pointerType !== "touch" && setActive(arc.i)}
              onPointerDown={(event) => event.pointerType === "touch" && setActive(active === arc.i ? null : arc.i)}
            />
          ))}
        </svg>
        {tip && <Tooltip tip={tip} />}
      </div>
      <ul className="chart-legend vertical">
        {slices.map((part, i) => (
          <li key={part.label}>
            <i style={{ background: color(i) }} />
            {part.label} <span>{fullNumber.format((part.value / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ChartTable({ spec }: { spec: ChartSpec }) {
  return (
    <div className="md-table">
      <table>
        <thead>
          <tr>
            <th />
            {spec.series.map((item) => (
              <th key={item.name}>{item.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {spec.labels.map((label, i) => (
            <tr key={i}>
              <td>{label}</td>
              {spec.series.map((item) => (
                <td key={item.name}>{formatValue(item.values[i], spec.unit)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// A ```chart block drawn as a bar, line, or pie chart, with a table view of the same numbers
export function Chart({ source }: { source: string }) {
  const spec = parseChart(source);
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [showTable, setShowTable] = useState(false);

  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  if (spec === null) {
    return (
      <pre className="md-code">
        <code>{source}</code>
      </pre>
    );
  }
  return (
    <figure className="chart" ref={box}>
      <figcaption>
        <span>{spec.title}</span>
        <button type="button" className="chart-toggle" onClick={() => setShowTable(!showTable)}>
          {showTable ? "Grafik" : "Tabel"}
        </button>
      </figcaption>
      {spec.series.length > 1 && !showTable && (
        <ul className="chart-legend">
          {spec.series.map((item, s) => (
            <li key={item.name}>
              <i style={{ background: SERIES_COLORS[s] }} />
              {item.name}
            </li>
          ))}
        </ul>
      )}
      {showTable ? (
        <ChartTable spec={spec} />
      ) : (
        width > 0 && (spec.type === "pie" ? <PieChart spec={spec} width={width} /> : <AxisChart spec={spec} width={width} />)
      )}
    </figure>
  );
}
