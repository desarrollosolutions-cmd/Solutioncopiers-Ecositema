/**
 * Text split — anima headings de secciones carácter por carácter o palabra a palabra.
 * Uso: <h2 data-split="words"> o <h2 data-split="chars">
 */
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

function splitWords(el) {
  const original = el.innerHTML;
  const words = el.textContent.trim().split(/\s+/);
  el.innerHTML = words
    .map(w => `<span class="split-word" style="display:inline-block;overflow:hidden;vertical-align:bottom"><span class="split-inner" style="display:inline-block">${w}</span></span>`)
    .join(" ");

  const inners = el.querySelectorAll(".split-inner");
  gsap.fromTo(inners,
    { yPercent: 110, opacity: 0 },
    {
      yPercent: 0, opacity: 1,
      duration: 0.75,
      stagger: 0.07,
      ease: "power3.out",
      scrollTrigger: { trigger: el, start: "top 92%", once: true },
      onComplete: () => {
        // Flatten después de animar para no romper selección de texto
        el.innerHTML = original;
      },
    }
  );
}

function splitChars(el) {
  const text   = el.textContent.trim();
  el.innerHTML = text
    .split("")
    .map(c => c === " "
      ? `<span style="display:inline-block;width:.35em">&nbsp;</span>`
      : `<span class="split-char" style="display:inline-block">${c}</span>`)
    .join("");

  const chars = el.querySelectorAll(".split-char");
  gsap.fromTo(chars,
    { opacity: 0, y: 28, rotateX: -45, transformPerspective: 600 },
    {
      opacity: 1, y: 0, rotateX: 0,
      duration: 0.5,
      stagger: 0.028,
      ease: "back.out(1.6)",
      scrollTrigger: { trigger: el, start: "top 92%", once: true },
    }
  );
}

export function initTextSplit() {
  document.querySelectorAll("[data-split]").forEach((el) => {
    const type = el.dataset.split;
    if (type === "chars") splitChars(el);
    else                  splitWords(el);
  });
}
