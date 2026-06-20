from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CollaborativeRoomViewSet, export_as_pdf

router = DefaultRouter()
router.register(r"rooms", CollaborativeRoomViewSet, basename="room")

urlpatterns = [
    path("", include(router.urls)),
    path("rooms/<str:room_id>/export-pdf/", export_as_pdf, name="export-pdf"),
]
