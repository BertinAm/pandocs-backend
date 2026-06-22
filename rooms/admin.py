from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from .models import CollaborativeRoom, GuestPresence, DocumentRevision, PageVisit


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


@admin.register(PageVisit)
class PageVisitAdmin(admin.ModelAdmin):
    list_display = ["created_at", "ip_address", "browser", "operating_system", "device_type", "path", "visitor_id"]
    list_filter = ["browser", "operating_system", "device_type"]
    search_fields = ["ip_address", "path", "referrer", "visitor_id", "user_agent"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    readonly_fields = [f.name for f in PageVisit._meta.fields]

    def has_add_permission(self, request):
        # Visits are only ever created by the public tracking endpoint
        return False

    def changelist_view(self, request, extra_context=None):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)
        year_start = today_start.replace(month=1, day=1)

        qs = PageVisit.objects.all()
        extra_context = extra_context or {}
        extra_context["visit_summary"] = {
            "today": qs.filter(created_at__gte=today_start).count(),
            "this_week": qs.filter(created_at__gte=week_start).count(),
            "this_month": qs.filter(created_at__gte=month_start).count(),
            "this_year": qs.filter(created_at__gte=year_start).count(),
            "all_time": qs.count(),
            "unique_visitors": qs.exclude(visitor_id="").values("visitor_id").distinct().count(),
        }
        return super().changelist_view(request, extra_context=extra_context)
