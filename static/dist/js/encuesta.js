(() => {
  // static/src/js/encuesta.js
  var STAR_LABELS = ["", "Muy malo", "Malo", "Regular", "Bueno", "Excelente"];
  document.addEventListener("DOMContentLoaded", () => {
    const sections = document.querySelectorAll(".survey-card[data-section]");
    const steps = document.querySelectorAll(".survey-step-item[data-step]");
    function updateStepper() {
      let activeStep = 1;
      sections.forEach((sec) => {
        const rect = sec.getBoundingClientRect();
        if (rect.top <= window.innerHeight * 0.55) {
          activeStep = parseInt(sec.dataset.section);
        }
      });
      steps.forEach((step) => {
        const n = parseInt(step.dataset.step);
        step.classList.toggle("is-active", n === activeStep);
        step.classList.toggle("is-done", n < activeStep);
      });
    }
    window.addEventListener("scroll", updateStepper, { passive: true });
    updateStepper();
    document.querySelectorAll(".star-group").forEach((group) => {
      const stars = group.querySelectorAll(".survey-star");
      const row = group.closest(".survey-rating-row");
      const hiddenInput = row ? row.querySelector(".rating-input") : null;
      const hint = row ? row.querySelector(".survey-star-hint") : null;
      function applyHover(val) {
        stars.forEach((s) => {
          const sv = parseInt(s.dataset.val);
          s.classList.toggle("is-hover", sv <= val);
          s.classList.remove("is-active");
        });
        if (hint) hint.textContent = STAR_LABELS[val] || "";
      }
      function applySelected(val) {
        stars.forEach((s) => {
          const sv = parseInt(s.dataset.val);
          s.classList.toggle("is-active", sv <= val);
          s.classList.remove("is-hover");
        });
        if (hint) hint.textContent = val ? STAR_LABELS[val] : "";
      }
      stars.forEach((star) => {
        star.addEventListener("mouseenter", () => applyHover(parseInt(star.dataset.val)));
        star.addEventListener("click", () => {
          const val = parseInt(star.dataset.val);
          if (hiddenInput) hiddenInput.value = val;
          applySelected(val);
          const err = document.getElementById("err-rating");
          if (err) err.classList.add("hidden");
        });
      });
      group.addEventListener("mouseleave", () => {
        const current = hiddenInput ? parseInt(hiddenInput.value) : 0;
        applySelected(current);
      });
    });
    document.querySelectorAll(".survey-service-card").forEach((card) => {
      const radio = card.querySelector("input[type=radio]");
      if (radio && radio.checked) card.classList.add("is-selected");
      card.addEventListener("click", () => {
        document.querySelectorAll(".survey-service-card").forEach(
          (c) => c.classList.remove("is-selected")
        );
        card.classList.add("is-selected");
        if (radio) radio.checked = true;
        const err = document.getElementById("err-servicio");
        if (err) err.classList.add("hidden");
      });
    });
    document.querySelectorAll(".survey-recommend-card").forEach((card) => {
      const radio = card.querySelector("input[type=radio]");
      if (radio && radio.checked) card.classList.add("is-selected");
      card.addEventListener("click", () => {
        document.querySelectorAll(".survey-recommend-card").forEach(
          (c) => c.classList.remove("is-selected")
        );
        card.classList.add("is-selected");
        if (radio) radio.checked = true;
      });
    });
    const form = document.getElementById("encuestaForm");
    if (!form) return;
    form.addEventListener("submit", (e) => {
      let valid = true;
      form.querySelectorAll(".survey-field-error").forEach((el) => {
        el.textContent = "";
        el.classList.add("hidden");
      });
      form.querySelectorAll(".survey-input").forEach(
        (el) => el.style.removeProperty("border-color")
      );
      const nombre = form.querySelector("#nombre");
      if (!nombre.value.trim()) {
        showError(nombre, "err-nombre", "El nombre es obligatorio.");
        valid = false;
      }
      const email = form.querySelector("#email");
      if (!email.value.trim()) {
        showError(email, "err-email", "El correo es obligatorio.");
        valid = false;
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
        showError(email, "err-email", "Ingresa un correo v\xE1lido.");
        valid = false;
      }
      if (!form.querySelector("[name='tipo_servicio']:checked")) {
        const err = document.getElementById("err-servicio");
        if (err) err.classList.remove("hidden");
        valid = false;
      }
      let ratingsOk = true;
      form.querySelectorAll(".rating-input").forEach((input) => {
        if (!input.value) ratingsOk = false;
      });
      if (!ratingsOk) {
        const err = document.getElementById("err-rating");
        if (err) err.classList.remove("hidden");
        valid = false;
      }
      if (!valid) {
        e.preventDefault();
        const firstErr = form.querySelector(".survey-field-error:not(.hidden)");
        if (firstErr)
          firstErr.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      const btn = document.getElementById("submitBtn");
      if (btn) {
        btn.disabled = true;
        const txt = btn.querySelector(".btn-text");
        if (txt) txt.textContent = "Enviando...";
      }
    });
    function showError(input, errId, msg) {
      const err = document.getElementById(errId);
      if (err) {
        err.textContent = msg;
        err.classList.remove("hidden");
      }
      input.style.borderColor = "var(--color-danger)";
      input.addEventListener(
        "input",
        () => {
          input.style.removeProperty("border-color");
          if (err) err.classList.add("hidden");
        },
        { once: true }
      );
    }
  });
})();
//# sourceMappingURL=encuesta.js.map
