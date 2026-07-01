/**
 * Scroll-reveal universal:
 * - [data-reveal] / [data-reveal-group] — atributos explícitos
 * - Auto-anima clases comunes del proyecto que no tienen otro handler
 */
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

const EASE = "power3.out";

// Elementos que ya tienen sus propios animadores — no duplicar
const SKIP = new Set();
function markSkipped(selector) {
  document.querySelectorAll(selector).forEach((el) => SKIP.add(el));
}

export function initScrollReveal() {
  // Marcar los que ya están manejados
  markSkipped("[data-bento-card]");
  markSkipped("[data-anim]");
  markSkipped("[data-anim-stagger] > *");

  // ── [data-reveal] individuales ─────────────────────────────────────────────
  gsap.utils.toArray("[data-reveal]").forEach((el) => {
    if (SKIP.has(el)) return;
    const dir   = el.dataset.reveal || "up";
    const delay = parseFloat(el.dataset.revealDelay || 0);
    animateFrom(el, dir, delay);
  });

  // ── [data-reveal-group] — stagger sobre hijos directos ────────────────────
  gsap.utils.toArray("[data-reveal-group]").forEach((group) => {
    const children  = [...group.children].filter((c) => !SKIP.has(c));
    if (!children.length) return;
    const stagger   = parseFloat(group.dataset.stagger || 0.1);
    const direction = group.dataset.revealGroup || "up";
    const from      = getFrom(direction);

    gsap.fromTo(children, from, {
      opacity: 1, y: 0, x: 0, scale: 1,
      duration: 0.75, stagger, ease: EASE,
      scrollTrigger: { trigger: group, start: "top 88%", once: true },
    });
  });

  // ── Auto-reveal de clases comunes ─────────────────────────────────────────
  autoRevealCards(".hp-svc",            "up",    0.09);
  autoRevealCards(".copier-card",       "up",    0.08);
  autoRevealCards(".testimonial-card",  "up",    0.08);
  autoRevealCards(".consumable-card",   "up",    0.07);
  autoRevealCards(".hp-proc-step",      "up",    0.1);
  autoRevealCards(".hp-stat-box",       "scale", 0.06);
  autoRevealCards(".card-padded",       "up",    0.09);

  // Section headers .hp-sh
  gsap.utils.toArray(".hp-sh").forEach((el) => {
    if (SKIP.has(el)) return;
    gsap.fromTo(el,
      { opacity: 0, y: 40 },
      {
        opacity: 1, y: 0,
        duration: 0.9, ease: EASE,
        scrollTrigger: { trigger: el, start: "top 90%", once: true },
      }
    );
  });

  // ── [data-img-reveal] — reveal de imágenes con clip-path ──────────────────
  document.querySelectorAll("[data-img-reveal]").forEach((wrapper) => {
    const img = wrapper.querySelector("img");
    if (!img) return;
    gsap.set(wrapper, { overflow: "hidden" });
    gsap.fromTo(wrapper,
      { clipPath: "inset(0% 0% 100% 0%)" },
      {
        clipPath: "inset(0% 0% 0% 0%)",
        duration: 1.1, ease: "power4.out",
        scrollTrigger: { trigger: wrapper, start: "top 88%", once: true },
        clearProps: "clipPath",
      }
    );
    gsap.fromTo(img,
      { scale: 1.15 },
      {
        scale: 1,
        duration: 1.4, ease: "power3.out",
        scrollTrigger: { trigger: wrapper, start: "top 88%", once: true },
      }
    );
  });
}

// ─── helpers ─────────────────────────────────────────────────────────────────

function getFrom(dir) {
  const from = { opacity: 0 };
  if (dir === "up")    from.y = 56;
  if (dir === "down")  from.y = -56;
  if (dir === "left")  from.x = 64;
  if (dir === "right") from.x = -64;
  if (dir === "scale") { from.scale = 0.84; from.y = 24; }
  return from;
}

function animateFrom(el, dir, delay = 0) {
  const from = getFrom(dir);
  gsap.fromTo(el, from, {
    opacity: 1, y: 0, x: 0, scale: 1,
    duration: 0.85, delay, ease: EASE,
    scrollTrigger: { trigger: el, start: "top 90%", once: true },
  });
}

function autoRevealCards(selector, dir, stagger) {
  const cards = gsap.utils.toArray(selector).filter((el) => !SKIP.has(el));
  if (!cards.length) return;

  // Agrupar por sección padre para stagger coherente
  const groups = new Map();
  cards.forEach((card) => {
    const parent = card.parentElement;
    if (!groups.has(parent)) groups.set(parent, []);
    groups.get(parent).push(card);
  });

  groups.forEach((group, parent) => {
    const from = getFrom(dir);
    ScrollTrigger.batch(group, {
      onEnter: (batch) =>
        gsap.to(batch, {
          opacity: 1, y: 0, x: 0, scale: 1,
          duration: 0.8, stagger,
          ease: EASE, overwrite: true,
        }),
      start: "top 88%",
      once: true,
    });
    gsap.set(group, from);
  });
}
