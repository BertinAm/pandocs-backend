"""
Django Channels URL routing for WebSocket connections.
Registered in pandocs_backend/asgi.py.
"""
try:
    from django.urls import re_path
    from channels.routing import URLRouter
    from .consumers import DocumentRoomConsumer

    websocket_urlpatterns = [
        re_path(r"^ws/collab/(?P<room_id>[^/]+)/$", DocumentRoomConsumer.as_asgi()),
    ]
except ImportError:
    websocket_urlpatterns = []
