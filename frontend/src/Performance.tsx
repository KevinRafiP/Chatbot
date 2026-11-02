import { useEffect, useState } from "react";
import { ApiError, getPerformance, type PerformanceEntry, type PerformanceReport, type PerformanceStats } from "./api";

const PERIODS = [
  { days: 1, label: "24 jam" },
  { days: 7, label: "7 hari" },
  { days: 30, label: "30 hari" },
];

const PROFILE_LABELS: Record<string, string> = {
  tamu: "Tamu",
  cepat: "Cepat",
  mendalam: "Mendalam",
  ringkasan: "Ringkasan percakapan",
};

function profileLabel(profile: string): string {
  return PROFILE_LABELS[profile] ?? profile;
}

function formatNumber(value: number): string {
  return value.toLocaleString("id-ID");
}

function formatSeconds(ms: number): string {
  return `${(ms / 1000).toLocaleString("id-ID", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} dtk`;
}

function formatPercent(part: number, whole: number): string {
  return whole === 0 ? "0%" : `${Math.round((part / whole) * 100)}%`;
}

// Today's entries show only the clock time; older ones also show the date
function formatTime(iso: string): string {
  const date = new Date(iso);
  const time = date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
  if (date.toDateString() === new Date().toDateString()) {
    return time;
  }
  return `${date.toLocaleDateString("id-ID", { day: "numeric", month: "short" })} ${time}`;
}

// Admin only: how fast the AI answers, how many tokens it uses, and which tools it calls.
// The question and answer text are never stored, only these numbers
export function PerformancePanel() {
  const [days, setDays] = useState(7);
  const [report, setReport] = useState<PerformanceReport | null>(null);
  const [error, setError] = useState("");
  // the old report stays on screen, dimmed, while another period loads
  const loading = error === "" && report?.days !== days;

  useEffect(() => {
    let active = true;
    getPerformance(days)
      .then((result) => active && setReport(result))
      .catch((err) => active && setError(err instanceof ApiError && err.message !== "" ? err.message : "Gagal memuat kinerja."));
    return () => {
      active = false;
    };
  }, [days]);

  function choosePeriod(next: number) {
    setError("");
    setDays(next);
  }

  return (
    <div className="performance">
      <div className="period-picker" role="group" aria-label="Rentang waktu">
        {PERIODS.map((period) => (
          <button
            key={period.days}
            className={period.days === days ? "active" : ""}
            aria-pressed={period.days === days}
            onClick={() => choosePeriod(period.days)}
          >
            {period.label}
          </button>
        ))}
      </div>
      {error !== "" && <p className="form-error">{error}</p>}
      {error === "" && report === null && (
        <div className="stat-grid" role="status" aria-label="Memuat kinerja">
          {Array.from({ length: 6 }, (_, index) => (
            <span key={index} className="skeleton stat-skeleton" />
          ))}
        </div>
      )}
      {error === "" && report !== null && (
        <div className={`performance-body ${loading ? "loading" : ""}`} aria-busy={loading}>
          <StatTiles stats={report.total} />
          {report.total.count === 0 && report.byProfile.length === 0 ? (
            <p className="form-note">Belum ada jawaban di rentang waktu ini.</p>
          ) : (
            <>
              <ProfileTable rows={report.byProfile} />
              {report.tools.length > 0 && <ToolBars tools={report.tools} />}
              <RecentTable entries={report.recent} />
            </>
          )}
        </div>
      )}
      <p className="performance-note">Isi pertanyaan dan jawaban tidak disimpan, hanya waktu, token, dan nama alat.</p>
    </div>
  );
}

function StatTiles({ stats }: { stats: PerformanceStats }) {
  const tiles = [
    { label: "Jawaban", value: formatNumber(stats.count) },
    { label: "Gagal", value: formatNumber(stats.failed), note: formatPercent(stats.failed, stats.count) },
    { label: "Rata-rata waktu", value: formatSeconds(stats.avgMs) },
    { label: "90% selesai dalam", value: formatSeconds(stats.p90Ms) },
    { label: "Rata-rata token", value: formatNumber(stats.avgTokens), note: "per jawaban" },
    { label: "Token masuk / keluar", value: `${formatNumber(stats.tokensIn)} / ${formatNumber(stats.tokensOut)}` },
  ];
  return (
    <div className="stat-grid">
      {tiles.map((tile) => (
        <div key={tile.label} className="stat-tile">
          <span>{tile.label}</span>
          <strong>{tile.value}</strong>
          {tile.note && <small>{tile.note}</small>}
        </div>
      ))}
    </div>
  );
}

function ProfileTable({ rows }: { rows: PerformanceStats[] }) {
  return (
    <section>
      <h3>Per profil</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Profil</th>
              <th className="num">Jumlah</th>
              <th className="num">Gagal</th>
              <th className="num">Rata-rata</th>
              <th className="num">90%</th>
              <th className="num">Token/jawaban</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.profile}>
                <td>{profileLabel(row.profile)}</td>
                <td className="num">{formatNumber(row.count)}</td>
                <td className="num">{formatNumber(row.failed)}</td>
                <td className="num">{formatSeconds(row.avgMs)}</td>
                <td className="num">{formatSeconds(row.p90Ms)}</td>
                <td className="num">{formatNumber(row.avgTokens)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// One bar per tool, as long as its share of the most used tool
function ToolBars({ tools }: { tools: { name: string; count: number }[] }) {
  const most = Math.max(...tools.map((tool) => tool.count));
  return (
    <section>
      <h3>Alat paling sering dipakai</h3>
      <ul className="tool-bars">
        {tools.map((tool) => (
          <li key={tool.name}>
            <span className="tool-name">{tool.name}</span>
            <span className="bar-track" aria-hidden="true">
              <span className="bar" style={{ width: `${(tool.count / most) * 100}%` }} />
            </span>
            <span className="tool-count">{formatNumber(tool.count)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function RecentTable({ entries }: { entries: PerformanceEntry[] }) {
  return (
    <section>
      <h3>Terbaru</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Waktu</th>
              <th>Profil</th>
              <th className="num">Lama</th>
              <th className="num">Token</th>
              <th>Alat</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, index) => (
              <tr key={`${entry.createdAt}-${index}`}>
                <td>{formatTime(entry.createdAt)}</td>
                <td>{profileLabel(entry.profile)}</td>
                <td className="num">{formatSeconds(entry.durationMs)}</td>
                <td
                  className="num"
                  title={`masuk ${formatNumber(entry.tokensIn)}, keluar ${formatNumber(entry.tokensOut)}, ${entry.modelCalls}× model`}
                >
                  {formatNumber(entry.tokensIn + entry.tokensOut)}
                </td>
                <td className="tools">{entry.tools.length > 0 ? entry.tools.join(", ") : "–"}</td>
                <td className={entry.ok ? "" : "status-failed"} title={entry.error}>
                  {entry.ok ? "Berhasil" : "Gagal"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
