"""
Crea (o actualiza) los grupos de permisos CRM:

  asesor_comercial — Lead / Quote / LeadActivity / FollowUpTask: view + add + change
  tecnico          — ServiceTicket / RentalContract: view + add + change
  supervisor       — todo lo anterior + delete en todos los modelos anteriores

Uso:
    python manage.py setup_crm_roles
"""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


def _perms(app_label, model, actions):
    """Devuelve queryset de Permission para un modelo y lista de acciones."""
    try:
        ct = ContentType.objects.get(app_label=app_label, model=model)
    except ContentType.DoesNotExist:
        return Permission.objects.none()
    return Permission.objects.filter(content_type=ct, codename__in=[
        f"{action}_{model}" for action in actions
    ])


class Command(BaseCommand):
    help = "Crea grupos de permisos CRM: asesor_comercial, tecnico, supervisor"

    def handle(self, *args, **options):
        self._setup_asesor()
        self._setup_tecnico()
        self._setup_supervisor()
        self.stdout.write(self.style.SUCCESS("Grupos CRM configurados correctamente."))

    # ------------------------------------------------------------------
    def _setup_asesor(self):
        group, _ = Group.objects.get_or_create(name="asesor_comercial")
        perms = Permission.objects.none()
        for model in ("lead", "quote", "leadactivity", "followuptask"):
            perms |= _perms("leads", model, ["view", "add", "change"])
        group.permissions.set(perms)
        self.stdout.write(f"  asesor_comercial: {perms.count()} permisos")

    def _setup_tecnico(self):
        group, _ = Group.objects.get_or_create(name="tecnico")
        perms = Permission.objects.none()
        for model in ("serviceticket", "rentalcontract"):
            perms |= _perms("leads", model, ["view", "add", "change"])
        group.permissions.set(perms)
        self.stdout.write(f"  tecnico: {perms.count()} permisos")

    def _setup_supervisor(self):
        group, _ = Group.objects.get_or_create(name="supervisor")
        perms = Permission.objects.none()
        asesor_models = ("lead", "quote", "leadactivity", "followuptask")
        tecnico_models = ("serviceticket", "rentalcontract")
        for model in asesor_models + tecnico_models:
            perms |= _perms("leads", model, ["view", "add", "change", "delete"])
        group.permissions.set(perms)
        self.stdout.write(f"  supervisor: {perms.count()} permisos")
