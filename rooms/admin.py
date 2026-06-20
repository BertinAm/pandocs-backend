from django.contrib import admin
from .models import CollaborativeRoom, GuestPresence, DocumentRevision


class GuestPresenceInline(admin.TabularInline):
    model = GuestPresence
    extra = 0
    readonly_fields = ["last_pulse"]


class DocumentRevisionInline(admin.TabularInline):
    model = DocumentRevision
    extra = 0
    readonly_fields = ["id", "created_at"]
    fields = ["updated_by_name", "created_at"]


@admin.register(CollaborativeRoom)
class CollaborativeRoomAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "created_at", "updated_at", "listener_count", "revision_count"]
    search_fields = ["id", "name"]
    ordering = ["-updated_at"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [GuestPresenceInline, DocumentRevisionInline]

    def listener_count(self, obj):
        return obj.listeners.count()
    listener_count.short_description = "Active guests"

    def revision_count(self, obj):
        return obj.revisions.count()
    revision_count.short_description = "Revisions"


@admin.register(GuestPresence)
class GuestPresenceAdmin(admin.ModelAdmin):
    list_display = ["peer_id", "name", "room", "color_class", "avatar_style", "last_pulse"]
    search_fields = ["peer_id", "name", "room__id", "room__name"]
    list_filter = ["avatar_style"]
    ordering = ["-last_pulse"]
    readonly_fields = ["last_pulse"]


@admin.register(DocumentRevision)
class DocumentRevisionAdmin(admin.ModelAdmin):
    list_display = ["id", "room", "updated_by_name", "created_at"]
    search_fields = ["room__id", "room__name", "updated_by_name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at"]
