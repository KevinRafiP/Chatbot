import { useEffect, useState } from "react";
import { ApiError, getPerformanceTrend, type PerformanceRange, type PerformanceTrend, type TrendPoint } from "./api";
import { ChartFigure } from "./Chart";
import type { ChartSpec } from "./chartData";

const PROFILE_LABELS: Record<string, string> = { tamu: "Tamu", cepat: "Cepat", mendalam: "Mendalam" };

// An hour reads as its clock time, a day as its date; both in the browser's time zone like the server buckets
function pointLabel(time: string, unit: PerformanceTrend["unit"]): string {
  const date = new Date(time);
  if (unit === "jam") {
    return date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("id-ID", { day: "numeric", month: "short" });
}

function seconds(ms: number): number {
  return Math.round(ms / 100) / 10;
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  return `${date.toLocaleDateString("id-ID", { day: "numeric", month: "short" })} ${date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}`;
}

function charts(trend: PerformanceTrend): ChartSpec[] {
  const labels = trend.points.map((point) => pointLabel(point.time, trend.unit));
  const series = (name: string, value: (point: TrendPoint) => number | null) => ({ name, values: trend.points.map(value) });
  // hours or days without answers have no answer time, so the line breaks there instead of dropping to zero
  const timed = (value: (point: TrendPoint) => number) => (point: TrendPoint) => (point.count > 0 ? seconds(value(point)) : null);
  return [
    {
      type: "bar",
      title: "Jawaban",
      labels,
      series: [series("Berhasil", (point) => point.count - point.failed), series("Gagal", (point) => point.failed)],
      unit: "",
    },
    {
      type: "line",
      title: "Token",
      labels,
      series: [series("Masuk", (point) => point.tokensIn), series("Keluar", (point) => point.tokensOut)],
      unit: "",
    },
    {
      type: "line",
      title: "Waktu jawab",
      labels,
      series: [series("Rata-rata", timed((point) => point.avgMs)), series("90% di bawah", timed((point) => point.p90Ms))],
      unit: "dtk",
    },
    {
      type: "bar",
      title: "Penilaian",
      labels,
      series: [series("Suka", (point) => point.likes), series("Tidak suka", (point) => point.dislikes)],
      unit: "",
    },
  ];
}

// Admin only: the period's answers, tokens, answer time, and ratings over time, and its slowest answers
export function PerformanceTrendSection({ range, account }: { range: PerformanceRange; account: string }) {
  const [trend, setTrend] = useState<PerformanceTrend | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getPerformanceTrend(range, account)
      .then((data) => active && setTrend(data))
      .catch((err) => active && setError(err instanceof ApiError && err.message !== "" ? err.message : "Gagal memuat grafik kinerja."));
    return () => {
      active = false;
    };
  }, [range, account]);

  if (error !== "") {
    return (
      <section>
        <h3>Grafik</h3>
        <p className="form-error">{error}</p>
      </section>
    );
  }
  if (trend === null) {
    return (
      <section>
        <h3>Grafik</h3>
        <span className="skeleton trend-skeleton" role="status" aria-label="Memuat grafik kinerja" />
      </section>
    );
  }
  return (
    <>
      <section>
        <h3>Grafik {trend.unit === "jam" ? "per jam" : "per hari"}</h3>
        <div className="trend-grid">
          {charts(trend).map((spec) => (
            <ChartFigure key={spec.title} spec={spec} />
          ))}
        </div>
      </section>
      {trend.slowest.length > 0 && (
        <section>
          <h3>Paling lambat</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Waktu</th>
                  {account === "" && <th>Akun</th>}
                  <th>Profil</th>
                  <th className="num">Lama</th>
                  <th className="num">Token</th>
                  <th>Alat</th>
                </tr>
              </thead>
              <tbody>
                {trend.slowest.map((entry, index) => (
                  <tr key={`${entry.createdAt}-${index}`}>
                    <td>{formatTime(entry.createdAt)}</td>
                    {account === "" && (
                      <td className="account-name">{entry.account === "tamu" ? "Tamu" : entry.accountName || "Tanpa akun"}</td>
                    )}
                    <td>{PROFILE_LABELS[entry.profile] ?? entry.profile}</td>
                    <td className="num">{seconds(entry.durationMs).toLocaleString("id-ID")} dtk</td>
                    <td className="num">{(entry.tokensIn + entry.tokensOut).toLocaleString("id-ID")}</td>
                    <td className="tools">{entry.tools.length > 0 ? entry.tools.join(", ") : "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
