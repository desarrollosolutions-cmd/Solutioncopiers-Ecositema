/**
 * Navbar: cambia a glassmorphism al hacer scroll > 80px.
 */
export function initNavbar() {
  const navbar = document.querySelector("[data-navbar]");
  if (!navbar) return;

  const handleScroll = () => {
    if (window.scrollY > 80) {
      navbar.classList.add("is-scrolled");
    } else {
      navbar.classList.remove("is-scrolled");
    }
  };

  handleScroll();
  window.addEventListener("scroll", handleScroll, { passive: true });
}
