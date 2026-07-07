"""
Limpia todas las tareas de entrega existentes y crea 10 de prueba.
Uso: python manage.py seed_delivery_tasks
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


TASKS = [
    {
        "field_user_pk": 1,   # mateo (mensajero)
        "title":         "Entregar tóner Ricoh MP2014",
        "client_name":   "Distribuidora La 50",
        "address":       "Carrera 50 #53-20, Medellín",
        "invoice_ref":   "FAC-2025-001",
        "payment_method": "efectivo",
        "description":   "Tóner negro x2. Preguntar por doña Carmen.",
        "order": 1,
    },
    {
        "field_user_pk": 1,
        "title":         "Instalar drum kit copiadora Canon",
        "client_name":   "Clínica San Rafael",
        "address":       "Calle 62 #51D-90, Medellín",
        "invoice_ref":   "FAC-2025-002",
        "payment_method": "banco",
        "description":   "Drum unit modelo NPG-59. Llevar factura.",
        "order": 2,
    },
    {
        "field_user_pk": 1,
        "title":         "Entrega insumos Xerox WorkCentre",
        "client_name":   "Universidad de Antioquia",
        "address":       "Calle 67 #53-108, Medellín",
        "invoice_ref":   "FAC-2025-003",
        "payment_method": "cxc",
        "description":   "Kit de mantenimiento completo.",
        "order": 3,
    },
    {
        "field_user_pk": 1,
        "title":         "Recogida equipo dañado Kyocera",
        "client_name":   "Seguros Bolívar",
        "address":       "Avenida El Poblado #1-20, Medellín",
        "invoice_ref":   "",
        "payment_method": "efectivo",
        "description":   "Recoger ECOSYS M2040dn. Llevar bolsa protectora.",
        "order": 4,
    },
    {
        "field_user_pk": 1,
        "title":         "Entregar tóner HP LaserJet x3",
        "client_name":   "Notaría 10 de Medellín",
        "address":       "Carrera 43A #14-109, El Poblado, Medellín",
        "invoice_ref":   "FAC-2025-004",
        "payment_method": "banco",
        "description":   "Tóner HP 85A x3 unidades.",
        "order": 5,
    },
    {
        "field_user_pk": 2,   # norbey (mensajero)
        "title":         "Mantenimiento preventivo Brother",
        "client_name":   "Colegio La Salle",
        "address":       "Carrera 65 #58-40, Laureles, Medellín",
        "invoice_ref":   "FAC-2025-005",
        "payment_method": "cxc",
        "description":   "Limpieza general + cambio rodillo fusor.",
        "order": 1,
    },
    {
        "field_user_pk": 2,
        "title":         "Entregar papel resma A4 x10",
        "client_name":   "Empresa de Telecomunicaciones",
        "address":       "Calle 44 #68-50, Belén, Medellín",
        "invoice_ref":   "FAC-2025-006",
        "payment_method": "efectivo",
        "description":   "Papel Bond 75gr x10 resmas.",
        "order": 2,
    },
    {
        "field_user_pk": 2,
        "title":         "Instalar impresora en red Sharp",
        "client_name":   "Constructora Conconcreto",
        "address":       "Carrera 43A #34-95, Medellín",
        "invoice_ref":   "FAC-2025-007",
        "payment_method": "banco",
        "description":   "Configurar Sharp MX-3070N en red local.",
        "order": 3,
    },
    {
        "field_user_pk": 3,   # daniel (técnico)
        "title":         "Revisión copiadora Ricoh MP3054",
        "client_name":   "Alkosto Medellín",
        "address":       "Autopista Sur #50-20, Itagüí",
        "invoice_ref":   "FAC-2025-008",
        "payment_method": "cxc",
        "description":   "Error código SC555. Llevar kit fusión.",
        "order": 1,
    },
    {
        "field_user_pk": 3,
        "title":         "Entrega equipo reparado Lexmark",
        "client_name":   "Hospital General de Medellín",
        "address":       "Calle 24 #1-00, Medellín",
        "invoice_ref":   "FAC-2025-009",
        "payment_method": "banco",
        "description":   "Lexmark MS421dn reparado. Entregar con acta.",
        "order": 2,
    },
]


class Command(BaseCommand):
    help = "Limpia entregas existentes y crea 10 tareas de prueba"

    def handle(self, *args, **options):
        from apps.dashboard.models import DeliveryTask, FieldUser
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # 1. Limpiar
        deleted, _ = DeliveryTask.objects.all().delete()
        self.stdout.write(self.style.WARNING(f"  Eliminadas {deleted} tarea(s) existentes."))

        # 2. Obtener usuario admin para created_by
        admin = User.objects.filter(is_staff=True).first()

        # 3. Crear tareas
        today = timezone.localdate()
        created = 0
        for t in TASKS:
            try:
                fu = FieldUser.objects.get(pk=t["field_user_pk"])
            except FieldUser.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"  FieldUser pk={t['field_user_pk']} no existe, omitiendo."))
                continue

            DeliveryTask.objects.create(
                field_user         = fu,
                title              = t["title"],
                client_name        = t["client_name"],
                address            = t["address"],
                completion_invoice = t["invoice_ref"],
                payment_method     = t["payment_method"],
                description        = t["description"],
                order              = t["order"],
                due_date           = today,
                created_by         = admin,
                status             = DeliveryTask.Status.PENDING,
            )
            created += 1
            self.stdout.write(f"  OK [{fu.user.get_full_name() or fu.user.username}] {t['title']}")

        self.stdout.write(self.style.SUCCESS(f"\n  {created} tareas de prueba creadas exitosamente."))
