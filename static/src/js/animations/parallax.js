/**
 * Parallax sutil para elementos decorativos.
 */
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

export function initParallax() {
  const elements = document.querySelectorAll("[data-parallax]");

  elements.forEach((el) => {
    const intensity = parseFloat(el.dataset.parallax) || 0.3;

    gsap.to(el, {
      yPercent: -20 * intensity,
      ease: "none",
      scrollTrigger: {
        trigger: el,
        start: "top bottom",
        end: "bottom top",
        scrub: true,
      },
    });
  });
}
