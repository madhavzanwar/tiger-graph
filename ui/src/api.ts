// VITE_REPLAY=1 builds a static, read-only console that reads exported snapshots from /demo (see `verdict export-demo`).
export const REPLAY = (import.meta as any).env?.VITE_REPLAY === "1";

function replayPath(path: string): string {
  if (path === "/api/health") return "/demo/health.json";
  if (path === "/api/cases") return "/demo/cases.json";
  if (path === "/api/model") return "/demo/model.json";
  if (path === "/api/policy") return "/demo/policy.json";
  const m = path.match(/^\/api\/cases\/([^/]+)$/);
  if (m) return `/demo/cases/${m[1]}.json`;
  return path;
}

export async function get<T = any>(path: string): Promise<T> {
  const r = await fetch(REPLAY ? replayPath(path) : path);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export async function post<T = any>(path: string, body: any = {}): Promise<T> {
  if (REPLAY) throw new Error("read-only replay: run the agent locally to investigate live");
  const r = await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const pct = (p?: number) => (p === undefined || p === null ? "–" : `${(p * 100).toFixed(p > 0.99 || p < 0.01 ? 1 : 0)}%`);
