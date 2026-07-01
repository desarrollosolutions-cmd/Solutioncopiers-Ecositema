/**
 * Efecto magnético — los elementos .cursor-magnetic siguen el cursor.
 */
import { gsap } from "gsap";

export function initMagnetic() {
  const magnetics = document.querySelectorAll(".cursor-magnetic");
  if (!magnetics.length) return;

  magnetics.forEach((el) => {
    const strength = parseFloat(el.dataset.magneticStrength || 0.38);
    const inner    = el.querySelector(".magnetic-inner") || el;

    el.addEventListener("mousemove", (e) => {
      const rect    = el.getBoundingClientRect();
      const centerX = rect.left + rect.width  / 2;
      const centerY = rect.top  + rect.height / 2;
      const dx      = (e.clientX - centerX) * strength;
      const dy      = (e.clientY - centerY) * strength;

      gsap.to(inner, {
        x: dx, y: dy,
        duration: 0.45,
        ease: "power2.out",
      });
    });

    el.addEventListener("mouseleave", () => {
      gsap.to(inner, {
        x: 0, y: 0,
        duration: 0.7,
        ease: "elastic.out(1, 0.4)",
      });
    });
  });
}
