from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.models import Q


class Command(BaseCommand):
    help = "Pruebas de la matriz de permisos unificada"

    def handle(self, *args, **options):
        from apps.dashboard.models import FieldUser, PANEL_ROLES
        from apps.dashboard.views import _sync_employee_perms

        ok = True

        # PRUEBA 1: technician_list SOLO tecnicos de campo (no staff)
        self.stdout.write("\n== PRUEBA 1: technician_list solo role=tecnico ==")
        techs = list(User.objects.filter(field_profile__role="tecnico"))
        names = [f"{u.username}(staff={u.is_staff})" for u in techs]
        self.stdout.write(f"   Tecnicos: {names}")
        staff_in_list = [u for u in techs if u.is_staff]
        if any(u.username == "daniel" for u in techs) and not staff_in_list:
            self.stdout.write(self.style.SUCCESS("   PASS: solo tecnicos de campo, sin staff"))
        else:
            self.stdout.write(self.style.ERROR("   FAIL"))
            ok = False

        # PRUEBA 2: PANEL_ROLES tecnico solo tiene panel_tickets
        self.stdout.write("\n== PRUEBA 2: PANEL_ROLES tecnico = [panel_tickets] ==")
        tecnico_role = next(r for r in PANEL_ROLES if r["key"] == "tecnico")
        self.stdout.write(f"   tecnico perms: {tecnico_role['perms']}")
        if tecnico_role["perms"] == ["panel_tickets"]:
            self.stdout.write(self.style.SUCCESS("   PASS"))
        else:
            self.stdout.write(self.style.ERROR("   FAIL: tecnico tiene perms extra"))
            ok = False

        # PRUEBA 3: PANEL_ROLES asesora incluye panel_tickets
        self.stdout.write("\n== PRUEBA 3: PANEL_ROLES asesora incluye panel_tickets ==")
        asesora_role = next(r for r in PANEL_ROLES if r["key"] == "asesora")
        self.stdout.write(f"   asesora perms: {asesora_role['perms']}")
        if "panel_tickets" in asesora_role["perms"] and "panel_facturacion" in asesora_role["perms"]:
            self.stdout.write(self.style.SUCCESS("   PASS"))
        else:
            self.stdout.write(self.style.ERROR("   FAIL: asesora no tiene todos los perms requeridos"))
            ok = False

        # PRUEBA 4: ajustar daniel a solo panel_tickets y verificar
        self.stdout.write("\n== PRUEBA 4: daniel tiene solo panel_tickets ==")
        daniel = User.objects.get(username="daniel")
        _sync_employee_perms(daniel, ["panel_tickets"])
        daniel = User.objects.get(username="daniel")
        perms = list(daniel.user_permissions.values_list("codename", flat=True))
        self.stdout.write(f"   daniel perms: {perms}")
        if perms == ["panel_tickets"]:
            self.stdout.write(self.style.SUCCESS("   PASS"))
        else:
            self.stdout.write(self.style.ERROR(f"   FAIL: esperaba [panel_tickets], tiene {perms}"))
            ok = False

        # PRUEBA 5: mensajero sin perms
        self.stdout.write("\n== PRUEBA 5: mensajero sin perms ==")
        try:
            mateito = User.objects.get(username="mateito")
            _sync_employee_perms(mateito, [])
            mateito = User.objects.get(username="mateito")
            perms = list(mateito.user_permissions.values_list("codename", flat=True))
            if perms == []:
                self.stdout.write(self.style.SUCCESS(f"   PASS: mateito sin perms"))
            else:
                self.stdout.write(self.style.ERROR(f"   FAIL: {perms}"))
                ok = False
        except User.DoesNotExist:
            self.stdout.write("   SKIP: mateito no existe")

        # PRUEBA 6: daniel puede acceder a /panel/ (cumple panel_required)
        self.stdout.write("\n== PRUEBA 6: daniel cumple panel_required ==")
        daniel = User.objects.get(username="daniel")
        if not daniel.is_staff and daniel.is_active:
            self.stdout.write(self.style.SUCCESS(f"   PASS: is_staff={daniel.is_staff} is_active={daniel.is_active}"))
        else:
            self.stdout.write(self.style.ERROR("   FAIL"))
            ok = False

        # PRUEBA 7: daniel mantiene FieldUser para campo
        self.stdout.write("\n== PRUEBA 7: daniel mantiene FieldUser ==")
        try:
            fp = daniel.field_profile
            self.stdout.write(self.style.SUCCESS(f"   PASS: role={fp.role}"))
        except FieldUser.DoesNotExist:
            self.stdout.write(self.style.ERROR("   FAIL"))
            ok = False

        self.stdout.write("")
        if ok:
            self.stdout.write(self.style.SUCCESS("=== TODAS LAS PRUEBAS PASARON ==="))
        else:
            self.stdout.write(self.style.ERROR("=== ALGUNAS PRUEBAS FALLARON ==="))
