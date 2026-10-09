/** The phone can't reach the server at all (wrong Wi-Fi, server down). */
export class OfflineError extends Error {}
/** The server is reachable but didn't answer in time. */
export class TimeoutError extends Error {}
/** The server answered with an error; `message` is safe to show the user. */
export class ApiError extends Error {}
/** The shopper pressed stop. */
export class CancelledError extends Error {}

export const SERVER_ERROR = "Something went wrong on the Mappy server. Try again.";

async function errorMessage(res) {
  try {
    return (await res.json()).error || SERVER_ERROR;
  } catch {
    return SERVER_ERROR;
  }
}

async function request(path, options, timeoutMs, signal) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  signal?.addEventListener("abort", () => ctrl.abort());
  try {
    const res = await fetch(path, { ...options, signal: ctrl.signal });
    if (!res.ok) throw new ApiError(await errorMessage(res));
    return await res.json();
  } catch (err) {
    if (err.name === "AbortError") throw signal?.aborted ? new CancelledError() : new TimeoutError(err.message);
    if (err instanceof TypeError) throw new OfflineError(err.message);
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export const getJSON = (path, timeoutMs = 15000) => request(path, {}, timeoutMs);

export const post = (path, body, { timeoutMs = 15000, signal } = {}) =>
  request(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }, timeoutMs, signal);
