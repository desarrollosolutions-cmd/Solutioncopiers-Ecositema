"""
Management command: alerta de consumibles con stock bajo o agotado.

Uso:
    python manage.py check_stock_alerts
    python manage.py check_stock_alerts --threshold 3  (umbral personalizado)
    python manage.py check_stock_alerts --dry-run

Programar en Windows Task Scheduler:
    Programa : python
    Argumentos: C:\\ruta\\manage.py check_stock_alerts
    Hora: 9:00 AM diariamente

Programar en cron (Linux):
    0 9 * * * /venv/bin/python /ruta/manage.py check_stock_alerts
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 5   # unidades — por debajo de esto se considera stock bajo


class Command(BaseCommand):
    help = "Envía alerta interna cuando el stock de consumibles está bajo o agotado."

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold",
            type=int,
            default=DEFAULT_THRESHOLD,
            help=f"Umbral de stock bajo (default: {DEFAULT_THRESHOLD})",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué alertas se enviarían sin enviarlas.",
        )

    def handle(self, *args, **options):
        from apps.catalog.models import Consumable
        from apps.leads.services import _send_email_async

        dry_run = options["dry_run"]
        threshold = options["threshold"]

        if dry_run:
            self.stdout.write(self.style.WARNING("-- DRY RUN --"))

        out_of_stock = list(
            Consumable.objects.filter(status="published", stock_quantity=0)
            .order_by("name")
            .values("id", "name", "part_number", "stock_quantity")
        )
        low_stock = list(
            Consumable.objects.filter(
                status="published",
                stock_quantity__gt=0,
                stock_quantity__lte=threshold,
            )
            .order_by("stock_quantity", "name")
            .values("id", "name", "part_number", "stock_quantity")
        )

        total = len(out_of_stock) + len(low_stock)
        if total == 0:
            self.stdout.write(self.style.SUCCESS("OK Sin alertas de stock."))
            return

        # Construir email
        lines = ["<h3 style='font-family:sans-serif'>⚠️ Alerta de Stock — Solution Copiers</h3>"]

        if out_of_stock:
            lines.append(f"<h4 style='color:#dc2626'>Agotados ({len(out_of_stock)})</h4><ul>")
            for item in out_of_stock:
                ref = f" [{item['part_number']}]" if item["part_number"] else ""
                lines.append(f"<li><b>{item['name']}{ref}</b> — 0 unidades</li>")
                self.stdout.write(self.style.ERROR(f"  AGOTADO: {item['name']}"))
            lines.append("</ul>")

        if low_stock:
            lines.append(f"<h4 style='color:#d97706'>Stock bajo (≤{threshold} unidades) — {len(low_stock)}</h4><ul>")
            for item in low_stock:
                ref = f" [{item['part_number']}]" if item["part_number"] else ""
                lines.append(
                    f"<li>{item['name']}{ref} — <b>{item['stock_quantity']} uds.</b></li>"
                )
                self.stdout.write(
                    self.style.WARNING(f"  BAJO: {item['name']} ({item['stock_quantity']} uds.)")
                )
            lines.append("</ul>")

        stock_url = getattr(settings, "SITE_URL", "") + "/dashadmin/stock/"
        lines.append(
            f"<p style='font-family:sans-serif'>"
            f"<a href='{stock_url}'>→ Gestionar stock en el panel</a></p>"
        )

        notify_email = getattr(settings, "LEADS_NOTIFICATION_EMAIL", "")
        if not notify_email:
            self.stdout.write(self.style.WARNING("LEADS_NOTIFICATION_EMAIL no configurado — email omitido."))
        elif not dry_run:
            _send_email_async(
                f"⚠️ Stock: {len(out_of_stock)} agotados, {len(low_stock)} bajos — Solution Copiers",
                "<div>" + "".join(lines) + "</div>",
                [notify_email],
            )
            self.stdout.write(self.style.SUCCESS(f"Email de alerta enviado a {notify_email}."))

        self.stdout.write(
            self.style.SUCCESS(
                f"OK {total} alertas: {len(out_of_stock)} agotados, {len(low_stock)} con stock bajo."
            )
        )
        logger.info(
            "check_stock_alerts: %d agotados, %d bajos (umbral=%d)",
            len(out_of_stock), len(low_stock), threshold,
        )
