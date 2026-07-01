"""
Auto-asignación de leads no asignados entre las asesoras activas.
Distribución round-robin: cada asesora recibe un turno igualitario.

Ejecutar:
    python manage.py assign_leads_roundrobin
    python manage.py assign_leads_roundrobin --dry-run
    python manage.py assign_leads_roundrobin --group asesor_comercial

Criterios:
  - Solo asesoras activas con permiso panel_clientes o en grupo asesor_comercial
  - Cotizaciones con status="new" y assigned_to=None
  - Se asignan en orden por fecha de creación (primero entra, primero asignado)
  - Turno round-robin basado en cantidad actual de cotizaciones asignadas (menor primero)
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


def _get_assignable_users(group_name: str):
    from django.contrib.auth.models import Permission, Group
    try:
        perm = Permission.objects.get(codename="panel_clientes")
    except Permission.DoesNotExist:
        perm = None

    users = User.objects.filter(is_active=True, is_staff=False)
    if group_name:
        try:
            g = Group.objects.get(name=group_name)
            users = users.filter(groups=g)
        except Group.DoesNotExist:
            pass
    elif perm:
        users = users.filter(user_permissions=perm)

    return list(users.distinct())


class Command(BaseCommand):
    help = "Asigna cotizaciones sin asesora en round-robin"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--group", type=str, default="asesor_comercial",
                            help="Nombre del grupo Django a usar (default: asesor_comercial)")

    def handle(self, *args, **options):
        from apps.leads.models import Quote
        from apps.dashboard.models import Notification
        from django.db.models import Count

        dry = options["dry_run"]
        group_name = options["group"]

        assignees = _get_assignable_users(group_name)
        if not assignees:
            self.stdout.write(self.style.WARNING(
                f"No hay asesoras activas en el grupo '{group_name}'. Saliendo."
            ))
            return

        # Cotizaciones sin asignar
        unassigned = Quote.objects.filter(
            status="new", assigned_to__isnull=True
        ).order_by("created_at")

        total = unassigned.count()
        if total == 0:
            self.stdout.write("No hay cotizaciones sin asignar.")
            return

        # Carga de trabajo actual por asesora
        workload = {
            u.pk: Quote.objects.filter(assigned_to=u, status__in=["new", "reviewing", "sent"]).count()
            for u in assignees
        }

        assigned_count = 0
        for quote in unassigned:
            # Asignar a la asesora con menor carga
            assignee = min(assignees, key=lambda u: workload[u.pk])

            if dry:
                self.stdout.write(
                    f"  [DRY] Cotización #{quote.pk} → {assignee.get_full_name() or assignee.username}"
                )
            else:
                quote.assigned_to = assignee
                quote.save(update_fields=["assigned_to"])

                # Notificación a la asesora
                Notification.push(
                    user=assignee,
                    type=Notification.Type.TASK_ASSIGNED,
                    title=f"Nueva cotización asignada #{quote.pk}",
                    message=f"Cliente: {quote.lead.full_name if quote.lead else '—'}",
                    link=f"/panel/cotizaciones/{quote.pk}/",
                )

            workload[assignee.pk] += 1
            assigned_count += 1

        mode = "[DRY RUN] " if dry else ""
        self.stdout.write(self.style.SUCCESS(
            f"{mode}Cotizaciones asignadas: {assigned_count} entre {len(assignees)} asesora(s)"
        ))
        for u in assignees:
            self.stdout.write(
                f"  {u.get_full_name() or u.username:30s} -> carga final: {workload[u.pk]}"
            )
