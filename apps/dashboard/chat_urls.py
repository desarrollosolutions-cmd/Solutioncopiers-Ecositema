"""URLs del chat interno — /chat/ (admins, asesoras y técnicos/mensajeros)"""
from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    path("", views.ChatListView.as_view(), name="list"),
    path("iniciar/", views.ChatStartView.as_view(), name="start"),
    path("no-leidos/json/", views.ChatUnreadCountJsonView.as_view(), name="unread_json"),
    path("perfil/", views.ProfileEditView.as_view(), name="profile_edit"),
    path("miembros/", views.MemberDirectoryView.as_view(), name="members"),
    path("miembros/<int:pk>/", views.ProfileDetailView.as_view(), name="profile_detail"),
    path("<int:pk>/", views.ChatThreadView.as_view(), name="thread"),
    path("<int:pk>/nuevos/", views.ChatPollView.as_view(), name="poll"),
]
