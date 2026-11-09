// Cloudflare Turnstile proves a real browser before the backend checks a login, so bots cannot guess passwords.
// An empty VITE_TURNSTILE_SITE_KEY turns it off: getCaptchaToken returns null and no header is sent
const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY ?? "";
const SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
const WAIT_MS = 60_000;
const FAILED = "Verifikasi keamanan gagal. Muat ulang halaman lalu coba lagi.";

type TurnstileApi = {
  render: (container: HTMLElement, options: Record<string, unknown>) => string;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let scriptPromise: Promise<TurnstileApi> | null = null;

// Loads the Turnstile script once; a failed load can be tried again on the next call
function loadScript(): Promise<TurnstileApi> {
  scriptPromise ??= new Promise<TurnstileApi>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new Error(FAILED)));
    script.onerror = () => {
      script.remove();
      scriptPromise = null;
      reject(new Error(`${FAILED} (script Cloudflare tidak termuat)`));
    };
    document.head.appendChild(script);
  });
  return scriptPromise;
}

// Returns a fresh one-time token, or null when the captcha is off.
// The widget stays hidden unless Cloudflare wants the visitor to click it
export async function getCaptchaToken(): Promise<string | null> {
  if (SITE_KEY === "") {
    return null;
  }
  const turnstile = await loadScript();
  const box = document.createElement("div");
  box.className = "captcha-box";
  document.body.appendChild(box);
  let widgetId = "";
  try {
    return await new Promise<string>((resolve, reject) => {
      const fail = (reason: string) => () => reject(new Error(`${FAILED} (${reason})`));
      const timer = setTimeout(fail("waktu habis"), WAIT_MS);
      const stop = (done: () => void) => () => {
        clearTimeout(timer);
        done();
      };
      widgetId = turnstile.render(box, {
        sitekey: SITE_KEY,
        appearance: "interaction-only",
        callback: (value: string) => stop(() => resolve(value))(),
        "error-callback": (code: string) => stop(fail(`kode ${code}`))(),
        "expired-callback": stop(fail("kedaluwarsa")),
        "timeout-callback": stop(fail("waktu habis")),
      });
    });
  } finally {
    if (widgetId !== "") {
      turnstile.remove(widgetId);
    }
    box.remove();
  }
}
