"""
Calcula y actualiza el Lead Score (0-100) para cada cliente.

Algoritmo de puntuación:

  Categoría            Puntos  Descripción
  ─────────────────────────────────────────────────────────────
  Datos completos       +10    email, phone, company, nit, city
  Actividad reciente    +25    actividad en los últimos 7 días
  Actividad moderada    +15    actividad en los últimos 30 días
  Tiene cotización      +15    al menos 1 cotización
  Cotización avanzada   +10    status: negotiating / accepted
  Contrato activo       +20    tiene contrato en estado active
  Ticket de servicio    +5     cliente existente con soporte
  Fuente de alta calidad +5    wizard / contact / referral
  ─────────────────────────────────────────────────────────────
  Penalizaciones
  Lead frío             -10    sin actividad > 60 días (y sin contrato)
  Sin datos             -5     sin email ni phone ni nit

Ejecutar:
    python manage.py update_lead_scores
    python manage.py update_lead_scores --lead-id 42
"""
from __future__ import annotations

import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


def calculate_score(lead) -> int:
    score = 0

    # ── Completitud de datos (max 10) ──────────────────────────────────
    data_fields = [lead.email, lead.phone, lead.company_name, lead.nit, lead.city]
    filled = sum(1 for f in data_fields if f and str(f).strip())
    score += min(filled * 2, 10)

    # ── Actividad reciente ──────────────────────────────────────────────
    now = timezone.now()
    last_activity = lead.activities.order_by("-created_at").first()
    if last_activity:
        days_ago = (now - last_activity.created_at).days
        if days_ago <= 7:
            score += 25
        elif days_ago <= 30:
            score += 15
        elif days_ago > 60:
            # cold lead (only if no active contract)
            has_contract = lead.contracts.filter(status="active").exists()
            if not has_contract:
                score -= 10

    # ── Cotizaciones ────────────────────────────────────────────────────
    quotes = list(lead.quotes.all())
    if quotes:
        score += 15
        advanced_statuses = {"negotiating", "accepted", "won"}
        if any(q.status in advanced_statuses for q in quotes):
            score += 10

    # ── Contratos ───────────────────────────────────────────────────────
    active_contracts = lead.contracts.filter(status="active").count()
    if active_contracts:
        score += 20

    # ── Tickets ─────────────────────────────────────────────────────────
    if lead.tickets.exists():
        score += 5

    # ── Fuente de alta calidad ──────────────────────────────────────────
    high_quality_sources = {"wizard", "contact", "referral"}
    if lead.source in high_quality_sources:
        score += 5

    # ── Penalización: sin datos de contacto ────────────────────────────
    if not lead.email and not lead.phone and not lead.nit:
        score -= 5

    return max(0, min(100, score))


class Command(BaseCommand):
    help = "Calcula y actualiza el Lead Score para todos los clientes"

    def add_arguments(self, parser):
        parser.add_argument("--lead-id", type=int, help="Solo actualizar este lead")
        parser.add_argument("--dry-run", action="store_true", help="Mostrar sin guardar")

    def handle(self, *args, **options):
        from apps.leads.models import Lead

        qs = Lead.objects.prefetch_related(
            "activities", "quotes", "contracts", "tickets"
        )
        if options["lead_id"]:
            qs = qs.filter(pk=options["lead_id"])

        dry = options["dry_run"]
        now = timezone.now()
        updated = 0
        distribution = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}

        for lead in qs.iterator(chunk_size=200):
            new_score = calculate_score(lead)

            # Distribución
            bucket = min(4, new_score // 21)
            keys = list(distribution.keys())
            distribution[keys[bucket]] += 1

            if not dry:
                Lead.objects.filter(pk=lead.pk).update(score=new_score, score_at=now)
            else:
                self.stdout.write(f"  [DRY] {lead.full_name[:35]:35s} -> {new_score:3d}")
            updated += 1

        mode = "[DRY RUN] " if dry else ""
        self.stdout.write(self.style.SUCCESS(
            f"{mode}Scores actualizados: {updated} leads"
        ))
        self.stdout.write("Distribucion:")
        for bucket, count in distribution.items():
            bar = "#" * min(40, count)
            self.stdout.write(f"  {bucket:8s} {bar} ({count})")
