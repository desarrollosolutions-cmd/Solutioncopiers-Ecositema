/**
 * Animated counters — triggered once by ScrollTrigger
 */
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

export function initCounters() {
  const els = document.querySelectorAll("[data-counter]");
  if (!els.length) return;

  els.forEach((el) => {
    const target = parseFloat(el.dataset.counter);
    const suffix = el.dataset.suffix || "";
    const decimals = el.dataset.decimals ? parseInt(el.dataset.decimals) : 0;

    ScrollTrigger.create({
      trigger: el,
      start: "top 85%",
      once: true,
      onEnter: () => {
        gsap.fromTo(
          { val: 0 },
          {
            val: target,
            duration: 2,
            ease: "power2.out",
            onUpdate() {
              el.textContent =
                this.targets()[0].val.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ",") + suffix;
            },
            onComplete() {
              el.textContent =
                target.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ",") + suffix;
            },
          }
        );
      },
    });
  });
}
