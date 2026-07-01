from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_notification_message_template'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='panelpermissions',
            options={
                'default_permissions': (),
                'managed': False,
                'permissions': [
                    ('panel_cotizaciones', 'Panel: Cotizaciones — ver, asignar y gestionar estados'),
                    ('panel_clientes', 'Panel: Clientes — ver perfiles e historial'),
                    ('panel_actividades', 'Panel: Actividades — registrar llamadas, notas y tareas'),
                    ('panel_tickets', 'Panel: Tickets — ver, crear y actualizar servicio'),
                    ('panel_contratos', 'Panel: Contratos — ver lista de alquileres'),
                    ('panel_insumos', 'Panel: Insumos — ver catálogo de consumibles'),
                    ('panel_reportes', 'Panel: Reportes — ver estadísticas y métricas'),
                    ('panel_exportar', 'Panel: Exportar — descargar datos en CSV'),
                    ('panel_facturacion', 'Panel: Facturación — crear y gestionar facturas propias'),
                ],
            },
        ),
    ]
