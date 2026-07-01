from django.db import models


class Encuesta(models.Model):
    CALIFICACION_CHOICES = [
        (1, "Muy malo"),
        (2, "Malo"),
        (3, "Regular"),
        (4, "Bueno"),
        (5, "Excelente"),
    ]

    SERVICIO_CHOICES = [
        ("venta", "Venta de equipos"),
        ("alquiler", "Alquiler de equipos"),
        ("mantenimiento", "Mantenimiento"),
        ("suministros", "Suministros / Tóner"),
        ("soporte", "Soporte técnico"),
        ("software", "Software / Desarrollo"),
        ("cableado", "Cableado estructurado"),
    ]

    nombre = models.CharField(max_length=150, verbose_name="Nombre completo")
    empresa = models.CharField(max_length=150, verbose_name="Empresa", blank=True)
    email = models.EmailField(verbose_name="Correo electrónico")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono", blank=True)

    tipo_servicio = models.CharField(
        max_length=50,
        choices=SERVICIO_CHOICES,
        verbose_name="Tipo de servicio recibido",
    )
    calificacion_atencion = models.PositiveSmallIntegerField(
        choices=CALIFICACION_CHOICES,
        verbose_name="Calidad de atención",
    )
    calificacion_servicio = models.PositiveSmallIntegerField(
        choices=CALIFICACION_CHOICES,
        verbose_name="Calidad del servicio técnico",
    )
    calificacion_tiempo = models.PositiveSmallIntegerField(
        choices=CALIFICACION_CHOICES,
        verbose_name="Tiempo de respuesta",
    )
    calificacion_precio = models.PositiveSmallIntegerField(
        choices=CALIFICACION_CHOICES,
        verbose_name="Relación precio / calidad",
    )
    recomendaria = models.BooleanField(default=True, verbose_name="¿Recomendaría Solution Copiers?")
    comentarios = models.TextField(blank=True, verbose_name="Comentarios adicionales")

    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de envío")
    ip_origen = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")

    class Meta:
        verbose_name = "Encuesta"
        verbose_name_plural = "Encuestas"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.nombre} — {self.fecha.strftime('%d/%m/%Y')}"

    @property
    def promedio(self):
        campos = [
            self.calificacion_atencion,
            self.calificacion_servicio,
            self.calificacion_tiempo,
            self.calificacion_precio,
        ]
        return round(sum(campos) / len(campos), 1)
