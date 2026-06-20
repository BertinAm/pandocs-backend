"""
Django Channels WebSocket consumer for real-time collaborative editing.

Requires:
    pip install channels channels-redis daphne

The consumer joins a channel group per room_id and broadcasts any received
payload to all other connected peers in that room. Connections are rejected
if the room has been marked not-live (link revoked via the stop-live REST
action), and any already-connected peers are force-closed when that happens.
"""
import json

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    from channels.db import database_sync_to_async

    class DocumentRoomConsumer(AsyncWebsocketConsumer):
        async def connect(self):
            self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
            self.room_group_name = f"collab_room_{self.room_id}"

            is_live = await self._get_or_create_room_is_live()
            if not is_live:
                # Room link has been revoked — refuse the connection outright.
                await self.close(code=4403)
                return

            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()

        @database_sync_to_async
        def _get_or_create_room_is_live(self):
            from .models import CollaborativeRoom
            room, _ = CollaborativeRoom.objects.get_or_create(
                id=self.room_id,
                defaults={"name": f"Live Document {self.room_id}", "is_live": True},
            )
            return room.is_live

        async def disconnect(self, close_code):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

        async def receive(self, text_data):
            payload = json.loads(text_data)

            # Relay the payload to every peer in the room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "broadcast_room_change",
                    "sender_id": payload.get("senderId"),
                    "data": payload,
                },
            )

        async def broadcast_room_change(self, event):
            """Called by group_send — forward the payload to this WebSocket client."""
            await self.send(text_data=json.dumps(event["data"]))

        async def broadcast_room_closed(self, event):
            """
            Called by group_send when a room's link is revoked (stop-live).
            Notify this client, then force-close its connection so the old
            link stops working for everyone, not just the peer who revoked it.
            """
            await self.send(text_data=json.dumps({"type": "room-closed"}))
            await self.close(code=4403)

except ImportError:
    # channels is not installed — define a stub so the module can be imported
    # without crashing. WebSocket functionality will be unavailable.
    class DocumentRoomConsumer:  # type: ignore[no-redef]
        pass
