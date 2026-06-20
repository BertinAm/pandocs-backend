"""
ASGI entry point for Pandocs Backend.
Handles both HTTP (via Django) and WebSocket (via Django Channels).
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pandocs_backend.settings")

django_asgi_app = get_asgi_application()

try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from rooms.routing import websocket_urlpatterns

    application = ProtocolTypeRouter(
        {
            "http": django_asgi_app,
            "websocket": AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            ),
        }
    )
except ImportError:
    # channels not installed — serve HTTP only
    application = django_asgi_app
