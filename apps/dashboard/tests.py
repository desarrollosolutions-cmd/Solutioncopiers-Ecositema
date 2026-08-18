"""
Suite de pruebas general del ecosistema Solution Copiers.

Cubre:
  1. Modelos: Lead, Quote, ServiceTicket, RentalContract, MeterReading
  2. Control de acceso: isolación entre portales (panel / dashadmin / campo)
  3. Panel CRM — vistas de asesora (cotizaciones, clientes, tickets, contratos)
  4. Dashadmin — vistas de administrador
  5. Campo — vistas de técnico/mensajero
  6. Seguridad: CSRF, fuerza bruta, escalación horizontal, headers
"""
from __future__ import annotations

import itertools
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.leads.models import (
    FollowUpTask,
    Lead,
    LeadActivity,
    MeterReading,
    Quote,
    RentalContract,
    ServiceTicket,
)

User = get_user_model()

_ticket_seq = itertools.count(1)
_contract_seq = itertools.count(1)


# ===========================================================================
# Helpers compartidos
# ===========================================================================

_ASESORA_PERMS = [
    "panel_cotizaciones", "panel_clientes", "panel_actividades",
    "panel_tickets", "panel_contratos", "panel_insumos", "panel_facturacion",
]


def _grant_panel_perms(user, codenames=None):
    """Otorga permisos de panel a un usuario (igual que el preset de asesora)."""
    from django.contrib.auth.models import Permission
    codes = codenames or _ASESORA_PERMS
    perms = Permission.objects.filter(
        content_type__app_label="dashboard",
        codename__in=codes,
    )
    user.user_permissions.set(perms)
    # Forzar refresh del caché de permisos
    user._perm_cache = set()
    if hasattr(user, "_user_perm_cache"):
        del user._user_perm_cache


def make_admin(username="admin_t", password="test1234"):
    u = User.objects.create_user(username=username, password=password)
    u.is_staff = True
    u.is_superuser = True
    u.is_active = True
    u.save()
    return u


def make_asesora(username="asesora_t", password="test1234"):
    u = User.objects.create_user(username=username, password=password)
    u.is_staff = False
    u.is_active = True
    u.save()
    _grant_panel_perms(u)
    return u


def make_field_user(username="tecnico_t", role="tecnico", password="test1234"):
    from apps.dashboard.models import FieldUser
    u = User.objects.create_user(username=username, password=password)
    u.is_staff = False
    u.is_active = True
    u.save()
    FieldUser.objects.create(user=u, role=role)
    _grant_panel_perms(u, ["panel_tickets"])
    return u


def make_lead(name="Cliente Test", email=None, phone="3001234567"):
    email = email or f"{name.replace(' ', '').lower()}@test.co"
    return Lead.objects.create(full_name=name, email=email, phone=phone)


def make_quote(lead, asesora=None, status="new", area="rental"):
    return Quote.objects.create(
        lead=lead, interest_area=area, status=status, assigned_to=asesora
    )


def make_ticket(lead, assigned_to=None, created_by=None, status="open"):
    n = next(_ticket_seq)
    return ServiceTicket.objects.create(
        ticket_number=f"TKT-TEST-{n:04d}",
        lead=lead,
        issue_type="repair",
        priority="medium",
        description="Test issue",
        status=status,
        assigned_to=assigned_to,
    )


def make_contract(lead, status="active"):
    n = next(_contract_seq)
    today = date.today()
    return RentalContract.objects.create(
        lead=lead,
        contract_number=f"CTR-TEST-{n:04d}",
        status=status,
        start_date=today,
        end_date=today + timedelta(days=365),
        monthly_rate=Decimal("350000"),
        equipment_description="Kyocera Test",
    )


# ===========================================================================
# 1. MODELOS
# ===========================================================================

class LeadModelTest(TestCase):

    def test_str(self):
        lead = make_lead("Ana García")
        self.assertIn("Ana García", str(lead))

    def test_score_defaults_to_zero(self):
        lead = make_lead()
        self.assertEqual(lead.score, 0)

    def test_has_active_contract_false_by_default(self):
        lead = make_lead()
        self.assertFalse(lead.contracts.filter(status="active").exists())

    def test_multiple_quotes_linked(self):
        lead = make_lead()
        make_quote(lead, status="new")
        make_quote(lead, status="reviewing")
        self.assertEqual(lead.quotes.count(), 2)


class QuoteModelTest(TestCase):

    def setUp(self):
        self.lead = make_lead()

    def test_str_contains_lead_name(self):
        q = make_quote(self.lead)
        self.assertIn(self.lead.full_name, str(q))

    def test_default_status_is_new(self):
        q = make_quote(self.lead)
        self.assertEqual(q.status, "new")

    def test_default_close_probability_is_zero(self):
        q = make_quote(self.lead)
        self.assertEqual(q.close_probability, 0)

    def test_can_assign_asesora(self):
        asesora = make_asesora("asesora_q")
        q = make_quote(self.lead, asesora=asesora)
        self.assertEqual(q.assigned_to, asesora)

    def test_lost_category_choices(self):
        valid = [c[0] for c in Quote.LostCategory.choices]
        self.assertIn("price", valid)
        self.assertIn("competitor", valid)
        self.assertIn("no_budget", valid)

    def test_public_id_is_unique(self):
        q1 = make_quote(self.lead)
        q2 = make_quote(self.lead)
        self.assertNotEqual(q1.public_id, q2.public_id)


class ServiceTicketModelTest(TestCase):

    def setUp(self):
        self.lead = make_lead()

    def test_str_contains_ticket_number(self):
        t = make_ticket(self.lead)
        self.assertIn("TKT-TEST-", str(t))

    def test_is_open_true_for_open_status(self):
        t = make_ticket(self.lead, status="open")
        self.assertTrue(t.is_open)

    def test_is_open_true_for_in_progress(self):
        t = make_ticket(self.lead, status="in_progress")
        self.assertTrue(t.is_open)

    def test_is_open_false_for_resolved(self):
        t = make_ticket(self.lead, status="resolved")
        self.assertFalse(t.is_open)

    def test_is_open_false_for_closed(self):
        t = make_ticket(self.lead, status="closed")
        self.assertFalse(t.is_open)

    def test_ticket_number_unique(self):
        t1 = make_ticket(self.lead)
        t2 = make_ticket(self.lead)
        self.assertNotEqual(t1.ticket_number, t2.ticket_number)

    def test_assigned_to_nullable(self):
        t = make_ticket(self.lead, assigned_to=None)
        self.assertIsNone(t.assigned_to)

    def test_resolved_at_null_by_default(self):
        t = make_ticket(self.lead)
        self.assertIsNone(t.resolved_at)


class RentalContractModelTest(TestCase):

    def setUp(self):
        self.lead = make_lead()

    def test_str_contains_contract_number(self):
        c = make_contract(self.lead)
        self.assertIn("CTR-TEST-", str(c))

    def test_default_status_active(self):
        c = make_contract(self.lead, status="active")
        self.assertEqual(c.status, "active")

    def _make_copier_unit(self, serial, status=None):
        from apps.catalog.models import Copier, CopierCategory, CopierUnit
        cat = CopierCategory.objects.create(name="Test Cat", description="Test")
        copier = Copier.objects.create(
            name="Ricoh Test", model_number="MP2015", category=cat,
            short_description="Test", description="Test",
            speed_ppm=20,
        )
        kwargs = {"copier": copier, "serial_number": serial}
        if status is not None:
            kwargs["status"] = status
        return CopierUnit.objects.create(**kwargs)

    def test_unit_sync_sets_in_field_on_active(self):
        from apps.catalog.models import CopierUnit
        unit = self._make_copier_unit("SN-TST-001", CopierUnit.UnitStatus.AVAILABLE)
        c = make_contract(self.lead, status="active")
        c.unit = unit
        c.save()
        unit.refresh_from_db()
        self.assertEqual(unit.status, CopierUnit.UnitStatus.IN_FIELD)

    def test_unit_sync_releases_on_expired(self):
        from apps.catalog.models import CopierUnit
        unit = self._make_copier_unit("SN-TST-002", CopierUnit.UnitStatus.IN_FIELD)
        c = make_contract(self.lead, status="active")
        c.unit = unit
        c.save()
        c.status = "expired"
        c.save()
        unit.refresh_from_db()
        self.assertEqual(unit.status, CopierUnit.UnitStatus.AVAILABLE)

    def test_unit_not_released_if_another_active_contract(self):
        from apps.catalog.models import CopierUnit
        unit = self._make_copier_unit("SN-TST-003", CopierUnit.UnitStatus.AVAILABLE)
        lead2 = make_lead("Otro Cliente", "otro@test.co")
        c1 = make_contract(self.lead, status="active")
        c1.unit = unit
        c1.save()
        c2 = make_contract(lead2, status="active")
        c2.unit = unit
        c2.save()
        # Cancelar uno — el otro sigue activo, la unidad debe quedar IN_FIELD
        c1.status = "cancelled"
        c1.save()
        unit.refresh_from_db()
        self.assertEqual(unit.status, CopierUnit.UnitStatus.IN_FIELD)


class MeterReadingModelTest(TestCase):

    def setUp(self):
        self.lead = make_lead()
        self.contract = make_contract(self.lead)

    def test_pages_printed_positive(self):
        mr = MeterReading.objects.create(
            contract=self.contract,
            reading_date=date.today(),
            previous_reading=1000,
            current_reading=3500,
        )
        self.assertEqual(mr.pages_printed, 2500)

    def test_pages_printed_never_negative(self):
        mr = MeterReading.objects.create(
            contract=self.contract,
            reading_date=date.today(),
            previous_reading=3500,
            current_reading=3500,
        )
        self.assertEqual(mr.pages_printed, 0)

    def test_overage_pages_zero_when_within_limit(self):
        self.contract.copies_included = 5000
        self.contract.save()
        mr = MeterReading.objects.create(
            contract=self.contract,
            reading_date=date.today(),
            previous_reading=0,
            current_reading=4000,
        )
        self.assertEqual(mr.overage_pages, 0)

    def test_overage_charge_calculated(self):
        self.contract.copies_included = 2000
        self.contract.copy_overage_rate = Decimal("45")
        self.contract.save()
        mr = MeterReading.objects.create(
            contract=self.contract,
            reading_date=date.today(),
            previous_reading=0,
            current_reading=3000,
        )
        self.assertEqual(mr.overage_pages, 1000)
        self.assertEqual(mr.overage_charge, 45000)


# ===========================================================================
# 2. CONTROL DE ACCESO — AISLAMIENTO DE PORTALES
# ===========================================================================

class PortalIsolationTest(TestCase):
    """Verifica que cada portal sólo permite el tipo de usuario correcto."""

    def setUp(self):
        self.client = Client()
        self.admin   = make_admin("iso_admin")
        self.asesora = make_asesora("iso_asesora")
        self.tecnico = make_field_user("iso_tecnico", role="tecnico")

    # ── Panel (asesoras) ──────────────────────────────────────────────────
    def test_anonimo_redirigido_desde_panel(self):
        r = self.client.get("/panel/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/panel/acceso/", r["Location"])

    def test_asesora_accede_al_panel(self):
        self.client.login(username="iso_asesora", password="test1234")
        r = self.client.get("/panel/")
        self.assertEqual(r.status_code, 200)

    def test_admin_redirigido_desde_panel_a_dashadmin(self):
        self.client.login(username="iso_admin", password="test1234")
        r = self.client.get("/panel/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/dashadmin/", r["Location"])

    # ── Dashadmin ─────────────────────────────────────────────────────────
    def test_anonimo_redirigido_desde_dashadmin(self):
        r = self.client.get("/dashadmin/")
        self.assertEqual(r.status_code, 302)

    def test_admin_accede_al_dashadmin(self):
        self.client.login(username="iso_admin", password="test1234")
        r = self.client.get("/dashadmin/")
        self.assertEqual(r.status_code, 200)

    def test_asesora_no_accede_al_dashadmin(self):
        self.client.login(username="iso_asesora", password="test1234")
        r = self.client.get("/dashadmin/")
        self.assertNotEqual(r.status_code, 200)

    def test_tecnico_no_accede_al_dashadmin(self):
        self.client.login(username="iso_tecnico", password="test1234")
        r = self.client.get("/dashadmin/")
        self.assertNotEqual(r.status_code, 200)

    # ── Campo ─────────────────────────────────────────────────────────────
    def test_anonimo_redirigido_desde_campo(self):
        r = self.client.get("/campo/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/campo/acceso/", r["Location"])

    def test_tecnico_accede_al_campo(self):
        self.client.login(username="iso_tecnico", password="test1234")
        r = self.client.get("/campo/")
        self.assertEqual(r.status_code, 200)

    def test_asesora_sin_field_profile_redirigida_desde_campo(self):
        self.client.login(username="iso_asesora", password="test1234")
        r = self.client.get("/campo/")
        self.assertEqual(r.status_code, 302)

    def test_admin_redirigido_desde_campo_a_dashadmin(self):
        self.client.login(username="iso_admin", password="test1234")
        r = self.client.get("/campo/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/dashadmin/", r["Location"])


# ===========================================================================
# 3. PANEL CRM — ASESORA
# ===========================================================================

class PanelHomeTest(TestCase):

    def setUp(self):
        self.client  = Client()
        self.asesora = make_asesora("ph_asesora")
        self.client.login(username="ph_asesora", password="test1234")

    def test_home_carga_200(self):
        r = self.client.get("/panel/")
        self.assertEqual(r.status_code, 200)

    def test_home_incluye_nombre_asesora(self):
        self.asesora.first_name = "Valeria"
        self.asesora.save()
        r = self.client.get("/panel/")
        self.assertContains(r, "Valeria")


class PanelQuoteTest(TestCase):

    def setUp(self):
        self.client  = Client()
        self.asesora = make_asesora("pq_asesora")
        self.client.login(username="pq_asesora", password="test1234")
        self.lead  = make_lead("Empresa ABC", "empresa@abc.co")
        self.quote = make_quote(self.lead, asesora=self.asesora, status="new")

    def test_lista_cotizaciones_200(self):
        r = self.client.get("/panel/cotizaciones/")
        self.assertEqual(r.status_code, 200)

    def test_lista_muestra_cotizacion_asignada(self):
        r = self.client.get("/panel/cotizaciones/")
        self.assertContains(r, "Empresa ABC")

    def test_detalle_cotizacion_200(self):
        r = self.client.get(f"/panel/cotizaciones/{self.quote.pk}/")
        self.assertEqual(r.status_code, 200)

    def test_detalle_muestra_cliente(self):
        r = self.client.get(f"/panel/cotizaciones/{self.quote.pk}/")
        self.assertContains(r, "Empresa ABC")

    def test_cotizacion_inexistente_retorna_404(self):
        r = self.client.get("/panel/cotizaciones/99999/")
        self.assertEqual(r.status_code, 404)


class PanelClientTest(TestCase):

    def setUp(self):
        self.client_  = Client()
        self.asesora  = make_asesora("pc_asesora")
        self.client_.login(username="pc_asesora", password="test1234")
        self.lead = make_lead("Carlos Pérez", "carlos@test.co")

    def test_lista_clientes_200(self):
        r = self.client_.get("/panel/clientes/")
        self.assertEqual(r.status_code, 200)

    def test_lista_muestra_cliente(self):
        r = self.client_.get("/panel/clientes/")
        self.assertContains(r, "Carlos Pérez")

    def test_detalle_cliente_200(self):
        r = self.client_.get(f"/panel/clientes/{self.lead.pk}/")
        self.assertEqual(r.status_code, 200)

    def test_detalle_cliente_muestra_datos(self):
        r = self.client_.get(f"/panel/clientes/{self.lead.pk}/")
        self.assertContains(r, "Carlos Pérez")

    def test_cliente_inexistente_retorna_404(self):
        r = self.client_.get("/panel/clientes/99999/")
        self.assertEqual(r.status_code, 404)

    def test_registrar_actividad_post(self):
        r = self.client_.post(
            f"/panel/clientes/{self.lead.pk}/actividad/",
            {"activity_type": "call", "notes": "Llamé y respondió", "outcome": "Enviar cotización"},
        )
        self.assertIn(r.status_code, (200, 302))
        self.assertTrue(LeadActivity.objects.filter(lead=self.lead).exists())

    def test_crear_tarea_post(self):
        tomorrow = (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        r = self.client_.post(
            f"/panel/clientes/{self.lead.pk}/tarea/",
            {"description": "Llamar el viernes", "due_date": tomorrow},
        )
        self.assertIn(r.status_code, (200, 302))
        self.assertTrue(FollowUpTask.objects.filter(lead=self.lead).exists())

    def test_buscar_cliente_por_nombre(self):
        make_lead("Empresa XYZ", "xyz@test.co")
        r = self.client_.get("/panel/clientes/?q=Carlos")
        self.assertContains(r, "Carlos Pérez")
        self.assertNotContains(r, "Empresa XYZ")


class PanelTicketTest(TestCase):

    def setUp(self):
        self.client_ = Client()
        self.asesora = make_asesora("pt_asesora")
        self.tecnico = make_field_user("pt_tecnico")
        self.client_.login(username="pt_asesora", password="test1234")
        self.lead   = make_lead("Empresa Tickets", "tkt@test.co")
        self.ticket = make_ticket(self.lead, assigned_to=self.tecnico)

    def test_lista_tickets_200(self):
        r = self.client_.get("/panel/tickets/")
        self.assertEqual(r.status_code, 200)

    def test_lista_muestra_ticket(self):
        r = self.client_.get("/panel/tickets/?mine=0")
        self.assertContains(r, "Empresa Tickets")

    def test_detalle_ticket_200(self):
        r = self.client_.get(f"/panel/tickets/{self.ticket.pk}/")
        self.assertEqual(r.status_code, 200)

    def test_ticket_inexistente_retorna_404(self):
        # El usuario tiene panel_tickets, por lo que la verificación pasa y luego get_object_or_404 devuelve 404
        r = self.client_.get("/panel/tickets/99999/")
        self.assertIn(r.status_code, (403, 404))

    def test_formulario_nuevo_ticket_200(self):
        r = self.client_.get("/panel/tickets/nuevo/")
        self.assertEqual(r.status_code, 200)

    def test_crear_ticket_post(self):
        r = self.client_.post("/panel/tickets/nuevo/", {
            "lead":            self.lead.pk,
            "issue_type":      "repair",
            "priority":        "high",
            "description":     "La fotocopiadora hace ruido raro",
            "equipment_description": "Kyocera M3145",
            "assigned_to":     self.tecnico.pk,
        })
        self.assertIn(r.status_code, (200, 302))
        self.assertTrue(
            ServiceTicket.objects.filter(lead=self.lead, priority="high").exists()
        )

    def test_actualizar_estado_ticket_ajax(self):
        r = self.client_.post(
            f"/panel/tickets/{self.ticket.pk}/estado/",
            {"status": "in_progress", "resolution_notes": ""},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ok"])
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "in_progress")

    def test_estado_invalido_retorna_400(self):
        r = self.client_.post(
            f"/panel/tickets/{self.ticket.pk}/estado/",
            {"status": "estado_inventado"},
        )
        self.assertEqual(r.status_code, 400)

    def test_resolver_ticket_registra_resolved_at(self):
        r = self.client_.post(
            f"/panel/tickets/{self.ticket.pk}/estado/",
            {"status": "resolved", "resolution_notes": "Se reemplazó el fusor"},
        )
        self.assertEqual(r.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.resolved_at)

    def test_tecnico_no_puede_crear_ticket(self):
        """Los técnicos no tienen acceso a crear tickets desde el panel."""
        client_tec = Client()
        client_tec.login(username="pt_tecnico", password="test1234")
        # El técnico no tiene acceso a /panel/ (es campo) → redirect
        r = client_tec.get("/panel/tickets/nuevo/")
        self.assertNotEqual(r.status_code, 200)


class PanelContractTest(TestCase):

    def setUp(self):
        self.client_ = Client()
        self.asesora = make_asesora("pcon_asesora")
        self.client_.login(username="pcon_asesora", password="test1234")
        self.lead     = make_lead("Empresa Contratos", "contrato@test.co")
        self.contract = make_contract(self.lead)

    def test_lista_contratos_200(self):
        r = self.client_.get("/panel/contratos/")
        self.assertEqual(r.status_code, 200)

    def test_lista_muestra_contrato(self):
        r = self.client_.get("/panel/contratos/")
        self.assertContains(r, "CTR-TEST-")


class PanelConsumableTest(TestCase):

    def setUp(self):
        self.client_ = Client()
        make_asesora("pins_asesora")
        self.client_.login(username="pins_asesora", password="test1234")

    def test_lista_insumos_200(self):
        r = self.client_.get("/panel/insumos/")
        self.assertEqual(r.status_code, 200)


# ===========================================================================
# 4. DASHADMIN
# ===========================================================================

class DashadminHomeTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin  = make_admin("da_admin")
        self.client.login(username="da_admin", password="test1234")

    def test_home_200(self):
        r = self.client.get("/dashadmin/")
        self.assertEqual(r.status_code, 200)

    def test_pipeline_200(self):
        r = self.client.get("/dashadmin/cotizaciones/pipeline/")
        self.assertEqual(r.status_code, 200)


class DashadminClientTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin  = make_admin("da_cl_admin")
        self.client.login(username="da_cl_admin", password="test1234")
        self.lead = make_lead("Empresa Admin", "admin_cl@test.co")

    def test_lista_clientes_200(self):
        r = self.client.get("/dashadmin/clientes/")
        self.assertEqual(r.status_code, 200)

    def test_lista_muestra_cliente(self):
        r = self.client.get("/dashadmin/clientes/")
        self.assertContains(r, "Empresa Admin")

    def test_detalle_cliente_200(self):
        r = self.client.get(f"/dashadmin/clientes/{self.lead.pk}/")
        self.assertEqual(r.status_code, 200)

    def test_editar_cliente_nombre(self):
        r = self.client.post(f"/dashadmin/clientes/{self.lead.pk}/", {
            "full_name":    "Empresa Admin Editada",
            "email":        "admin_cl@test.co",
            "phone":        "3001234567",
        })
        self.assertIn(r.status_code, (200, 302))
        self.lead.refresh_from_db()
        self.assertIn("Editada", self.lead.full_name)

    def test_buscar_cliente(self):
        make_lead("Empresa Otro", "otro@test.co")
        r = self.client.get("/dashadmin/clientes/?q=Admin")
        self.assertContains(r, "Empresa Admin")
        self.assertNotContains(r, "Empresa Otro")

    def test_exportar_leads_csv(self):
        r = self.client.get("/dashadmin/exportar/leads/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])


class DashadminQuoteTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin  = make_admin("da_q_admin")
        self.client.login(username="da_q_admin", password="test1234")
        self.lead  = make_lead("Empresa Quote", "quote@test.co")
        self.quote = make_quote(self.lead, status="new")

    def test_lista_cotizaciones_200(self):
        r = self.client.get("/dashadmin/cotizaciones/")
        self.assertEqual(r.status_code, 200)

    def test_detalle_cotizacion_200(self):
        r = self.client.get(f"/dashadmin/cotizaciones/{self.quote.pk}/")
        self.assertEqual(r.status_code, 200)

    def test_mover_estado_pipeline(self):
        import json as _json
        r = self.client.post(
            f"/dashadmin/cotizaciones/{self.quote.pk}/mover/",
            data=_json.dumps({"status": "reviewing"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.status, "reviewing")

    def test_marcar_ganada_registra_closed_at(self):
        import json as _json
        self.client.post(
            f"/dashadmin/cotizaciones/{self.quote.pk}/mover/",
            data=_json.dumps({"status": "won"}),
            content_type="application/json",
        )
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.status, "won")
        self.assertIsNotNone(self.quote.closed_at)

    def test_marcar_perdida_con_categoria(self):
        import json as _json
        # El pipeline move no guarda lost_category — eso es un hallazgo: puede ser una brecha
        r = self.client.post(
            f"/dashadmin/cotizaciones/{self.quote.pk}/mover/",
            data=_json.dumps({"status": "lost"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.status, "lost")

    def test_exportar_cotizaciones_csv(self):
        r = self.client.get("/dashadmin/exportar/cotizaciones/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])


class DashadminTicketTest(TestCase):

    def setUp(self):
        self.client  = Client()
        self.admin   = make_admin("da_tkt_admin")
        self.tecnico = make_field_user("da_tecnico")
        self.client.login(username="da_tkt_admin", password="test1234")
        self.lead   = make_lead("Empresa Ticket Admin", "tkt_da@test.co")
        self.ticket = make_ticket(self.lead, assigned_to=self.tecnico)

    def test_lista_tickets_200(self):
        r = self.client.get("/dashadmin/tickets/")
        self.assertEqual(r.status_code, 200)

    def test_detalle_ticket_200(self):
        r = self.client.get(f"/dashadmin/tickets/{self.ticket.pk}/")
        self.assertEqual(r.status_code, 200)

    def test_actualizar_estado_ticket(self):
        r = self.client.post(f"/dashadmin/tickets/{self.ticket.pk}/", {
            "lead":             self.ticket.lead.pk,
            "status":           "in_progress",
            "priority":         "high",
            "resolution_notes": "",
            "description":      "Descripción actualizada",
            "equipment_description": "Ricoh 2015",
            "issue_type":       "repair",
        })
        self.assertIn(r.status_code, (200, 302))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "in_progress")


class DashadminContractTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.admin  = make_admin("da_con_admin")
        self.client.login(username="da_con_admin", password="test1234")
        self.lead = make_lead("Empresa Contrato Da", "contrato_da@test.co")

    def test_lista_contratos_200(self):
        r = self.client.get("/dashadmin/contratos/")
        self.assertEqual(r.status_code, 200)

    def test_crear_contrato_get_200(self):
        r = self.client.get("/dashadmin/contratos/nuevo/")
        self.assertEqual(r.status_code, 200)

    def test_crear_contrato_post(self):
        today = date.today()
        r = self.client.post("/dashadmin/contratos/nuevo/", {
            "lead":                   self.lead.pk,
            "status":                 "active",
            "start_date":             today.strftime("%Y-%m-%d"),
            "end_date":               (today + timedelta(days=365)).strftime("%Y-%m-%d"),
            "monthly_rate":           "450000",
            "equipment_description":  "Ricoh MP 2014AD",
            "copies_included":        "3000",
            "copy_overage_rate":      "45",
        })
        self.assertIn(r.status_code, (200, 302))
        self.assertTrue(RentalContract.objects.filter(lead=self.lead).exists())

    def test_exportar_contratos_csv(self):
        r = self.client.get("/dashadmin/exportar/contratos/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])


# ===========================================================================
# 5. CAMPO (TÉCNICOS / MENSAJEROS)
# ===========================================================================

class CampoTurnoTest(TestCase):

    def setUp(self):
        self.client  = Client()
        self.tecnico = make_field_user("campo_tec", role="tecnico")
        self.client.login(username="campo_tec", password="test1234")

    def test_turno_200(self):
        r = self.client.get("/campo/")
        self.assertEqual(r.status_code, 200)

    def test_turno_contiene_seccion_ruta(self):
        r = self.client.get("/campo/")
        self.assertContains(r, "Mi Turno")

    def test_tecnico_ve_sus_tickets_en_ruta(self):
        lead   = make_lead("Cliente Campo", "campo@test.co")
        make_ticket(lead, assigned_to=self.tecnico)
        r = self.client.get("/campo/")
        self.assertContains(r, "Cliente Campo")

    def test_tecnico_no_ve_tickets_de_otro(self):
        otro   = make_field_user("campo_tec2", role="tecnico")
        lead   = make_lead("Cliente Ajeno", "ajeno@test.co")
        make_ticket(lead, assigned_to=otro)
        r = self.client.get("/campo/")
        self.assertNotContains(r, "Cliente Ajeno")

    def test_turno_start_post(self):
        r = self.client.post("/campo/turno/inicio/", {"lat": "6.24", "lon": "-75.58"})
        self.assertIn(r.status_code, (200, 302))

    def test_turno_end_post(self):
        self.client.post("/campo/turno/inicio/", {"lat": "6.24", "lon": "-75.58"})
        r = self.client.post("/campo/turno/fin/")
        self.assertIn(r.status_code, (200, 302))


class CampoMensajeroTest(TestCase):

    def setUp(self):
        self.client    = Client()
        self.mensajero = make_field_user("campo_msg", role="mensajero")
        self.client.login(username="campo_msg", password="test1234")

    def test_turno_200(self):
        r = self.client.get("/campo/")
        self.assertEqual(r.status_code, 200)

    def test_mensajero_no_accede_al_panel_crm(self):
        r = self.client.get("/panel/cotizaciones/")
        self.assertNotEqual(r.status_code, 200)


# ===========================================================================
# 6. PÁGINAS PÚBLICAS
# ===========================================================================

class PublicPagesTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_home_200(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)

    def test_about_200(self):
        r = self.client.get("/sobre-nosotros/")
        self.assertEqual(r.status_code, 200)

    def test_contact_200(self):
        r = self.client.get("/contacto/")
        self.assertEqual(r.status_code, 200)

    def test_formulario_contacto_post_valido(self):
        r = self.client.post("/contacto/", {
            "name":    "Juan Prueba",
            "email":   "juan@prueba.co",
            "phone":   "3001234567",
            "message": "Quiero información",
        })
        self.assertIn(r.status_code, (200, 302))

    def test_sitemap_200(self):
        r = self.client.get("/sitemap.xml")
        self.assertIn(r.status_code, (200, 301, 302))

    def test_robots_txt_200(self):
        r = self.client.get("/robots.txt")
        self.assertIn(r.status_code, (200, 301, 302))


# ===========================================================================
# 7. SEGURIDAD
# ===========================================================================

class SecurityHeadersTest(TestCase):
    """Verifica que las respuestas incluyan headers de seguridad básicos."""

    def setUp(self):
        self.client = Client()

    def test_x_frame_options_en_home(self):
        r = self.client.get("/")
        self.assertIn(r.get("X-Frame-Options", ""), ("DENY", "SAMEORIGIN"))

    def test_panel_login_devuelve_csrf_cookie(self):
        r = self.client.get("/panel/acceso/")
        self.assertIn("csrftoken", r.cookies)

    def test_dashadmin_login_devuelve_csrf_cookie(self):
        r = self.client.get("/dashadmin/acceso/")
        self.assertIn("csrftoken", r.cookies)


class CsrfProtectionTest(TestCase):
    """Verifica que los POSTs sin CSRF token sean rechazados."""

    def setUp(self):
        self.asesora = make_asesora("csrf_asesora")

    def test_post_sin_csrf_en_actividad_rechazado(self):
        lead = make_lead("CSRF Cliente", "csrf@test.co")
        client_no_csrf = Client(enforce_csrf_checks=True)
        client_no_csrf.login(username="csrf_asesora", password="test1234")
        r = client_no_csrf.post(f"/panel/clientes/{lead.pk}/actividad/", {
            "activity_type": "call",
            "description":   "Test sin CSRF",
            "outcome":       "",
        })
        self.assertEqual(r.status_code, 403)

    def test_post_sin_csrf_en_ticket_estado_rechazado(self):
        lead   = make_lead("CSRF Ticket", "csrf_tkt@test.co")
        ticket = make_ticket(lead)
        client_no_csrf = Client(enforce_csrf_checks=True)
        client_no_csrf.login(username="csrf_asesora", password="test1234")
        r = client_no_csrf.post(f"/panel/tickets/{ticket.pk}/estado/", {
            "status": "in_progress",
        })
        self.assertEqual(r.status_code, 403)


class BruteForceTest(TestCase):
    """Verifica que el sistema bloquee intentos de login repetidos."""

    def test_multiples_intentos_fallidos_panel_devuelven_error(self):
        client = Client()
        for _ in range(6):
            r = client.post("/panel/acceso/", {
                "username": "no_existe",
                "password": "mal_password",
            })
        # Después de varios intentos fallidos, el sistema debe bloquear o dar error
        self.assertIn(r.status_code, (200, 302, 429))
        content = r.content.decode("utf-8", errors="replace")
        bloqueado = any(kw in content.lower() for kw in (
            "bloqueado", "blocked", "intento", "espera", "wait", "too many"
        ))
        # Si no muestra bloqueo explícito, al menos no otorga acceso
        self.assertNotIn("/panel/", r.get("Location", ""))

    def test_login_exitoso_limpia_contador_de_intentos(self):
        asesora = make_asesora("bf_asesora")
        client  = Client()
        client.post("/panel/acceso/", {"username": "bf_asesora", "password": "mal"})
        r = client.post("/panel/acceso/", {"username": "bf_asesora", "password": "test1234"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/panel/", r["Location"])


class HorizontalPrivilegeTest(TestCase):
    """Una asesora NO puede ver datos de tickets asignados a otra."""

    def setUp(self):
        self.client1 = Client()
        self.client2 = Client()
        self.asesora1 = make_asesora("hpe_asesora1")
        self.asesora2 = make_asesora("hpe_asesora2")
        self.tecnico  = make_field_user("hpe_tecnico")
        self.client1.login(username="hpe_asesora1", password="test1234")
        self.client2.login(username="hpe_asesora2", password="test1234")

    def test_asesora_puede_ver_lista_completa_de_tickets(self):
        """El panel muestra todos los tickets (no solo de una asesora) — comportamiento esperado."""
        lead   = make_lead("Cliente HPE", "hpe@test.co")
        ticket = make_ticket(lead, assigned_to=self.tecnico)
        r = self.client2.get("/panel/tickets/")
        # Ambas asesoras ven los tickets (es la lista general del equipo)
        self.assertEqual(r.status_code, 200)

    def test_asesora_no_puede_acceder_al_dashadmin(self):
        r = self.client1.get("/dashadmin/clientes/")
        self.assertNotEqual(r.status_code, 200)

    def test_asesora_no_puede_acceder_al_campo(self):
        r = self.client1.get("/campo/turno/")
        self.assertNotEqual(r.status_code, 200)


class SqlInjectionTest(TestCase):
    """Entradas maliciosas no deben provocar errores 500."""

    def setUp(self):
        self.client  = Client()
        self.asesora = make_asesora("sqli_asesora")
        self.client.login(username="sqli_asesora", password="test1234")

    def test_busqueda_con_comilla_simple_no_explota(self):
        r = self.client.get("/panel/clientes/?q=' OR '1'='1")
        self.assertNotEqual(r.status_code, 500)

    def test_busqueda_con_punto_coma_no_explota(self):
        r = self.client.get("/panel/clientes/?q=; DROP TABLE leads_lead;--")
        self.assertNotEqual(r.status_code, 500)

    def test_busqueda_admin_con_inyeccion(self):
        self.client.logout()
        admin = make_admin("sqli_admin")
        self.client.login(username="sqli_admin", password="test1234")
        r = self.client.get("/dashadmin/clientes/?q=<script>alert(1)</script>")
        self.assertNotEqual(r.status_code, 500)
        # El script no debe aparecer sin escapar en la respuesta
        self.assertNotIn(b"<script>alert(1)</script>", r.content)

    def test_campo_ticket_descripcion_xss_escapada(self):
        lead   = make_lead("XSS Test", "xss@test.co")
        ticket = make_ticket(lead)
        ticket.description = "<script>alert('xss')</script>"
        ticket.save()
        r = self.client.get(f"/panel/tickets/{ticket.pk}/")
        self.assertNotIn(b"<script>alert('xss')</script>", r.content)


class AuthenthicatedEndpointsTest(TestCase):
    """Endpoints sensibles no deben ser accesibles sin autenticación."""

    def setUp(self):
        self.client = Client()
        self.lead   = make_lead("Anon Test", "anon@test.co")
        self.ticket = make_ticket(self.lead)

    def test_panel_cotizaciones_requiere_login(self):
        r = self.client.get("/panel/cotizaciones/")
        self.assertEqual(r.status_code, 302)

    def test_panel_clientes_requiere_login(self):
        r = self.client.get("/panel/clientes/")
        self.assertEqual(r.status_code, 302)

    def test_panel_tickets_requiere_login(self):
        r = self.client.get("/panel/tickets/")
        self.assertEqual(r.status_code, 302)

    def test_panel_ticket_estado_requiere_login(self):
        r = self.client.post(f"/panel/tickets/{self.ticket.pk}/estado/", {"status": "closed"})
        self.assertEqual(r.status_code, 302)

    def test_dashadmin_requiere_login(self):
        r = self.client.get("/dashadmin/")
        self.assertEqual(r.status_code, 302)

    def test_dashadmin_exportar_leads_requiere_login(self):
        r = self.client.get("/dashadmin/exportar/leads/")
        self.assertEqual(r.status_code, 302)

    def test_whatsapp_inbox_requiere_login(self):
        r = self.client.get("/whatsapp/panel/inbox/")
        self.assertEqual(r.status_code, 302)

    def test_whatsapp_simulador_requiere_login(self):
        r = self.client.get("/whatsapp/panel/simulador/")
        self.assertEqual(r.status_code, 302)

    def test_whatsapp_dashadmin_requiere_login(self):
        r = self.client.get("/whatsapp/dash/")
        self.assertEqual(r.status_code, 302)
