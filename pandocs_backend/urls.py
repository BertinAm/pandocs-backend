from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include


def health_check(request):
    """Lightweight endpoint for Render's health check probe."""
    return HttpResponse("ok")


urlpatterns = [
    path("healthz", health_check),
    path("admin/", admin.site.urls),
    path("api/", include("rooms.urls")),
]
