# Collaborative Markdown Editor - Backend Specification Guide (Django Stack)

This blueprint details the architectural specifications, endpoints, and data layers required to build a robust **Django backend** to serve our fully interactive, collaborative Markdown Editor, specifically focusing on **No-Sign-Up / Guest Portability & Real-Time Syncing Rooms**.

---

## 1. Frontend Technology Stack

The client-side editor is a highly polished single-page workspace built with the following technologies:
*   **Framework:** React (v19) with Vite (v6) for super-fast building and bundling.
*   **Language:** TypeScript (Type-safe metadata, files, and settings mappings).
*   **Styling:** Tailwind CSS (Modern fluid spacing, responsive layouts, custom scrollbars, and light/dark theme selector states).
*   **Synchronization Engine:** HTML5 BroadcastChannel API for automated multi-tab and multi-window sync during collaborative offline rooms.
*   **Portability Layer:** Portable JSON schema workspace exporter and importer to move files across browsers instantly without requiring authentication.
*   **Rendering:** Customized client-side Markdown AST Lexer supporting headers, tables, task checklists, code highlighter panels, tip callouts, and page rules.
*   **Icons:** Lucide React (Clean vector UI iconography).
*   **Animations:** Framer Motion / Motion (Micro-interactions, active status pulsing, drag-&-drop file indicators, and warning callouts).

---

## 2. No-Sign-Up Collaborative Architecture

To solve the challenge of collaborating **without user accounts or signups**, the system operates with **Anonymous Guest Presence and Temporary Shared Rooms (`?room=xxxxx`)**:

### Local / Single-Device Workflow:
*   Users can immediately type on standard pages. Data is automatically preserved in the browser's `localStorage` state under `pandocs_files` and `pandocs_settings`.
*   A customized **Guest Collaborator Profile** (stored inside local storage as `pandocs_guest_presence`) lets users change their name and choose a vibrant avatar color at any time.

### Multi-Tab Offline & Local Network Workspace Sync:
*   When a collaborative session begins, users generate a virtual shared room identifier.
*   An active `BroadcastChannel` manages instant, zero-latency content broadcasts and presence triggers across all open windows.

### Django Live-Sync Room Extension (The Production Backend Solution):
When transitioning to a live online Django backend, we can coordinate anonymous sessions by mapping **Temporary Room Handles** to temporary storage spaces:

```
                      ┌────────────────────────────────────┐
                      │    Anonymous Collaborators Client  │
                      └────────────────┬───────────────────┘
                                       │
                      [WebSocket: /ws/collab/?room=alpha]
                                       │
                                       ▼
                      ┌────────────────────────────────────┐
                      │    Django Channels ASGI Consumer   │
                      └────────────────┬───────────────────┘
                                       │
                         [Pub/Sub Broadcast to Room Group]
                                       │
                                       ▼
                      ┌────────────────────────────────────┐
                      │    Redis Key-Value InMemory Store  │
                      │  (Holds doc contents & temporary   │
                      │   guest lists with 24hr TTL limit) │
                      └────────────────────────────────────┘
```

---

## 3. Database Schema Design & DRF Serializers

For a database layer that supports both durable persistence and temporary zero-login rooms, configure models in your Django apps:

```python
# models.py
import uuid
from django.db import models

class CollaborativeRoom(models.Model):
    """
    Represents a temporary shared editing canvas created on-the-fly.
    No user registrations are required to join.
    """
    id = models.CharField(
        max_length=64, 
        primary_key=True, 
        default=uuid.uuid4, 
        help_text="Unique room suffix, e.g., 'room-a982f1'"
    )
    name = models.CharField(max_length=255, default="Shared Workspace Document.md")
    content = models.TextField(blank=True, default="# Shared Document Markdown\n")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Room {self.id} - {self.name}"

class GuestPresence(models.Model):
    """
    Tracks who is actively viewing/editing inside a collaborative room.
    These records can expire or be purged periodically.
    """
    peer_id = models.CharField(max_length=64, primary_key=True, help_text="Random peer session token")
    room = models.ForeignKey(CollaborativeRoom, on_delete=models.CASCADE, related_name="listeners")
    name = models.CharField(max_length=150, default="Peer Guest")
    color_class = models.CharField(max_length=50, default="bg-indigo-600")
    avatar_style = models.CharField(
        max_length=50, 
        default="shapes", 
        help_text="Custom avatar visualization style (e.g., shapes, bottts, lorelei, pixel-art, initials, adventurer)"
    )
    last_pulse = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} in details room {self.room_id}"

class DocumentRevision(models.Model):
    """
    Saves snapshots of CollaborativeRooms periodically or on user request,
    supplementing client-side undo/redo with a permanent server revision timeline.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(CollaborativeRoom, on_delete=models.CASCADE, related_name="revisions")
    content = models.TextField()
    updated_by_name = models.CharField(max_length=150, default="Anonymous Peer")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Revision of {self.room_id} at {self.created_at}"
```

### Django REST Framework Serializers
Connect the anonymous session models directly to responsive API structures using Django REST Framework Serializers:

```python
# serializers.py
from rest_framework import serializers
from .models import CollaborativeRoom, GuestPresence, DocumentRevision

class GuestPresenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestPresence
        fields = ['peer_id', 'room', 'name', 'color_class', 'avatar_style', 'last_pulse']
        read_only_fields = ['last_pulse']

class DocumentRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentRevision
        fields = ['id', 'room', 'content', 'updated_by_name', 'created_at']
        read_only_fields = ['id', 'created_at']
```

class CollaborativeRoomSerializer(serializers.ModelSerializer):
    listeners = GuestPresenceSerializer(many=True, read_only=True)
    
    class Meta:
        model = CollaborativeRoom
        fields = ['id', 'name', 'content', 'created_at', 'updated_at', 'listeners']
```

---

## 4. Work Portability Format (JSON Exchange Blueprint)

To preserve the absolute privacy of users, our backup and restore functionality operates on a standardized, portable JSON format that your Django REST API can also consume to bulk-upload documents:

```json
{
  "files": [
    {
      "id": "reviewing-changes",
      "name": "Reviewing Changes.md",
      "author": "Jada Gamble",
      "lastUpdated": "Apr 28, 2022",
      "content": "# How to review..."
    }
  ],
  "settings": {
    "showLineNumbers": true,
    "showMinimap": true,
    "sidebarCollapsed": false,
    "viewMode": "split",
    "activeTheme": "zinc",
    "darkMode": false
  },
  "timestamp": 1718814231000
}
```

---

## 5. HTTP API Endpoints (Django REST Views & ViewSets)

Below are the complete, production-ready Django REST Framework views. It leverages DRF ViewSets to manage Collaborative Rooms natively, including custom actions to update Guest Heartbeat signals and import workspace backups:

```python
# views.py
import markdown
import weasyprint
from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import CollaborativeRoom, GuestPresence, DocumentRevision
from .serializers import CollaborativeRoomSerializer, GuestPresenceSerializer, DocumentRevisionSerializer

class CollaborativeRoomViewSet(viewsets.ModelViewSet):
    """
    Handles standard CRUD for anonymous collaborative rooms.
    Allows saving raw markdown, loading details, pulsing live guest states, and restoring portable backups.
    """
    queryset = CollaborativeRoom.objects.all()
    serializer_class = CollaborativeRoomSerializer
    lookup_field = 'id'

    @action(detail=True, methods=['post'], url_path='pulse')
    def pulse_presence(self, request, id=None):
        """
        Refreshes a guest peer's heartbeat context within the collaborative workspace.
        Payload: {"peer_id": "xxx", "name": "Guest Peer", "color_class": "bg-indigo-600", "avatar_style": "pixel-art"}
        """
        room = self.get_object()
        peer_id = request.data.get('peer_id')
        name = request.data.get('name', 'Anonymous Peer')
        color_class = request.data.get('color_class', 'bg-indigo-600')
        avatar_style = request.data.get('avatar_style', 'shapes')

        if not peer_id:
            return Response({"error": "peer_id parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        presence, created = GuestPresence.objects.update_or_create(
            peer_id=peer_id,
            defaults={
                'room': room,
                'name': name,
                'color_class': color_class,
                'avatar_style': avatar_style
            }
        )
        serializer = GuestPresenceSerializer(presence)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='revisions')
    def list_revisions(self, request, id=None):
        """
        Retrieves all historic server-side revision snapshots for the document.
        """
        room = self.get_object()
        revisions = room.revisions.all()
        serializer = DocumentRevisionSerializer(revisions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='save-revision')
    def save_revision(self, request, id=None):
        """
        Manually trigger a revision checkpoint snapshot in the server history timeline.
        Payload: {"updated_by_name": "Jada Gamble"}
        """
        room = self.get_object()
        updated_by_name = request.data.get('updated_by_name', 'Anonymous Peer')
        
        # Don't create empty or redundant duplicate revision if the content hasn't changed from the last revision
        last_revision = room.revisions.first()
        if last_revision and last_revision.content == room.content:
            return Response(
                {"info": "Document content is identical to the latest snapshot. Revision skipped."},
                status=status.HTTP_200_OK
            )

        revision = DocumentRevision.objects.create(
            room=room,
            content=room.content,
            updated_by_name=updated_by_name
        )
        serializer = DocumentRevisionSerializer(revision)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='rollback')
    def rollback_to_revision(self, request, id=None):
        """
        Restores the active document's contents back to matching a selected historical snapshot.
        Payload: {"revision_id": "xxxx"}
        """
        room = self.get_object()
        revision_id = request.data.get('revision_id')
        if not revision_id:
            return Response({"error": "revision_id is required for rollbacks"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            revision = room.revisions.get(id=revision_id)
        except DocumentRevision.DoesNotExist:
            return Response({"error": "Specified revision snapshot not found"}, status=status.HTTP_404_NOT_FOUND)

        # Update document room content in main db
        room.content = revision.content
        room.save()

        return Response({
            "success": True,
            "message": f"Successfully rolled back document contents to revision {revision.id}",
            "content": room.content
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='backup')
    def restore_backup(self, request):
        """
        Parses portable JSON structures and imports/restores them into active workspaces.
        """
        files_data = request.data.get('files', [])
        imported_count = 0
        for doc in files_data:
            room_id = doc.get('id', '')
            if room_id:
                CollaborativeRoom.objects.update_or_create(
                    id=room_id,
                    defaults={
                        'name': doc.get('name', 'Untitled.md'),
                        'content': doc.get('content', '')
                    }
                )
                imported_count += 1
        return Response({"success": True, "imported_files_count": imported_count}, status=status.HTTP_200_OK)


# --- B. Dynamic PDF Rendering View (WeasyPrint) ---

def export_as_pdf(request, room_id):
    """
    Compiles active markdown content and generates a portable PDF file on the fly.
    """
    try:
        room = CollaborativeRoom.objects.get(id=room_id)
        content = room.content
        title = room.name
    except CollaborativeRoom.DoesNotExist:
        content = "# New Workspace"
        title = "Document.md"

    # Convert markdown contents to HTML format
    html_body = markdown.markdown(content, extensions=['tables', 'fenced_code', 'codehilite'])

    # Build response variables aligned with the page styling criteria
    context = {
        'title': title,
        'body': html_body,
        'last_updated': 'Synced Live'
    }
    rendered_html = render_to_string('pdf_template.html', context)
    pdf_bytes = weasyprint.HTML(string=rendered_html).write_pdf()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{title}.pdf"'
    return response
```

---

## 6. WebSocket Collaboration Server (Django Channels)

### Consumers Setup
WebSocket channels act as the central message relays. If peer `Guest 438` types, the letter changes are broadcasted:

```python
# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class DocumentRoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'collab_room_{self.room_id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        payload = json.loads(text_data)
        
        # Format aligned with real-time payload updates
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'broadcast_room_change',
                'sender_id': payload.get('senderId'),
                'data': payload
            }
        )

    async def broadcast_room_change(self, event):
        await self.send(text_data=json.dumps(event['data']))
```

---

## 7. Deployment Considerations & Security

1.  **CORS Allowed Origins:**
    Ensure Django allows connection origins from AI Studio preview tools:
    ```python
    CORS_ALLOWED_ORIGINS = [
        "https://ai.studio",
        "http://localhost:3000",
        "https://*.aistudio-preview.com",
    ]
    CORS_ALLOW_CREDENTIALS = True
    ```
2.  **Anonymous Room Sweeper Cron:** Setup a simple background celery worker task to automatically delete inactive Rooms or Guest logs after 24 hours to keep the Redis cache cleanly organized.
3.  **PDF Static Compilers:** Make sure your production runtime includes `pango` and `cairo` native packages for the PDF compiling tools.

---

## 8. Database Migrations & Initial Data Seeding

### Running Database Migrations
To create and apply the database schemas for Collaborative Rooms and Guest Presence records inside your Django project, execute:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Writing a Custom Seeding Script
You can seed the database with initial standard templates (such as "Welcome to Pulse MD.md") using a Django Management Command or a simple data migration. Create a file `your_app/management/commands/seed_rooms.py`:

```python
# your_app/management/commands/seed_rooms.py
from django.core.management.base import BaseCommand
from your_app.models import CollaborativeRoom

class Command(BaseCommand):
    help = "Seeds database with default markdown templates"

    def handle(self, *args, **options):
        default_content = """# Welcome to Pulse MD 🚀

Pulse MD is a secure, collaborative, real-time Markdown editor.

## Key Features:
* **Real-time Live Rooms**: Work with teammates completely sign-up free.
* **Astounding Outline Navigation**: Fast, dynamic Table of Contents jumps.
* **Portable Office Backup**: Instantly run backups to local JSON and restore configurations.
"""
        room, created = CollaborativeRoom.objects.get_or_create(
            id="default-welcome-room",
            defaults={
                "name": "Welcome to Pulse MD.md",
                "content": default_content
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Successfully seeded default welcome room!"))
        else:
            self.stdout.write(self.style.WARNING("Default welcome room already exists."))
```

---

## 9. Local Micro-Services API Integration & Testing

### A. Testing the Room Metadata & Heartbeat Pulse Endpoint
Use curl or Postman to test live guest pulses with custom styles and collaboration notifications:
```bash
# Request heartbeat pulse to active room with an explicit avatar_style
curl -X POST http://localhost:8000/api/rooms/default-welcome-room/pulse/ \
     -H "Content-Type: application/json" \
     -d '{
       "peer_id": "client-user-992f",
       "name": "Jada Gamble",
       "color_class": "bg-indigo-600",
       "avatar_style": "pixel-art"
     }'
```

### B. Testing Server-Backed Revision Snapshots & Reversions
 supplement client-side undo/redo with server checkpoints and state rollbacks:

```bash
# 1. Trigger a custom document markdown revision snap-shot
curl -X POST http://localhost:8000/api/rooms/default-welcome-room/save-revision/ \
     -H "Content-Type: application/json" \
     -d '{
       "updated_by_name": "Jada Gamble"
     }'

# 2. Get list of all saved revisions for the document
curl -X GET http://localhost:8000/api/rooms/default-welcome-room/revisions/

# 3. Rollback the active room contents back to matching a unique snapshot
curl -X POST http://localhost:8000/api/rooms/default-welcome-room/rollback/ \
     -H "Content-Type: application/json" \
     -d '{
       "revision_id": "paste-your-revision-uuid-here"
     }'
```

### C. Bulk Recovery Export and Migration Import Endpoint
Verify backup parsing logic:
```bash
# Request restoration of workspace JSON state
curl -X POST http://localhost:8000/api/rooms/backup/ \
     -H "Content-Type: application/json" \
     -d '{
       "files": [
         {
           "id": "restored-doc-1",
           "name": "Restored Document.md",
           "content": "# Restored content from offline JSON backup!"
         }
       ]
     }'
```

