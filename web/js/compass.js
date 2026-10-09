/**
 * Phone compass: a smoothed heading in degrees clockwise from true north, or null when unknown.
 * Browsers only expose orientation on https pages; iOS also asks permission on a tap.
 */

const SMOOTHING = 0.2;
const MIN_CHANGE_DEG = 1;

const listeners = new Set();
let heading = null;
let started = false;
let vec = null;

export const norm = (deg) => ((deg % 360) + 360) % 360;

/** Signed smallest turn from a to b, in (-180, 180]. */
export const turn = (a, b) => {
  const d = norm(b - a);
  return d > 180 ? d - 360 : d;
};

export function compassHeading() {
  return heading;
}

export function onHeading(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

const needsPermission = () => typeof DeviceOrientationEvent.requestPermission === "function";

export const supported = () => window.isSecureContext && "DeviceOrientationEvent" in window;

function screenAngle() {
  return (screen.orientation && screen.orientation.angle) || Number(window.orientation) || 0;
}

function read(e) {
  if (typeof e.webkitCompassHeading === "number" && e.webkitCompassHeading >= 0) return e.webkitCompassHeading + screenAngle();
  if (e.absolute && typeof e.alpha === "number") return 360 - e.alpha + screenAngle();
  return null;
}

/** Average on the unit circle so 359° and 1° smooth to 0°, not 180°. */
function smooth(raw) {
  const r = (raw * Math.PI) / 180;
  const x = Math.sin(r);
  const y = Math.cos(r);
  vec = vec ? [vec[0] + (x - vec[0]) * SMOOTHING, vec[1] + (y - vec[1]) * SMOOTHING] : [x, y];
  return norm((Math.atan2(vec[0], vec[1]) * 180) / Math.PI);
}

function handle(e) {
  const raw = read(e);
  if (raw === null) return;
  const next = smooth(norm(raw));
  if (heading !== null && Math.abs(turn(heading, next)) < MIN_CHANGE_DEG) return;
  heading = next;
  listeners.forEach((fn) => fn(heading));
}

/**
 * Listen for compass readings. Readings arrive without asking where the browser allows it (Android);
 * pass ask=true from a tap to show the permission prompt where it's required (iOS).
 * Resolves to false when the compass can't be used.
 */
export async function startCompass({ ask = false } = {}) {
  if (!supported()) return false;
  if (ask && needsPermission()) {
    try {
      if ((await DeviceOrientationEvent.requestPermission()) !== "granted") return false;
    } catch {
      return false;
    }
  }
  if (!started) {
    started = true;
    // Android Chrome reports north-referenced readings on its own event; iOS adds webkitCompassHeading to the plain one.
    window.addEventListener("ondeviceorientationabsolute" in window ? "deviceorientationabsolute" : "deviceorientation", handle);
  }
  return true;
}
