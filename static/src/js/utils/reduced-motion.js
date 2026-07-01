/**
 * Detecta si el usuario prefiere movimiento reducido.
 */
export function respectsReducedMotion() {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
