// Runs Python code from the agent's jalankan_python tool with Pyodide. It lives in a worker so the page
// stays responsive, and a run that takes too long can be stopped by terminating the worker
type Pyodide = {
  globals: { get(name: string): () => PyProxy };
  loadPackagesFromImports(code: string): Promise<unknown>;
  runPythonAsync(code: string, options?: { globals?: PyProxy }): Promise<unknown>;
  setStdout(options: { batched: (text: string) => void }): void;
  setStderr(options: { batched: (text: string) => void }): void;
};
type PyProxy = { destroy(): void };
type WorkerScope = {
  location: Location;
  fetch: typeof fetch;
  postMessage(message: unknown): void;
  onmessage: ((event: MessageEvent<{ id: number; code: string }>) => void) | null;
};

const scope = self as unknown as WorkerScope;
const PYODIDE_URL = new URL(
  (import.meta.env.VITE_PYODIDE_URL || "https://cdn.jsdelivr.net/pyodide/v0.29.5/full/").replace(/\/?$/, "/"),
  scope.location.href,
).href;
const MAX_OUTPUT = 20_000;

let loading: Promise<Pyodide> | null = null;

// Python code may only download Pyodide's own packages; the page's API and other sites stay out of reach
function lockNetwork(): void {
  const allowedFetch = scope.fetch.bind(scope);
  scope.fetch = (input, init) => {
    const url = new URL(input instanceof Request ? input.url : String(input), scope.location.href);
    return url.href.startsWith(PYODIDE_URL)
      ? allowedFetch(input, init)
      : Promise.reject(new TypeError("Network access is disabled for Python code"));
  };
  for (const name of ["XMLHttpRequest", "WebSocket", "EventSource", "importScripts"]) {
    Object.defineProperty(scope, name, { value: undefined, configurable: false, writable: false });
  }
}

async function loadPyodide(): Promise<Pyodide> {
  const module = await import(/* @vite-ignore */ `${PYODIDE_URL}pyodide.mjs`);
  const pyodide: Pyodide = await module.loadPyodide({ indexURL: PYODIDE_URL });
  lockNetwork();
  return pyodide;
}

// Pyodide's own frames come before the user's code in a traceback; they only cost the model tokens
function cleanTraceback(message: string): string {
  return message.replace(/^ {2}File "\/lib\/python[^"]*\/_pyodide\/[\s\S]*?(?=^ {2}File "<exec>")/m, "");
}

function addLine(current: string, text: string): string {
  return current.length >= MAX_OUTPUT ? current : `${current}${text}\n`;
}

async function run(id: number, code: string) {
  let output = "";
  let error = "";
  try {
    loading ??= loadPyodide();
    const pyodide = await loading.catch((err) => {
      loading = null;
      throw err;
    });
    pyodide.setStdout({ batched: (text) => (output = addLine(output, text)) });
    pyodide.setStderr({ batched: (text) => (error = addLine(error, text)) });
    await pyodide.loadPackagesFromImports(code);
    scope.postMessage({ id, started: true });
    // Every run gets a fresh namespace so variables from an earlier answer do not leak in
    const globals = pyodide.globals.get("dict")();
    try {
      const value = await pyodide.runPythonAsync(code, { globals });
      const result = value === undefined || value === null ? "" : String(value);
      (value as Partial<PyProxy> | null)?.destroy?.();
      return { output, error, result };
    } finally {
      globals.destroy();
    }
  } catch (err) {
    return { output, error: error + cleanTraceback(err instanceof Error ? err.message : String(err)), result: "" };
  }
}

scope.onmessage = async (event) => {
  const { id, code } = event.data;
  scope.postMessage({ id, result: await run(id, code) });
};