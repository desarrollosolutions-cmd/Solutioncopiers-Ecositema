/**
 * Animación de entrada del hero.
 */
import { gsap } from "gsap";

export function initHero() {
  const hero = document.querySelector("[data-hero]");
  if (!hero) return;

  const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

  const eyebrow = hero.querySelector("[data-anim='eyebrow']");
  if (eyebrow) {
    tl.fromTo(eyebrow,
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: 0.6 }
    );
  }

  const headline = hero.querySelector("[data-anim='headline']");
  if (headline) {
    const text = headline.textContent;
    headline.innerHTML = text
      .split(" ")
      .map((word) => `<span class="inline-block">${word}</span>`)
      .join(" ");
    const words = headline.querySelectorAll("span");

    tl.fromTo(words,
      { opacity: 0, y: 40, rotateX: -20 },
      {
        opacity: 1, y: 0, rotateX: 0,
        duration: 0.9, stagger: 0.08,
        ease: "back.out(1.4)",
      },
      "-=0.3"
    );
  }

  const description = hero.querySelector("[data-anim='description']");
  if (description) {
    tl.fromTo(description,
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: 0.8 },
      "-=0.4"
    );
  }

  const ctas = hero.querySelectorAll("[data-anim='cta']");
  if (ctas.length) {
    tl.fromTo(ctas,
      { opacity: 0, scale: 0.9, y: 16 },
      { opacity: 1, scale: 1, y: 0, duration: 0.6, stagger: 0.1 },
      "-=0.6"
    );
  }

  const trust = hero.querySelectorAll("[data-anim='trust'] > *");
  if (trust.length) {
    tl.fromTo(trust,
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.5, stagger: 0.08 },
      "-=0.4"
    );
  }
}
