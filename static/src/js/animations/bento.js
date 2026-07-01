/**
 * Bento grid: entrada con stagger + 3D tilt + spotlight light-follow.
 * También aplica spotlight a .hp-svc y .card-padded.
 */
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

function addSpotlight(el) {
  el.addEventListener("mousemove", (e) => {
    const rect = el.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width)  * 100;
    const y = ((e.clientY - rect.top)  / rect.height) * 100;
    el.style.setProperty("--mx", `${x}%`);
    el.style.setProperty("--my", `${y}%`);
  });
}

export function initBento() {
  const cards = gsap.utils.toArray("[data-bento-card]");
  if (!cards.length) return;

  gsap.set(cards, { opacity: 0, y: 60 });

  ScrollTrigger.batch(cards, {
    onEnter: (batch) =>
      gsap.to(batch, {
        opacity: 1, y: 0,
        duration: 0.9, stagger: 0.12,
        ease: "power3.out",
        overwrite: true,
      }),
    start: "top 85%",
    once: true,
  });

  cards.forEach((card) => {
    addSpotlight(card);

    const handleMove = (e) => {
      const rect    = card.getBoundingClientRect();
      const x       = e.clientX - rect.left;
      const y       = e.clientY - rect.top;
      const rotateY = ((x / rect.width)  - 0.5) *  6;
      const rotateX = ((y / rect.height) - 0.5) * -6;

      gsap.to(card, {
        rotateX, rotateY,
        duration: 0.5,
        ease: "power2.out",
        transformPerspective: 1000,
      });
    };

    const handleLeave = () => {
      gsap.to(card, {
        rotateX: 0, rotateY: 0,
        duration: 0.6,
        ease: "elastic.out(1, 0.5)",
      });
    };

    card.addEventListener("mousemove", handleMove);
    card.addEventListener("mouseleave", handleLeave);
  });

  // Spotlight también en service cards y cards generales
  document.querySelectorAll(".hp-svc, .card-padded").forEach(addSpotlight);
}
