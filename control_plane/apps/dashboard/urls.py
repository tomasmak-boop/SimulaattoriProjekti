from django.urls import path

from control_plane.apps.dashboard import views


app_name = "dashboard"

urlpatterns = [
    path("", views.session_list, name="session-list"),
]