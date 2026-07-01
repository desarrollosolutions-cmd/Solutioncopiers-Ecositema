import logging

from django.shortcuts import render, redirect
from django.contrib import messages, auth
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count

from .models import Encuesta

logger = logging.getLogger(__name__)


def panel_login(request):
    """Login propio del panel de encuestas — solo staff."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("encuestas:panel")

    next_url = request.GET.get("next", "encuestas:panel")
    error = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        next_url = request.POST.get("next", "encuestas:panel")

        user = auth.authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            auth.login(request, user)
            return redirect(next_url if next_url.startswith("/") else "encuestas:panel")
        else:
            # Usar un objeto que simule form.errors para el template
            error = True

    return render(request, "encuestas/login.html", {
        "form": type("F", (), {"errors": error})(),
        "next": next_url,
    })


def encuesta_form(request):
    context = {
        "model_choices": Encuesta.SERVICIO_CHOICES,
        "rating_fields": [
            ("calificacion_atencion", "Calidad de atención"),
            ("calificacion_servicio", "Servicio técnico"),
            ("calificacion_tiempo", "Tiempo de respuesta"),
            ("calificacion_precio", "Precio / Calidad"),
        ],
    }
    return render(request, "encuestas/encuesta.html", context)


def encuesta_guardar(request):
    if request.method != "POST":
        return redirect("encuestas:form")

    # Usar REMOTE_ADDR (fiable) como IP. En producción detrás de proxy
    # Render/Heroku ya reescribe REMOTE_ADDR con la IP real del cliente.
    ip = request.META.get("REMOTE_ADDR", "")

    try:
        encuesta = Encuesta(
            nombre=request.POST.get("nombre", "").strip(),
            empresa=request.POST.get("empresa", "").strip(),
            email=request.POST.get("email", "").strip(),
            telefono=request.POST.get("telefono", "").strip(),
            tipo_servicio=request.POST.get("tipo_servicio", ""),
            calificacion_atencion=int(request.POST.get("calificacion_atencion", 3)),
            calificacion_servicio=int(request.POST.get("calificacion_servicio", 3)),
            calificacion_tiempo=int(request.POST.get("calificacion_tiempo", 3)),
            calificacion_precio=int(request.POST.get("calificacion_precio", 3)),
            recomendaria=request.POST.get("recomendaria") == "si",
            comentarios=request.POST.get("comentarios", "").strip(),
            ip_origen=ip,
        )
        encuesta.full_clean()
        encuesta.save()
        return redirect("encuestas:exito")

    except Exception as e:
        logger.exception("Error al guardar encuesta desde IP %s: %s", ip, e)
        messages.error(request, "No se pudo guardar la encuesta. Por favor intenta de nuevo.")
        return redirect("encuestas:form")


def encuesta_exito(request):
    return render(request, "encuestas/exito.html")


@staff_member_required(login_url="/encuesta/acceso/")
def panel(request):
    encuestas_qs = Encuesta.objects.all()

    stats = encuestas_qs.aggregate(
        total=Count("id"),
        prom_atencion=Avg("calificacion_atencion"),
        prom_servicio=Avg("calificacion_servicio"),
        prom_tiempo=Avg("calificacion_tiempo"),
        prom_precio=Avg("calificacion_precio"),
    )

    total = stats["total"] or 0
    recomiendan = encuestas_qs.filter(recomendaria=True).count()
    pct_recomiendan = round((recomiendan / total * 100) if total else 0)

    promedio_general = 0
    if total:
        campos = ["prom_atencion", "prom_servicio", "prom_tiempo", "prom_precio"]
        valores = [stats[c] or 0 for c in campos]
        promedio_general = round(sum(valores) / len(valores), 1)

    por_servicio = (
        encuestas_qs.values("tipo_servicio")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    paginator = Paginator(encuestas_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    dimension_stats = [
        ("Atención", stats["prom_atencion"] or 0),
        ("Servicio técnico", stats["prom_servicio"] or 0),
        ("Tiempo de resp.", stats["prom_tiempo"] or 0),
        ("Precio / Calidad", stats["prom_precio"] or 0),
    ]

    context = {
        "encuestas": page_obj,
        "total": total,
        "promedio_general": promedio_general,
        "pct_recomiendan": pct_recomiendan,
        "por_servicio": por_servicio,
        "stats": stats,
        "dimension_stats": dimension_stats,
    }
    return render(request, "encuestas/panel.html", context)
