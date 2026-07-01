/**
 * Quote Wizard — Componente Alpine.js
 */
import { gsap } from "gsap";
import { calculateLiveEstimate } from "./live-calculator.js";
import {
  validateEmail,
  validateColombianPhone,
  validateRequired,
  validateNumber,
} from "./form-validators.js";

export function quoteWizard() {
  return {
    currentStep: 1,
    totalSteps: 3,
    isSubmitting: false,
    successMessage: "",
    errorMessage: "",

    interestArea: "",

    details: {
      copier_id: null,
      quantity: 1,
      monthly_pages: 2000,
      needs_color: false,
      logical_points: 10,
      electrical_points: 0,
      office_size_m2: null,
      needs_certification: false,
      complexity: "medium",
      project_description: "",
      desired_timeline: "",
      // Consumibles
      consumable_type: "toner_bn",
      equipment_model: "",
      consumable_qty: 1,
      consumable_unit_price: 0,
      consumable_product_name: "",
    },

    contact: {
      full_name: "",
      email: "",
      phone: "",
      company_name: "",
      company_size: "",
      job_title: "",
      city: "Medellín",
      gdpr_consent: false,
    },

    errors: {},

    estimate: {
      total: 0,
      range_min: 0,
      range_max: 0,
      formatted: "Pendiente",
      isCalculating: false,
    },

    interestAreas: [
      {
        id: "rental", label: "Alquiler de fotocopiadoras", description: "Renta de equipos Ricoh con servicio incluido",
        silo: "hardware",
        iconSvg: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/></svg>`,
      },
      {
        id: "sale", label: "Compra de fotocopiadoras", description: "Adquisición de equipos nuevos o refurbished",
        silo: "hardware",
        iconSvg: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"/></svg>`,
      },
      {
        id: "consumables", label: "Tóner, tintas y repuestos", description: "Insumos para toda marca y modelo de equipo",
        silo: "hardware",
        iconSvg: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125"/></svg>`,
      },
      {
        id: "cabling", label: "Cableado estructurado", description: "Puntos de red, eléctricos y certificación",
        silo: "hardware",
        iconSvg: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12.55a11 11 0 0114.08 0M1.42 9a16 16 0 0121.16 0M8.53 16.11a6 6 0 016.95 0M12 20h.01"/></svg>`,
      },
      {
        id: "software", label: "Software a la medida", description: "Sistemas, ERPs e integraciones",
        silo: "software",
        iconSvg: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/></svg>`,
      },
      {
        id: "web", label: "Diseño web / E-commerce", description: "Sitios corporativos y tiendas online",
        silo: "software",
        iconSvg: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path stroke-linecap="round" stroke-linejoin="round" d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10A15.3 15.3 0 0112 2z"/></svg>`,
      },
      {
        id: "mobile", label: "Aplicaciones móviles", description: "Apps iOS, Android e híbridas",
        silo: "software",
        iconSvg: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>`,
      },
      {
        id: "database", label: "Bases de datos", description: "Diseño y migración cloud",
        silo: "software",
        iconSvg: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"/></svg>`,
      },
      {
        id: "full_office", label: "Solución integral", description: "Llave en mano: red + impresión + software",
        silo: "hybrid",
        iconSvg: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>`,
      },
    ],

    availableCopiers: [],

    init() {
      const dataEl = document.querySelector("[data-wizard-context]");
      if (dataEl) {
        try {
          const ctx = JSON.parse(dataEl.textContent);
          this.availableCopiers = ctx.copiers || [];
          if (ctx.session && Object.keys(ctx.session).length) {
            this.restoreFromSession(ctx.session);
          }
        } catch (e) {
          console.warn("No se pudo cargar contexto:", e);
        }
      }

      this.$nextTick(() => this.recalculate());

      this.$watch("details", () => this.recalculate(), { deep: true });
      this.$watch("interestArea", () => this.recalculate());
    },

    async nextStep() {
      if (!this.validateCurrentStep()) {
        this.shakeForm();
        return;
      }

      const persisted = await this.persistStep();
      if (!persisted) return;

      if (this.currentStep < this.totalSteps) {
        await this.animateStepTransition("next");
        this.currentStep++;
      }
    },

    async prevStep() {
      if (this.currentStep > 1) {
        await this.animateStepTransition("prev");
        this.currentStep--;
      }
    },

    async goToStep(targetStep) {
      if (targetStep < this.currentStep) {
        await this.animateStepTransition("prev");
        this.currentStep = targetStep;
      } else if (targetStep === this.currentStep + 1) {
        await this.nextStep();
      }
    },

    animateStepTransition(direction) {
      return new Promise((resolve) => {
        const currentEl = document.querySelector(`[data-step="${this.currentStep}"]`);
        if (!currentEl) {
          resolve();
          return;
        }

        const xExit = direction === "next" ? -60 : 60;
        gsap.to(currentEl, {
          opacity: 0,
          x: xExit,
          duration: 0.3,
          ease: "power2.in",
          onComplete: () => {
            this.$nextTick(() => {
              const newStepNum = direction === "next" ? this.currentStep + 1 : this.currentStep - 1;
              const newEl = document.querySelector(`[data-step="${newStepNum}"]`);
              if (newEl) {
                gsap.fromTo(newEl,
                  { opacity: 0, x: direction === "next" ? 60 : -60 },
                  {
                    opacity: 1, x: 0, duration: 0.5,
                    ease: "power3.out",
                    onComplete: () => resolve(),
                  }
                );
              } else {
                resolve();
              }
            });
          },
        });
      });
    },

    shakeForm() {
      const stepEl = document.querySelector(`[data-step="${this.currentStep}"]`);
      if (!stepEl) return;
      gsap.fromTo(stepEl, { x: 0 }, {
        x: 0, duration: 0.4,
        ease: "elastic.out(1, 0.3)",
        keyframes: [{ x: -10 }, { x: 10 }, { x: -8 }, { x: 8 }, { x: 0 }],
      });
    },

    validateCurrentStep() {
      this.errors = {};

      if (this.currentStep === 1) {
        if (!this.interestArea) {
          this.errors.interestArea = "Selecciona una opción";
          return false;
        }
      }

      if (this.currentStep === 2) {
        return this.validateDetailsStep();
      }

      if (this.currentStep === 3) {
        return this.validateContactStep();
      }

      return true;
    },

    validateDetailsStep() {
      const ok = (cond, field, msg) => {
        if (!cond) this.errors[field] = msg;
        return cond;
      };

      switch (this.interestArea) {
        case "rental":
        case "sale":
          return (
            ok(validateNumber(this.details.quantity, 1, 50), "quantity", "Cantidad inválida (1-50)") &
            ok(validateNumber(this.details.monthly_pages, 100, 500000), "monthly_pages", "Páginas mensuales fuera de rango")
          );

        case "consumables":
          return true; // todos los campos son opcionales en insumos

        case "cabling":
          return ok(
            this.details.logical_points + this.details.electrical_points >= 1,
            "logical_points",
            "Debe haber al menos 1 punto a instalar"
          );

        case "software":
        case "web":
        case "mobile":
        case "database":
        case "full_office":
          return (
            ok(validateRequired(this.details.complexity), "complexity", "Selecciona complejidad") &
            ok(this.details.project_description.length >= 30, "project_description", "Descripción mínima de 30 caracteres")
          );

        default:
          return true;
      }
    },

    validateContactStep() {
      const ok = (cond, field, msg) => {
        if (!cond) this.errors[field] = msg;
        return cond;
      };

      return (
        ok(validateRequired(this.contact.full_name), "full_name", "Nombre requerido") &
        ok(validateEmail(this.contact.email), "email", "Email inválido") &
        ok(validateColombianPhone(this.contact.phone), "phone", "Teléfono colombiano inválido") &
        ok(this.contact.gdpr_consent === true, "gdpr_consent", "Debes autorizar el tratamiento de datos")
      );
    },

    _calcTimeout: null,
    recalculate() {
      clearTimeout(this._calcTimeout);
      this._calcTimeout = setTimeout(async () => {
        if (!this.interestArea) return;

        this.estimate.isCalculating = true;
        try {
          const result = await calculateLiveEstimate(this.interestArea, this.details);
          if (result.ok) {
            this.estimate = {
              total: result.estimated_total,
              range_min: result.range_min,
              range_max: result.range_max,
              formatted: result.formatted,
              isCalculating: false,
            };
            this.animateEstimate();
          } else {
            this.estimate.isCalculating = false;
          }
        } catch (e) {
          console.warn("Error calculando estimación:", e);
          this.estimate.isCalculating = false;
        }
      }, 400);
    },

    animateEstimate() {
      const el = document.querySelector("[data-estimate-value]");
      if (!el) return;
      gsap.fromTo(el,
        { scale: 1.08, color: "var(--color-primary)" },
        {
          scale: 1, color: "var(--color-text-primary)",
          duration: 0.6, ease: "elastic.out(1, 0.4)",
        }
      );
    },

    async persistStep() {
      const formData = new FormData();

      if (this.currentStep === 1) {
        formData.append("interest_area", this.interestArea);
      } else if (this.currentStep === 2) {
        Object.entries(this.details).forEach(([key, value]) => {
          if (value !== null && value !== undefined) {
            formData.append(key, value);
          }
        });
      } else if (this.currentStep === 3) {
        Object.entries(this.contact).forEach(([key, value]) => {
          if (value !== null && value !== undefined) {
            formData.append(key, value);
          }
        });
      }

      try {
        const response = await fetch(`/cotizador/paso/${this.currentStep}/`, {
          method: "POST",
          headers: {
            "X-CSRFToken": this.getCSRFToken(),
            "X-Requested-With": "XMLHttpRequest",
          },
          body: formData,
        });

        const data = await response.json();
        if (!data.ok) {
          if (data.errors) {
            Object.entries(data.errors).forEach(([field, errs]) => {
              this.errors[field] = errs[0]?.message || "Campo inválido";
            });
          } else if (data.error) {
            this.errorMessage = data.error;
          }
          return false;
        }
        return true;
      } catch (e) {
        console.error("Error persistiendo paso:", e);
        this.errorMessage = "Error de conexión. Intenta de nuevo.";
        return false;
      }
    },

    restoreFromSession(session) {
      if (session.interest_area) this.interestArea = session.interest_area;
      if (session.step_2) {
        Object.entries(session.step_2).forEach(([k, v]) => {
          if (k in this.details) this.details[k] = v;
        });
      }
      if (session.step_3) {
        Object.entries(session.step_3).forEach(([k, v]) => {
          if (k in this.contact) this.contact[k] = v;
        });
      }
      // Si step_1 ya está grabado (pre-selección desde landing o sesión guardada),
      // avanza automáticamente al paso correcto
      if (session.step_1 && session.interest_area) {
        if (session.step_3) {
          this.currentStep = 3;
        } else if (session.step_2) {
          this.currentStep = 2;
        } else {
          // Pre-selección limpia: ir al paso 2 con animación suave
          this.$nextTick(() => {
            setTimeout(() => { this.currentStep = 2; }, 250);
          });
        }
      }
    },

    async submit() {
      if (!this.validateCurrentStep()) {
        this.shakeForm();
        return;
      }

      this.isSubmitting = true;
      this.errorMessage = "";

      const persisted = await this.persistStep();
      if (!persisted) {
        this.isSubmitting = false;
        return;
      }

      try {
        const response = await fetch("/cotizador/enviar/", {
          method: "POST",
          headers: {
            "X-CSRFToken": this.getCSRFToken(),
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        });

        const data = await response.json();
        if (data.ok) {
          window.location.href = `/cotizador/gracias/?qid=${data.quote_id}`;
        } else {
          this.errorMessage = data.error || "Error al enviar. Intenta de nuevo.";
        }
      } catch (e) {
        console.error("Error en submit:", e);
        this.errorMessage = "Error de conexión. Intenta de nuevo.";
      } finally {
        this.isSubmitting = false;
      }
    },

    getCSRFToken() {
      const cookie = document.cookie
        .split("; ")
        .find((c) => c.startsWith("csrftoken="));
      return cookie ? cookie.split("=")[1] : "";
    },

    get progressPercentage() {
      return Math.round(((this.currentStep - 1) / (this.totalSteps - 1)) * 100);
    },

    get currentInterestData() {
      return this.interestAreas.find((a) => a.id === this.interestArea);
    },

    get isHardwareFlow() {
      const hw = ["rental", "sale", "cabling"];
      return hw.includes(this.interestArea);
    },

    get isSoftwareFlow() {
      const sw = ["software", "web", "mobile", "database"];
      return sw.includes(this.interestArea);
    },

    formatCurrency(value) {
      if (!value) return "$0";
      return new Intl.NumberFormat("es-CO", {
        style: "currency",
        currency: "COP",
        maximumFractionDigits: 0,
      }).format(value);
    },
  };
}

window.quoteWizard = quoteWizard;
