from rest_framework import serializers
from .models import CollaborativeRoom, GuestPresence, DocumentRevision


class GuestPresenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestPresence
        fields = ["peer_id", "room", "name", "color_class", "avatar_style", "last_pulse"]
        read_only_fields = ["last_pulse"]


class DocumentRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentRevision
        fields = ["id", "room", "content", "updated_by_name", "created_at"]
        read_only_fields = ["id", "created_at"]


class CollaborativeRoomSerializer(serializers.ModelSerializer):
    listeners = GuestPresenceSerializer(many=True, read_only=True)

    class Meta:
        model = CollaborativeRoom
        fields = ["id", "name", "content", "is_live", "created_at", "updated_at", "listeners"]
