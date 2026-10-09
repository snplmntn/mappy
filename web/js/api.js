export class OfflineError extends Error {}

async function request(path, options, timeoutMs) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(path, { ...options, signal: ctrl.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err.name === "AbortError" || err instanceof TypeError) throw new OfflineError(err.message);
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export const getJSON = (path, timeoutMs = 15000) => request(path, {}, timeoutMs);

export const post = (path, body, timeoutMs = 15000) =>
  request(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }, timeoutMs);
