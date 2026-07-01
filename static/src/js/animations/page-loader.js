/**
 * Page loader — barra de progreso + panel que sube al cargar.
 */
import { gsap } from "gsap";

export function initPageLoader() {
  const loader = document.getElementById("page-loader");
  if (!loader) return;

  document.body.style.overflow = "hidden";

  const bar  = loader.querySelector(".loader-bar");
  const logo = loader.querySelector(".loader-logo");

  const tl = gsap.timeline({
    onComplete: () => {
      loader.remove();
      document.body.style.overflow = "";
    },
  });

  tl.set(bar, { scaleX: 0, transformOrigin: "left center" })
    .to(bar, { scaleX: 1, duration: 0.65, ease: "power2.inOut" })
    .to(logo, { opacity: 0, y: -16, duration: 0.3, ease: "power2.in" }, "-=0.1")
    .to(loader, {
      yPercent: -100,
      duration: 0.65,
      ease: "power3.inOut",
    }, "-=0.05");
}
