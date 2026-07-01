/**
 * Cursor personalizado con punto seguidor y anillo con lag.
 * Se activa solo en dispositivos con hover (no touch).
 */
import { gsap } from "gsap";

export function initCursor() {
  if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;

  // Inyectar DOM
  const dot  = document.createElement("div");
  const ring = document.createElement("div");
  dot.id  = "cursor-dot";
  ring.id = "cursor-ring";
  document.body.appendChild(dot);
  document.body.appendChild(ring);

  let mx = window.innerWidth  / 2;
  let my = window.innerHeight / 2;

  // El punto sigue exacto
  document.addEventListener("mousemove", (e) => {
    mx = e.clientX;
    my = e.clientY;
    gsap.to(dot, { x: mx, y: my, duration: 0.08, ease: "none" });
  });

  // El anillo sigue con lag
  gsap.ticker.add(() => {
    gsap.to(ring, { x: mx, y: my, duration: 0.55, ease: "power3.out" });
  });

  // Estado hover sobre links y botones
  const interactives = "a, button, .cursor-magnetic, [data-cursor='pointer'], input, label";

  document.addEventListener("mouseover", (e) => {
    if (e.target.closest(interactives)) {
      dot.classList.add("cursor-hover");
      ring.classList.add("cursor-hover");
    }
  });

  document.addEventListener("mouseout", (e) => {
    if (e.target.closest(interactives)) {
      dot.classList.remove("cursor-hover");
      ring.classList.remove("cursor-hover");
    }
  });

  // Ocultar cuando sale de la ventana
  document.addEventListener("mouseleave", () => {
    gsap.to([dot, ring], { opacity: 0, duration: 0.3 });
  });
  document.addEventListener("mouseenter", () => {
    gsap.to([dot, ring], { opacity: 1, duration: 0.3 });
  });
}
