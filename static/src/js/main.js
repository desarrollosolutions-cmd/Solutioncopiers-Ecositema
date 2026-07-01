/**
 * Solution Copiers — Frontend Entry Point
 */
import Alpine from "alpinejs";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import { initHero }         from "./animations/hero.js";
import { initBento }        from "./animations/bento.js";
import { initParallax }     from "./animations/parallax.js";
import { initNavbar }       from "./animations/navbar.js";
import { initCounters }     from "./animations/counters.js";
import { initScrollReveal } from "./animations/scroll-reveal.js";
import { initMagnetic }     from "./animations/magnetic.js";
import { initTextSplit }    from "./animations/text-split.js";
import { initCursor }       from "./animations/cursor.js";
import { initPageLoader }   from "./animations/page-loader.js";
import { initLenis }        from "./utils/lenis.js";
import { respectsReducedMotion } from "./utils/reduced-motion.js";

import { quoteWizard } from "./components/quote-wizard.js";

gsap.registerPlugin(ScrollTrigger);

// === THEME MANAGER ===
function darkMode() {
  return {
    theme: document.documentElement.getAttribute('data-theme') || 'light',
    open: false,

    themes: [
      {
        id: 'light',
        label: 'Claro',
        desc: 'Modo día',
        bg: '#FFFFFF',
        surface: '#FFFFFF',
        primary: '#C4121A',
      },
      {
        id: 'dark',
        label: 'Noche',
        desc: 'Modo oscuro',
        bg: '#100808',
        surface: '#221414',
        primary: '#C4121A',
      },
    ],

    setTheme(id) {
      this.theme = id;
      document.documentElement.setAttribute('data-theme', id);
      localStorage.setItem('theme', id);
      this.open = false;
    },

    toggle() {
      this.open = !this.open;
    },

    get dark() {
      return this.theme !== 'light';
    },

    get current() {
      return this.themes.find(t => t.id === this.theme) || this.themes[0];
    },
  };
}
window.darkMode = darkMode;

// === ALPINE.JS ===
window.Alpine = Alpine;
window.quoteWizard = quoteWizard;
Alpine.start();

// === BOOT ===
document.addEventListener("DOMContentLoaded", () => {

  // FAQ accordion — independiente de animaciones
  document.querySelectorAll(".hp-faq-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item   = btn.closest(".hp-faq-item");
      const isOpen = item.hasAttribute("data-open");
      document.querySelectorAll(".hp-faq-item[data-open]").forEach((el) => el.removeAttribute("data-open"));
      if (!isOpen) item.setAttribute("data-open", "");
    });
  });

  const reducedMotion      = respectsReducedMotion();
  const animationsEnabled  =
    document.documentElement.dataset.animationsEnabled === "true";

  // Page loader siempre, independiente de las otras animaciones
  initPageLoader();

  if (!animationsEnabled || reducedMotion) {
    document.body.classList.add("js-failed");
    return;
  }

  if (document.documentElement.dataset.smoothScroll === "true") {
    initLenis();
  }

  initCursor();
  initNavbar();
  initCounters();
  initScrollReveal();
  initTextSplit();
  initMagnetic();

  if (document.querySelector("[data-hero]")) {
    initHero();
  }
  if (document.querySelector("[data-bento-card]")) {
    initBento();
  }
  if (
    document.documentElement.dataset.parallaxEnabled === "true" &&
    document.querySelector("[data-parallax]")
  ) {
    initParallax();
  }
});
