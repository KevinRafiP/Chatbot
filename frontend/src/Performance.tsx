import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ApiError,
  getPerformance,
  getPerformanceRecent,
  type DislikedAnswer,
  type PerformanceAccount,
  type PerformanceRange,
  type PerformanceRecentPage,
  type PerformanceReport,
  type PerformanceStats,
  type RatingStats,
} from "./api";
import { Markdown } from "./Markdown";
import { plainMarkdown } from "./markdownPlain";
import { Pagination } from "./Pagination";

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

// A YYYY-MM-DD date in the browser's time zone, daysAgo days before today
function localDate(daysAgo = 0): string {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function rangeKey(range: PerformanceRange, account: string): string {
  return `${"days" in range ? `days-${range.days}` : `${range.from}-${range.to}`}-${account}`;
}

// All guests share one row, and logs from before accounts were recorded (or from deleted accounts) share another
function accountLabel(key: string, name: string): string {
  if (key === "tamu") return "Tamu";
  if (key === "lain") return "Tanpa akun";
  return name || "(tanpa nama)";
}

// Admin only: how fast the AI answers, how many tokens it uses, which tools it calls, and how users rate the answers.
// The performance log stores no question or answer text; disliked answers are read from the users' conversations
export function PerformancePanel() {
  const [range, setRange] = useState<PerformanceRange>({ days: 7 });
  // "" shows every account; otherwise the key of one account from the "Per akun" table
  const [account, setAccount] = useState("");
  const top = useRef<HTMLDivElement>(null);
  const [picking, setPicking] = useState(false);
  const [from, setFrom] = useState(() => localDate(6));
  const [to, setTo] = useState(() => localDate());
  const [report, setReport] = useState<{ key: string; range: PerformanceRange; data: PerformanceReport } | null>(null);
  const [error, setError] = useState("");
  // the old report stays on screen, dimmed, while another period or account loads
  const loading = error === "" && report !== null && report.key !== rangeKey(range, account);

  useEffect(() => {
    let active = true;
    const key = rangeKey(range, account);
    getPerformance(range, account)
      .then((result) => active && setReport({ key, range, data: result }))
      .catch((err) => active && setError(errorText(err, "Gagal memuat kinerja.")));
    return () => {
      active = false;
    };
  }, [range, account]);

  // the account table sits low on the page, so the view moves up to the numbers of the chosen account
  function chooseAccount(next: string) {
    setError("");
    setAccount(next);
    top.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function choosePeriod(next: number) {
    setError("");
    setPicking(false);
    setRange({ days: next });
  }

  function applyDates(event: FormEvent) {
    event.preventDefault();
    if (from === "" || to === "" || from > to) {
      setError("Tanggal akhir harus sama dengan atau setelah tanggal awal.");
      return;
    }
    setError("");
    setRange({ from, to });
  }

  return (
    <div className="performance" ref={top}>
      <div className="period-picker" role="group" aria-label="Rentang waktu">
        {PERIODS.map((period) => (
          <button
            key={period.days}
            className={!picking && "days" in range && period.days === range.days ? "active" : ""}
            aria-pressed={!picking && "days" in range && period.days === range.days}
            onClick={() => choosePeriod(period.days)}
          >
            {period.label}
          </button>
        ))}
        <button className={picking ? "active" : ""} aria-pressed={picking} onClick={() => setPicking(true)}>
          Tanggal
        </button>
      </div>
      {picking && (
        <form className="date-range" onSubmit={applyDates}>
          <label>
            Dari
            <input type="date" value={from} max={to || localDate()} onChange={(event) => setFrom(event.target.value)} required />
          </label>
          <label>
            Sampai
            <input type="date" value={to} min={from} max={localDate()} onChange={(event) => setTo(event.target.value)} required />
          </label>
          <button type="submit" className="primary">
            Tampilkan
          </button>
        </form>
      )}
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
          <p className="period-label">{formatPeriod(report.data)}</p>
          {report.data.account !== "" && (
            <AccountFilter
              account={report.data.account}
              rows={report.data.byAccount}
              onClear={() => chooseAccount("")}
            />
          )}
          <StatTiles stats={report.data.total} />
          {report.data.total.count === 0 && report.data.byProfile.length === 0 ? (
            <p className="form-note">Belum ada jawaban di rentang waktu ini.</p>
          ) : (
            <>
              <ProfileTable rows={report.data.byProfile} />
              {report.data.tools.length > 0 && <ToolBars tools={report.data.tools} />}
            </>
          )}
          {report.data.byAccount.length > 0 && (
            // a new period starts the account list on its first page again
            <AccountTable
              key={`accounts-${rangeKey(report.range, "")}`}
              rows={report.data.byAccount}
              active={report.data.account}
              onChoose={chooseAccount}
            />
          )}
          {(report.data.total.count > 0 || report.data.byProfile.length > 0) && (
            <RecentTable key={report.key} range={report.range} account={report.data.account} />
          )}
          <RatingSection ratings={report.data.ratings} disliked={report.data.disliked} />
        </div>
      )}
      <p className="performance-note">
        Catatan kinerja menyimpan waktu, token, nama alat, dan akun yang bertanya, tanpa isi pertanyaan. Potongan jawaban yang tidak disukai diambil dari percakapan
        pengguna dan bisa dimatikan dengan KINERJA_TAMPILKAN_ISI=tidak. Catatan yang lebih lama dari KINERJA_SIMPAN_HARI sudah
        dihapus.
      </p>
    </div>
  );
}

// The dates the report covers; "to" is the exclusive end, so the last day shown is one moment before it
function formatPeriod(report: PerformanceReport): string {
  const options: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" };
  const from = new Date(report.from);
  const to = new Date(new Date(report.to).getTime() - 1);
  const start = from.toLocaleDateString("id-ID", options);
  const end = to.toLocaleDateString("id-ID", options);
  return start === end ? start : `${start} – ${end}`;
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

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError && err.message !== "" ? err.message : fallback;
}

// The newest logs, one page at a time; a page loads on its own, so moving between pages does not reload the whole report
function RecentTable({ range, account }: { range: PerformanceRange; account: string }) {
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<{ page: number; data: PerformanceRecentPage } | null>(null);
  const [error, setError] = useState("");
  // the old page stays on screen, dimmed, while the next one loads
  const loading = error === "" && result !== null && result.page !== page;

  useEffect(() => {
    let active = true;
    getPerformanceRecent(range, account, page)
      .then((data) => active && setResult({ page, data }))
      .catch((err) => active && setError(errorText(err, "Gagal memuat catatan terbaru.")));
    return () => {
      active = false;
    };
  }, [range, account, page]);

  function changePage(next: number) {
    setError("");
    setPage(next);
  }

  if (error !== "") {
    return (
      <section>
        <h3>Terbaru</h3>
        <p className="form-error">{error}</p>
      </section>
    );
  }
  if (result === null) {
    return (
      <section>
        <h3>Terbaru</h3>
        <span className="skeleton recent-skeleton" role="status" aria-label="Memuat catatan terbaru" />
      </section>
    );
  }

  const { entries, total, perPage } = result.data;
  const shownPage = result.data.page;
  const pageCount = Math.max(1, Math.ceil(total / perPage));
  const first = (shownPage - 1) * perPage + 1;
  return (
    <section className={`recent ${loading ? "loading" : ""}`} aria-busy={loading}>
      <h3>Terbaru</h3>
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
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, index) => (
              <tr key={`${entry.createdAt}-${index}`}>
                <td>{formatTime(entry.createdAt)}</td>
                {account === "" && <td className="account-name">{accountLabel(entry.account, entry.accountName)}</td>}
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
      {total > 0 && (
        <div className="recent-footer">
          <p className="form-note">
            Menampilkan {formatNumber(first)}–{formatNumber(first + entries.length - 1)} dari {formatNumber(total)} catatan
          </p>
          {pageCount > 1 && <Pagination page={shownPage} pageCount={pageCount} onChange={changePage} label="Halaman catatan terbaru" />}
        </div>
      )}
    </section>
  );
}

// Shown above the numbers while the report is filtered to one account
function AccountFilter({ account, rows, onClear }: { account: string; rows: PerformanceAccount[]; onClear: () => void }) {
  const row = rows.find((item) => item.key === account);
  return (
    <div className="account-filter">
      <span>
        Akun: <strong>{row ? accountLabel(row.key, row.name) : "akun terpilih"}</strong>
        {row?.email && <small> {row.email}</small>}
      </span>
      <button type="button" className="link-button" onClick={onClear}>
        Semua akun
      </button>
    </div>
  );
}

const ACCOUNT_PAGE_SIZE = 10;

// One row per account, the busiest first; choosing a name shows the whole report for that account only
function AccountTable({ rows, active, onChoose }: { rows: PerformanceAccount[]; active: string; onChoose: (key: string) => void }) {
  const [page, setPage] = useState(1);
  const pageCount = Math.ceil(rows.length / ACCOUNT_PAGE_SIZE);
  const shown = rows.slice((page - 1) * ACCOUNT_PAGE_SIZE, page * ACCOUNT_PAGE_SIZE);
  return (
    <section>
      <h3>Per akun</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Akun</th>
              <th className="num">Jawaban</th>
              <th className="num">Gagal</th>
              <th className="num">Rata-rata</th>
              <th className="num">Token</th>
              <th>Terakhir</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr key={row.key} className={row.key === active ? "active-row" : ""}>
                <td className="account-cell">
                  <button
                    type="button"
                    className="link-button"
                    aria-pressed={row.key === active}
                    onClick={() => onChoose(row.key === active ? "" : row.key)}
                  >
                    {accountLabel(row.key, row.name)}
                  </button>
                  {row.role === "admin" && <span className="badge">admin</span>}
                  {row.email !== "" && <small>{row.email}</small>}
                </td>
                <td className="num">{formatNumber(row.count)}</td>
                <td className="num">{formatNumber(row.failed)}</td>
                <td className="num">{formatSeconds(row.avgMs)}</td>
                <td className="num" title={`masuk ${formatNumber(row.tokensIn)}, keluar ${formatNumber(row.tokensOut)}`}>
                  {formatNumber(row.tokensIn + row.tokensOut)}
                </td>
                <td>{formatTime(row.lastAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pageCount > 1 && (
        <div className="recent-footer">
          <Pagination page={page} pageCount={pageCount} onChange={setPage} label="Halaman daftar akun" />
        </div>
      )}
    </section>
  );
}

// Likes and dislikes from users: the totals, a row per profile, and the newest disliked answers
function RatingSection({ ratings, disliked }: { ratings: RatingStats[]; disliked: DislikedAnswer[] }) {
  const [total, ...byProfile] = ratings;
  if (total === undefined) {
    return (
      <section>
        <h3>Penilaian pengguna</h3>
        <p className="form-note">Belum ada jawaban yang dinilai di rentang waktu ini.</p>
      </section>
    );
  }
  return (
    <section>
      <h3>Penilaian pengguna</h3>
      <div className="stat-grid">
        <div className="stat-tile">
          <span>Suka</span>
          <strong>{formatNumber(total.likes)}</strong>
          <small>{formatPercent(total.likes, total.likes + total.dislikes)}</small>
        </div>
        <div className="stat-tile">
          <span>Tidak suka</span>
          <strong>{formatNumber(total.dislikes)}</strong>
          <small>{formatPercent(total.dislikes, total.likes + total.dislikes)}</small>
        </div>
        {byProfile.map((row) => (
          <div key={row.profile} className="stat-tile">
            <span>{profileLabel(row.profile) || "Lainnya"}</span>
            <strong>{formatPercent(row.likes, row.likes + row.dislikes)} suka</strong>
            <small>
              {formatNumber(row.likes)} suka, {formatNumber(row.dislikes)} tidak
            </small>
          </div>
        ))}
      </div>
      {disliked.length > 0 && (
        <ul className="disliked-list">
          {disliked.map((item, index) => (
            <li key={`${item.ratedAt}-${index}`}>
              <span className="disliked-meta">
                {formatTime(item.ratedAt)} · {profileLabel(item.profile) || "Lainnya"}
              </span>
              <p className="disliked-question">{item.question ? plainMarkdown(item.question) : "(pertanyaan tidak ditemukan)"}</p>
              {/* the answer is cut short, so its formatting is closed like an answer still being typed */}
              <div className="disliked-answer">
                <Markdown text={item.answer} partial />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}