import uuid
from django.db import models


class CollaborativeRoom(models.Model):
    """Temporary shared editing canvas — no user registration required."""
    id = models.CharField(
        max_length=64,
        primary_key=True,
        default=uuid.uuid4,
        help_text="Unique room identifier, e.g. 'room-a982f1'",
    )
    name = models.CharField(max_length=255, default="Shared Workspace Document.md")
    content = models.TextField(blank=True, default="# Shared Document Markdown\n")
    is_live = models.BooleanField(
        default=True,
        help_text="When False, the room's link is revoked — no new WebSocket "
        "connections are accepted and existing ones are force-closed.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Room {self.id} – {self.name}"


class GuestPresence(models.Model):
    """Tracks anonymous peers actively viewing/editing inside a room."""
    peer_id = models.CharField(
        max_length=64,
        primary_key=True,
        help_text="Random peer session token generated on the client",
    )
    room = models.ForeignKey(
        CollaborativeRoom, on_delete=models.CASCADE, related_name="listeners"
    )
    name = models.CharField(max_length=150, default="Peer Guest")
    color_class = models.CharField(max_length=50, default="bg-indigo-600")
    avatar_style = models.CharField(
        max_length=50,
        default="shapes",
        help_text="Avatar style: shapes | bottts | lorelei | pixel-art | initials | adventurer",
    )
    last_pulse = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} in room {self.room_id}"


class DocumentRevision(models.Model):
    """Server-side snapshot of a room's content at a point in time."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        CollaborativeRoom, on_delete=models.CASCADE, related_name="revisions"
    )
    content = models.TextField()
    updated_by_name = models.CharField(max_length=150, default="Anonymous Peer")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Revision of room {self.room_id} at {self.created_at}"


class PageVisit(models.Model):
    """A single recorded visit to the frontend, sent by a lightweight tracking call."""
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    browser = models.CharField(max_length=50, blank=True, default="Unknown")
    operating_system = models.CharField(max_length=50, blank=True, default="Unknown")
    device_type = models.CharField(max_length=20, blank=True, default="Desktop")
    path = models.CharField(max_length=255, blank=True, default="/")
    referrer = models.CharField(max_length=500, blank=True, default="")
    visitor_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Client-generated id stored in the browser's localStorage — "
        "used to approximate unique visitors (not a real identity).",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ip_address} – {self.browser}/{self.operating_system} @ {self.created_at}"
