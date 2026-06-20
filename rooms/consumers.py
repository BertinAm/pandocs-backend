"""
Django Channels WebSocket consumer for real-time collaborative editing.

Requires:
    pip install channels channels-redis daphne

The consumer joins a channel group per room_id and broadcasts any received
payload to all other connected peers in that room.
"""
import json

try:
    from channels.generic.websocket import AsyncWebsocketConsumer

    class DocumentRoomConsumer(AsyncWebsocketConsumer):
        async def connect(self):
            self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
            self.room_group_name = f"collab_room_{self.room_id}"

            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()

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

except ImportError:
    # channels is not installed — define a stub so the module can be imported
    # without crashing. WebSocket functionality will be unavailable.
    class DocumentRoomConsumer:  # type: ignore[no-redef]
        pass
