"""
Genera notificaciones CRM internas para todos los usuarios staff.

Ejecutar manualmente:
    python manage.py generate_notifications

Configurar en un cron/celery para correr diariamente, ej: 08:00.

Lógica:
  - Tareas vencidas:        LeadTask con due_date < hoy y completed=False
  - Contratos por vencer:   RentalContract activo con end_date en <= 30 días
  - Cotizaciones sin atender: Quote status="new" creada hace > 48 h sin asignada
  - Leads fríos:            Lead sin actividad en los últimos 14 días (tiene Quote abierta)
"""
from __future__ import annotations

import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = "Genera notificaciones CRM internas para el equipo"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Mostrar sin crear")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        total = 0

        staff_users = list(User.objects.filter(is_staff=True, is_active=True))
        if not staff_users:
            self.stdout.write("No hay usuarios staff activos.")
            return

        total += self._overdue_tasks(staff_users, dry)
        total += self._expiring_contracts(staff_users, dry)
        total += self._stale_quotes(staff_users, dry)
        total += self._cold_leads(staff_users, dry)

        mode = "[DRY RUN] " if dry else ""
        self.stdout.write(self.style.SUCCESS(f"{mode}Notificaciones generadas: {total}"))

    # ------------------------------------------------------------------
    def _overdue_tasks(self, users, dry) -> int:
        from apps.leads.models import FollowUpTask
        from apps.dashboard.models import Notification

        today = datetime.date.today()
        tasks = FollowUpTask.objects.filter(
            due_date__lt=today, is_done=False
        ).select_related("lead", "assigned_to")

        created = 0
        for task in tasks:
            short = (task.description[:55] + "...") if len(task.description) > 55 else task.description
            title = f"Tarea vencida: {short}"
            link = f"/dashadmin/clientes/{task.lead_id}/" if task.lead_id else ""
            for user in users:
                if dry:
                    self.stdout.write(f"  [DRY] {user.username} <- {title}")
                    created += 1
                else:
                    Notification.push(
                        user=user,
                        type=Notification.Type.TASK_OVERDUE,
                        title=title,
                        message=f"Vencio el {task.due_date:%d/%m/%Y}" if task.due_date else "",
                        link=link,
                    )
                    created += 1
        return created

    # ------------------------------------------------------------------
    def _expiring_contracts(self, users, dry) -> int:
        from apps.leads.models import RentalContract
        from apps.dashboard.models import Notification

        today = datetime.date.today()
        threshold = today + datetime.timedelta(days=30)
        contracts = RentalContract.objects.filter(
            status="active", end_date__range=(today, threshold)
        ).select_related("lead")

        created = 0
        for contract in contracts:
            days_left = (contract.end_date - today).days
            title = f"Contrato {contract.contract_number} vence en {days_left} días"
            link = f"/dashadmin/contratos/{contract.pk}/"
            msg = f"Cliente: {contract.lead.full_name if contract.lead else ''}"
            for user in users:
                if dry:
                    self.stdout.write(f"  [DRY] {user.username} <- {title}")
                    created += 1
                else:
                    Notification.push(
                        user=user,
                        type=Notification.Type.CONTRACT_EXPIRING,
                        title=title,
                        message=msg,
                        link=link,
                    )
                    created += 1
        return created

    # ------------------------------------------------------------------
    def _stale_quotes(self, users, dry) -> int:
        from apps.leads.models import Quote
        from apps.dashboard.models import Notification

        cutoff = timezone.now() - datetime.timedelta(hours=48)
        quotes = Quote.objects.filter(
            status="new", created_at__lte=cutoff
        ).select_related("lead")[:50]

        created = 0
        for quote in quotes:
            days = (timezone.now() - quote.created_at).days
            title = f"Cotización #{quote.pk} sin atender ({days} días)"
            link = f"/dashadmin/cotizaciones/{quote.pk}/"
            msg = f"Cliente: {quote.lead.full_name if quote.lead else ''}"
            for user in users:
                if dry:
                    self.stdout.write(f"  [DRY] {user.username} <- {title}")
                    created += 1
                else:
                    Notification.push(
                        user=user,
                        type=Notification.Type.QUOTE_STALE,
                        title=title,
                        message=msg,
                        link=link,
                    )
                    created += 1
        return created

    # ------------------------------------------------------------------
    def _cold_leads(self, users, dry) -> int:
        from apps.leads.models import Lead, Quote
        from apps.dashboard.models import Notification

        cutoff = timezone.now() - datetime.timedelta(days=14)

        # Leads con cotizaciones abiertas pero sin actividad en 14 días
        open_quote_lead_ids = set(
            Quote.objects.filter(status__in=["new", "sent"])
            .values_list("lead_id", flat=True)
        )
        cold_leads = Lead.objects.filter(
            pk__in=open_quote_lead_ids,
            updated_at__lte=cutoff,
        ).order_by("updated_at")[:30]

        created = 0
        for lead in cold_leads:
            days = (timezone.now() - lead.updated_at).days
            title = f"Lead frío: {lead.full_name[:50]} ({days} días sin actividad)"
            link = f"/dashadmin/clientes/{lead.pk}/"
            for user in users:
                if dry:
                    self.stdout.write(f"  [DRY] {user.username} <- {title}")
                    created += 1
                else:
                    Notification.push(
                        user=user,
                        type=Notification.Type.LEAD_COLD,
                        title=title,
                        link=link,
                    )
                    created += 1
        return created
