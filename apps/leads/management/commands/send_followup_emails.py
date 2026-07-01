"""
Management command: envía alertas diarias de seguimiento y contratos por vencer.

Uso:
    python manage.py send_followup_emails
    python manage.py send_followup_emails --dry-run

═══════════════════════════════════════════════════════
PROGRAMACIÓN AUTOMÁTICA — WINDOWS TASK SCHEDULER
═══════════════════════════════════════════════════════

1. Abrir: Inicio → "Programador de tareas" → Crear tarea básica
2. Nombre: Solution Copiers — Alertas Diarias
3. Desencadenador: Diariamente a las 08:00 a.m.
4. Acción: Iniciar un programa
   Programa/script : C:\\ruta\\al\\venv\\Scripts\\python.exe
   Argumentos      : C:\\ruta\\al\\proyecto\\manage.py send_followup_emails
   Iniciar en      : C:\\ruta\\al\\proyecto
5. Repetir para check_stock_alerts a las 09:00 a.m.

O con PowerShell (ejecutar como administrador):
    $action  = New-ScheduledTaskAction -Execute 'C:\\venv\\Scripts\\python.exe' `
                 -Argument 'C:\\proyecto\\manage.py send_followup_emails' `
                 -WorkingDirectory 'C:\\proyecto'
    $trigger = New-ScheduledTaskTrigger -Daily -At 8am
    Register-ScheduledTask -TaskName 'SC-Followup' -Action $action -Trigger $trigger -RunLevel Highest

Cron (Linux/Mac):
    0 8 * * * /venv/bin/python /proyecto/manage.py send_followup_emails
    0 9 * * * /venv/bin/python /proyecto/manage.py check_stock_alerts
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)

FOLLOWUP_DAYS = 3   # días en estado "new" antes de enviar alerta
EXPIRY_DAYS   = [30, 7]  # días antes del vencimiento para alertar


class Command(BaseCommand):
    help = "Envía alertas automáticas de seguimiento de cotizaciones y contratos por vencer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué emails se enviarían sin enviarlos realmente.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("-- DRY RUN - no se enviaran emails reales --"))

        total_sent = 0
        total_sent += self._check_followups(dry_run)
        total_sent += self._check_contract_expiries(dry_run)

        msg = f"OK Completado: {total_sent} notificaciones {'que se enviarian' if dry_run else 'enviadas'}."
        self.stdout.write(self.style.SUCCESS(msg))
        logger.info(msg)

    # ------------------------------------------------------------------
    def _check_followups(self, dry_run: bool) -> int:
        from apps.leads.models import Quote
        from apps.leads.services import send_followup_email

        cutoff = timezone.now() - timedelta(days=FOLLOWUP_DAYS)
        pending_quotes = Quote.objects.filter(
            status="new",
            created_at__lte=cutoff,
        ).select_related("lead")

        count = 0
        for quote in pending_quotes:
            days = (timezone.now() - quote.created_at).days
            label = f"Cotización #{quote.pk} de {quote.lead.full_name} ({days} días)"
            if dry_run:
                self.stdout.write(f"  [followup] {label}")
            else:
                send_followup_email(quote, days)
                self.stdout.write(f"  → Followup enviado: {label}")
            count += 1

        self.stdout.write(f"Seguimientos pendientes: {count}")
        return count

    # ------------------------------------------------------------------
    def _check_contract_expiries(self, dry_run: bool) -> int:
        from apps.leads.models import RentalContract
        from apps.leads.services import send_contract_expiry_email

        today = date.today()
        count = 0

        for threshold in EXPIRY_DAYS:
            target_date = today + timedelta(days=threshold)
            contracts = RentalContract.objects.filter(
                status="active",
                end_date=target_date,
            ).select_related("lead")

            for contract in contracts:
                label = f"{contract.contract_number} — {contract.lead.full_name} ({threshold} días)"
                if dry_run:
                    self.stdout.write(f"  [expiry-{threshold}d] {label}")
                else:
                    send_contract_expiry_email(contract, threshold)
                    self.stdout.write(f"  → Alerta vencimiento enviada: {label}")
                count += 1

        self.stdout.write(f"Contratos por vencer: {count}")
        return count
