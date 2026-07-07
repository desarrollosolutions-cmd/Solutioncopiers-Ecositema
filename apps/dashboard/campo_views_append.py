
# ===========================================================================
# PORTAL DE CAMPO — /campo/  (mensajeros y tecnicos)
# ===========================================================================

def campo_required(view_func):
    from apps.dashboard.models import FieldUser
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/campo/acceso/?next={request.path}")
        if request.user.is_staff:
            return redirect("/dashadmin/")
        try:
            request.user.field_profile
        except FieldUser.DoesNotExist:
            return redirect("/campo/acceso/")
        return view_func(request, *args, **kwargs)
    return wrapper


campo_decorator = method_decorator(campo_required, name="dispatch")


class CampoLoginView(View):
    template_name = "campo/login.html"

    def get(self, request):
        from apps.dashboard.models import FieldUser
        if request.user.is_authenticated:
            try:
                request.user.field_profile
                return redirect("campo:turno")
            except FieldUser.DoesNotExist:
                pass
        return render(request, self.template_name)

    def post(self, request):
        from apps.dashboard.models import FieldUser
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            try:
                user.field_profile
                login(request, user)
                return redirect(request.GET.get("next") or "campo:turno")
            except FieldUser.DoesNotExist:
                pass
        return render(request, self.template_name, {"error": "Credenciales invalidas o sin acceso al portal de campo."})


class CampoLogoutView(View):
    def post(self, request):
        from apps.dashboard.models import FieldUserLocation
        if request.user.is_authenticated:
            try:
                loc = request.user.field_location
                loc.is_on_shift = False
                loc.save(update_fields=["is_on_shift"])
            except FieldUserLocation.DoesNotExist:
                pass
        logout(request)
        return redirect("campo:login")

    def get(self, request):
        logout(request)
        return redirect("campo:login")


@campo_decorator
class CampoTurnoView(View):
    template_name = "campo/turno.html"

    def get(self, request):
        from apps.dashboard.models import FieldUser, FieldUserLocation
        from apps.leads.models import FollowUpTask, ServiceTicket
        field_user = request.user.field_profile
        try:
            loc = request.user.field_location
        except FieldUserLocation.DoesNotExist:
            loc = None

        today = timezone.localdate()
        tasks = FollowUpTask.objects.filter(
            assigned_to=request.user, is_done=False, due_date=today
        ).select_related("lead").order_by("pk")[:20]

        tickets = ServiceTicket.objects.filter(
            assigned_to=request.user,
            status__in=("open", "in_progress", "waiting_parts")
        ).select_related("lead").order_by("priority", "created_at")[:20]

        return render(request, self.template_name, {
            "field_user": field_user,
            "location":   loc,
            "tasks":      tasks,
            "tickets":    tickets,
            "today":      today,
        })


@campo_decorator
class CampoUbicacionUpdateView(View):

    LOG_INTERVAL_SECONDS = 120  # guardar punto de ruta cada 2 minutos

    def post(self, request):
        from apps.dashboard.models import FieldUserLocation, FieldLocationLog
        from datetime import timedelta
        try:
            lat  = float(request.POST.get("lat") or request.POST.get("latitude"))
            lng  = float(request.POST.get("lng") or request.POST.get("longitude"))
            acc  = request.POST.get("accuracy")
            bat  = request.POST.get("battery")
            loc, _ = FieldUserLocation.objects.update_or_create(
                user=request.user,
                defaults={
                    "latitude":    lat,
                    "longitude":   lng,
                    "accuracy":    float(acc) if acc else None,
                    "battery":     int(float(bat)) if bat else None,
                    "is_on_shift": True,
                },
            )
            # ── Registro de ruta (throttled a LOG_INTERVAL_SECONDS) ──
            today = timezone.localdate()
            cutoff = timezone.now() - timedelta(seconds=self.LOG_INTERVAL_SECONDS)
            already_logged = FieldLocationLog.objects.filter(
                user=request.user, recorded_at__gte=cutoff
            ).exists()
            if not already_logged:
                FieldLocationLog.objects.create(
                    user=request.user, latitude=lat, longitude=lng, shift_date=today
                )
                # Limpiar puntos con más de 90 días (cada vez que se loguea un punto nuevo)
                FieldLocationLog.objects.filter(
                    user=request.user,
                    shift_date__lt=today - timedelta(days=90)
                ).delete()
            return JsonResponse({"ok": True, "updated_at": loc.updated_at.isoformat()})
        except (TypeError, ValueError) as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=400)


@campo_decorator
class CampoShiftStartView(View):
    def post(self, request):
        from apps.dashboard.models import FieldUserLocation
        FieldUserLocation.objects.update_or_create(
            user=request.user,
            defaults={"is_on_shift": True, "latitude": 0, "longitude": 0},
        )
        return JsonResponse({"ok": True})


@campo_decorator
class CampoShiftEndView(View):
    def post(self, request):
        from apps.dashboard.models import FieldUserLocation
        try:
            loc = request.user.field_location
            loc.is_on_shift = False
            loc.save(update_fields=["is_on_shift"])
        except FieldUserLocation.DoesNotExist:
            pass
        return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# Mapa de campo en el dashadmin
# ---------------------------------------------------------------------------

@da_decorator
class CampoMapView(TemplateView):
    template_name = "dashboard/campo/map.html"

    def get_context_data(self, **kwargs):
        from apps.dashboard.models import FieldUser, FieldUserLocation
        ctx = super().get_context_data(**kwargs)
        ctx["field_users"] = FieldUser.objects.select_related("user", "user__field_location").all()
        ctx["on_shift"] = FieldUserLocation.objects.filter(is_on_shift=True).count()
        return ctx


@da_decorator
class CampoLocationsJsonView(View):

    def get(self, request):
        from apps.dashboard.models import FieldUser, FieldUserLocation
        from django.utils.timesince import timesince
        locations = (
            FieldUserLocation.objects
            .filter(is_on_shift=True)
            .select_related("user", "user__field_profile")
        )
        data = []
        for loc in locations:
            fp = getattr(loc.user, "field_profile", None)
            data.append({
                "id":         loc.user.pk,
                "name":       loc.user.get_full_name() or loc.user.username,
                "role":       fp.get_role_display() if fp else "---",
                "role_key":   fp.role if fp else "",
                "lat":        float(loc.latitude),
                "lng":        float(loc.longitude),
                "accuracy":   loc.accuracy,
                "battery":    loc.battery,
                "updated_at": loc.updated_at.isoformat(),
                "ago":        timesince(loc.updated_at),
            })
        return JsonResponse({"locations": data, "count": len(data)})


@da_decorator
class CampoUserListView(TemplateView):
    template_name = "dashboard/campo/users.html"

    def get_context_data(self, **kwargs):
        from apps.dashboard.models import FieldUser
        ctx = super().get_context_data(**kwargs)
        ctx["field_users"] = FieldUser.objects.select_related("user", "user__field_location").order_by("role", "user__first_name")
        return ctx


@da_decorator
class CampoUserCreateView(View):
    template_name = "dashboard/campo/user_form.html"

    def get(self, request):
        from apps.dashboard.models import FieldUser
        from django.contrib.auth import get_user_model
        User = get_user_model()
        existing_ids = FieldUser.objects.values_list("user_id", flat=True)
        available = User.objects.filter(is_active=True, is_staff=False).exclude(pk__in=existing_ids).order_by("first_name")
        return render(request, self.template_name, {
            "available_users": available,
            "role_choices": FieldUser.Role.choices,
        })

    def post(self, request):
        from apps.dashboard.models import FieldUser
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(pk=request.POST.get("user_id"))
            FieldUser.objects.create(
                user  = user,
                role  = request.POST.get("role"),
                phone = request.POST.get("phone", "").strip(),
            )
            messages.success(request, f"{user.get_full_name() or user.username} agregado al equipo de campo.")
            return redirect("dashboard:campo_users")
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return redirect("dashboard:campo_user_create")


@da_decorator
class CampoUserDetailView(View):
    template_name = "dashboard/campo/user_form.html"

    def get(self, request, pk):
        from apps.dashboard.models import FieldUser
        fu = get_object_or_404(FieldUser, pk=pk)
        return render(request, self.template_name, {
            "field_user": fu,
            "role_choices": FieldUser.Role.choices,
        })

    def post(self, request, pk):
        from apps.dashboard.models import FieldUser
        fu = get_object_or_404(FieldUser, pk=pk)
        action = request.POST.get("action")
        if action == "delete":
            fu.delete()
            messages.success(request, "Usuario eliminado del equipo de campo.")
            return redirect("dashboard:campo_users")
        fu.role  = request.POST.get("role", fu.role)
        fu.phone = request.POST.get("phone", fu.phone).strip()
        fu.save()
        messages.success(request, "Datos actualizados.")
        return redirect("dashboard:campo_users")


# ---------------------------------------------------------------------------
# Gestión de tickets en el portal de campo (solo técnicos de campo)
# ---------------------------------------------------------------------------

def campo_tecnico_required(view_func):
    """Restricts access to field users with role='tecnico'."""
    from apps.dashboard.models import FieldUser
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/campo/acceso/?next={request.path}")
        if request.user.is_staff:
            return redirect("/dashadmin/")
        try:
            fp = request.user.field_profile
            if fp.role != FieldUser.Role.TECNICO:
                return redirect("campo:turno")
        except FieldUser.DoesNotExist:
            return redirect("/campo/acceso/")
        return view_func(request, *args, **kwargs)
    return wrapper


tecnico_decorator = method_decorator(campo_tecnico_required, name="dispatch")


@tecnico_decorator
class CampoTicketDetailView(View):
    """Vista de detalle y gestión de un ticket desde el portal de campo."""
    template_name = "campo/ticket_detail.html"

    def get(self, request, pk):
        from apps.leads.models import ServiceTicket
        ticket = get_object_or_404(
            ServiceTicket.objects.select_related("lead", "contract"),
            pk=pk, assigned_to=request.user,
        )
        return render(request, self.template_name, {"ticket": ticket})

    def post(self, request, pk):
        from apps.leads.models import ServiceTicket
        ticket = get_object_or_404(ServiceTicket, pk=pk, assigned_to=request.user)

        new_status = request.POST.get("status", "").strip()
        notes      = request.POST.get("resolution_notes", "").strip()

        valid_transitions = {
            "open":          ["in_progress", "waiting_parts"],
            "in_progress":   ["waiting_parts", "resolved"],
            "waiting_parts": ["in_progress", "resolved"],
            "resolved":      [],
            "closed":        [],
        }
        allowed = valid_transitions.get(ticket.status, [])

        if new_status and new_status in allowed:
            ticket.status = new_status
            if new_status == "resolved":
                ticket.resolved_at = timezone.now()

        if notes:
            ticket.resolution_notes = notes

        ticket.save(update_fields=["status", "resolution_notes", "resolved_at"])
        return redirect("campo:ticket_detail", pk=pk)


# ---------------------------------------------------------------------------
# Rutas históricas del equipo de campo
# ---------------------------------------------------------------------------

@da_decorator
class CampoRouteHistoryView(TemplateView):
    template_name = "dashboard/campo/route_history.html"

    def get_context_data(self, **kwargs):
        from apps.dashboard.models import FieldUser, FieldLocationLog
        ctx = super().get_context_data(**kwargs)
        ctx["field_users"] = FieldUser.objects.select_related("user").order_by("user__first_name")
        # Días disponibles (últimos 90) para el usuario seleccionado
        user_pk  = self.request.GET.get("user")
        date_str = self.request.GET.get("date", timezone.localdate().isoformat())
        ctx["selected_user"]  = user_pk
        ctx["selected_date"]  = date_str
        if user_pk:
            ctx["available_dates"] = (
                FieldLocationLog.objects
                .filter(user__pk=user_pk)
                .values_list("shift_date", flat=True)
                .distinct()
                .order_by("-shift_date")[:90]
            )
        return ctx


@da_decorator
class CampoRouteJsonView(View):
    """Devuelve puntos de ruta + tareas completadas para un usuario y fecha."""

    def get(self, request):
        from apps.dashboard.models import FieldLocationLog, DeliveryTask, FieldUser
        user_pk  = request.GET.get("user")
        date_str = request.GET.get("date")
        if not user_pk or not date_str:
            return JsonResponse({"points": [], "tasks": []})

        points = list(
            FieldLocationLog.objects
            .filter(user__pk=user_pk, shift_date=date_str)
            .values("latitude", "longitude", "recorded_at")
            .order_by("recorded_at")
        )
        # Tareas completadas ese día por ese usuario
        try:
            fu = FieldUser.objects.get(user__pk=user_pk)
            tasks_qs = DeliveryTask.objects.filter(
                field_user=fu, status="done",
                completed_at__date=date_str,
            ).values("pk", "title", "client_name", "address", "completion_invoice",
                     "payment_method", "completed_at")
            tasks = list(tasks_qs)
        except FieldUser.DoesNotExist:
            tasks = []

        return JsonResponse({
            "points": [
                {
                    "lat": float(p["latitude"]),
                    "lng": float(p["longitude"]),
                    "t":   p["recorded_at"].strftime("%H:%M"),
                }
                for p in points
            ],
            "tasks": [
                {
                    "pk":      t["pk"],
                    "title":   t["title"],
                    "client":  t["client_name"],
                    "address": t["address"],
                    "invoice": t["completion_invoice"],
                    "payment": t["payment_method"],
                    "time":    t["completed_at"].strftime("%H:%M") if t["completed_at"] else "",
                }
                for t in tasks
            ],
        })
