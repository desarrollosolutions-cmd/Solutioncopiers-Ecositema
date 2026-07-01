"""
Automatización de renovación de contratos.

Detecta contratos activos próximos a vencer y:
  1. Crea tareas de seguimiento (FollowUpTask) asignadas a la asesora del lead
  2. Genera notificaciones CRM personalizadas
  3. Marca contratos como expirados si ya vencieron

Umbrales:
  - 60 días: "Primer contacto de renovación"
  - 30 días: "Seguimiento urgente de renovación"
  - 15 días: "Renovación crítica — vence en 15 días"
  -  0 días: marcar contrato como expired

Ejecutar:
    python manage.py contract_renewal_tasks
    python manage.py contract_renewal_tasks --dry-run
    python manage.py contract_renewal_tasks --force   (crea aunque ya exista tarea)
"""
from __future__ import annotations

import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()

THRESHOLDS = [
    (60, "Primer contacto renovación — {num} ({client}) vence en {days} días"),
    (30, "Seguimiento urgente — contrato {num} vence en {days} días"),
    (15, "RENOVACIÓN CRÍTICA — contrato {num} ({client}) vence en {days} días"),
]


def _asesora_for_lead(lead, fallback_user):
    """
    Devuelve el usuario asignado a la cotización más reciente activa del lead.
    Si no hay asignación, devuelve fallback_user.
    """
    from apps.leads.models import Quote
    quote = (
        Quote.objects
        .filter(lead=lead, assigned_to__isnull=False)
        .order_by("-created_at")
        .select_related("assigned_to")
        .first()
    )
    if quote and quote.assigned_to and quote.assigned_to.is_active:
        return quote.assigned_to
    return fallback_user


class Command(BaseCommand):
    help = "Crea tareas y notificaciones de renovación de contratos por asesora"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Muestra sin crear")
        parser.add_argument("--force",   action="store_true", help="Crea aunque ya exista")

    def handle(self, *args, **options):
        from apps.leads.models import RentalContract, FollowUpTask
        from apps.dashboard.models import Notification

        dry   = options["dry_run"]
        force = options["force"]
        today = datetime.date.today()

        tasks_created   = 0
        notifs_created  = 0
        expired_marked  = 0

        default_user = User.objects.filter(is_superuser=True, is_active=True).first()

        active_contracts = (
            RentalContract.objects
            .filter(status="active", end_date__isnull=False)
            .select_related("lead")
        )

        for contract in active_contracts:
            days_left = (contract.end_date - today).days
            lead      = contract.lead
            asesora   = _asesora_for_lead(lead, default_user) if lead else default_user

            # ── Contrato ya vencido ──────────────────────────────────────
            if days_left < 0:
                if not dry:
                    contract.status = "expired"
                    contract.save(update_fields=["status"])
                expired_marked += 1
                self.stdout.write(f"  [EXPIRED] {contract.contract_number}")
                continue

            # ── Umbrales ─────────────────────────────────────────────────
            for threshold, desc_tpl in THRESHOLDS:
                if days_left != threshold:
                    continue

                desc = desc_tpl.format(
                    num    = contract.contract_number,
                    client = lead.full_name if lead else "—",
                    days   = days_left,
                )
                task_due = today + datetime.timedelta(days=1)

                already_exists = (
                    not force and
                    FollowUpTask.objects.filter(
                        lead=lead,
                        description__startswith=desc[:40],
                        is_done=False,
                    ).exists()
                )

                if not already_exists:
                    if dry:
                        self.stdout.write(
                            f"  [DRY TAREA] → {asesora.username if asesora else '—'} | {desc[:70]}"
                        )
                    else:
                        FollowUpTask.objects.create(
                            lead        = lead,
                            assigned_to = asesora,
                            due_date    = task_due,
                            description = desc,
                        )
                    tasks_created += 1

                # Notificación personalizada a la asesora (no a todo el equipo)
                notif_title = f"Renovación: {contract.contract_number} vence en {days_left} días"
                link        = f"/panel/contratos/"

                if asesora:
                    if dry:
                        self.stdout.write(
                            f"  [DRY NOTIF] → {asesora.username} | {notif_title}"
                        )
                        notifs_created += 1
                    else:
                        Notification.push(
                            user    = asesora,
                            type    = Notification.Type.CONTRACT_RENEWAL,
                            title   = notif_title,
                            message = f"Cliente: {lead.full_name if lead else '—'}",
                            link    = link,
                        )
                        notifs_created += 1

                # Notificar también al superusuario si es diferente a la asesora
                if default_user and default_user != asesora:
                    admin_title = f"[Admin] Renovación: {contract.contract_number} ({days_left}d) — asesora {asesora.get_full_name() if asesora else '—'}"
                    if not dry:
                        Notification.push(
                            user    = default_user,
                            type    = Notification.Type.CONTRACT_RENEWAL,
                            title   = admin_title,
                            message = f"Cliente: {lead.full_name if lead else '—'}",
                            link    = f"/dashadmin/contratos/{contract.pk}/",
                        )
                        notifs_created += 1

        # ── Contratos activos que ya vencieron (lote) ────────────────────
        past_due = RentalContract.objects.filter(
            status="active", end_date__lt=today
        )
        if not dry:
            count = past_due.count()
            past_due.update(status="expired")
            expired_marked += count

        mode = "[DRY RUN] " if dry else ""
        self.stdout.write(self.style.SUCCESS(
            f"{mode}Tareas: {tasks_created} | "
            f"Notificaciones: {notifs_created} | "
            f"Contratos expirados: {expired_marked}"
        ))
