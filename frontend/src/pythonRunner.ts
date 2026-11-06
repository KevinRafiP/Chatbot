export type PythonResult = { output: string; error: string; result: string };

// Pyodide (about 10 MB) is downloaded the first time Python runs on this device, so loading has its own limit;
// it stays below the agent's 30 second allowance so the agent hears about a failed load
const LOAD_SECONDS = 25;

let worker: Worker | null = null;
let nextId = 0;

function failed(error: string): PythonResult {
  return { output: "", error, result: "" };
}

// Runs Python code on this device. A run that passes its time limit stops the worker; a new one is made next time
export function runPython(code: string, timeoutSeconds: number): Promise<PythonResult> {
  worker ??= new Worker(new URL("./pythonWorker.ts", import.meta.url), { type: "module" });
  const current = worker;
  const id = ++nextId;

  return new Promise((resolve) => {
    let timer = 0;
    const finish = (result: PythonResult) => {
      window.clearTimeout(timer);
      current.removeEventListener("message", onMessage);
      current.removeEventListener("error", onError);
      resolve(result);
    };
    const stop = (error: string) => {
      current.terminate();
      if (worker === current) worker = null;
      finish(failed(error));
    };
    const startTimer = (seconds: number, error: string) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => stop(error), seconds * 1000);
    };
    const onMessage = (event: MessageEvent<{ id: number; started?: boolean; result?: PythonResult }>) => {
      if (event.data.id !== id) return;
      if (event.data.started) startTimer(timeoutSeconds, `Kode dihentikan setelah ${timeoutSeconds} detik`);
      if (event.data.result) finish(event.data.result);
    };
    const onError = (event: ErrorEvent) => stop(event.message || "Python tidak bisa dijalankan di perangkat ini");

    current.addEventListener("message", onMessage);
    current.addEventListener("error", onError);
    startTimer(LOAD_SECONDS, "Python gagal dimuat di perangkat ini");
    current.postMessage({ id, code });
  });
}