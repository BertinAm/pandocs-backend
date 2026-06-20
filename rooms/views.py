import re
from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import CollaborativeRoom, GuestPresence, DocumentRevision
from .serializers import (
    CollaborativeRoomSerializer,
    GuestPresenceSerializer,
    DocumentRevisionSerializer,
)

try:
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
except ImportError:
    async_to_sync = None
    get_channel_layer = None


# ---------------------------------------------------------------------------
# Lightweight markdown → HTML converter (uses only stdlib + re, no extra deps)
# ---------------------------------------------------------------------------

def _md_to_html(md: str) -> str:
    """
    Convert a subset of Markdown to HTML suitable for PDF rendering.
    Handles: headings, bold, italic, inline code, code fences, blockquotes,
    unordered/ordered/task lists, tables, horizontal rules, paragraphs, links.
    """
    lines = md.split("\n")
    html_parts: list[str] = []
    i = 0

    def inline(text: str) -> str:
        # Bold **text**
        text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
        # Italic *text*
        text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
        # Inline code
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        # Links [text](url)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        # Images ![alt](url)
        text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2"/>', text)
        return text

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Fenced code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip() or "text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_body = "\n".join(code_lines)
            html_parts.append(
                f'<pre><code class="language-{lang}">{code_body}</code></pre>'
            )
            i += 1
            continue

        # Headings
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            html_parts.append(f"<h{level}>{inline(m.group(2).strip())}</h{level}>")
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^(---|===|\*\*\*)$", stripped):
            html_parts.append("<hr/>")
            i += 1
            continue

        # Blockquote
        if stripped.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            inner = " ".join(quote_lines)
            html_parts.append(f"<blockquote><p>{inline(inner)}</p></blockquote>")
            continue

        # Table (pipe-based)
        if stripped.startswith("|") and i + 1 < len(lines) and lines[i + 1].strip().startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            if len(table_lines) >= 2:
                headers = [h.strip() for h in table_lines[0].split("|")[1:-1]]
                thead = "<tr>" + "".join(f"<th>{inline(h)}</th>" for h in headers) + "</tr>"
                tbody_rows = []
                for row_line in table_lines[2:]:
                    cells = [c.strip() for c in row_line.split("|")[1:-1]]
                    cells += [""] * (len(headers) - len(cells))
                    tbody_rows.append(
                        "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells[:len(headers)]) + "</tr>"
                    )
                html_parts.append(
                    f"<table><thead>{thead}</thead><tbody>{''.join(tbody_rows)}</tbody></table>"
                )
            continue

        # Unordered / task list
        if re.match(r"^(\*|-|\+)\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^(\*|-|\+)\s+", lines[i].strip()):
                item_text = re.sub(r"^(\*|-|\+)\s+", "", lines[i].strip())
                if item_text.startswith("[ ]"):
                    items.append(f'<li><input type="checkbox" disabled/> {inline(item_text[3:].strip())}</li>')
                elif item_text.lower().startswith("[x]"):
                    items.append(f'<li><input type="checkbox" checked disabled/> {inline(item_text[3:].strip())}</li>')
                else:
                    items.append(f"<li>{inline(item_text)}</li>")
                i += 1
            html_parts.append(f"<ul>{''.join(items)}</ul>")
            continue

        # Ordered list
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                item_text = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                items.append(f"<li>{inline(item_text)}</li>")
                i += 1
            html_parts.append(f"<ol>{''.join(items)}</ol>")
            continue

        # Blank line → skip
        if not stripped:
            i += 1
            continue

        # Paragraph — collect consecutive non-special lines
        para_lines = []
        while (
            i < len(lines)
            and lines[i].strip()
            and not re.match(r"^#{1,6}\s", lines[i])
            and not re.match(r"^(---|===|\*\*\*)$", lines[i].strip())
            and not lines[i].strip().startswith("```")
            and not lines[i].strip().startswith(">")
            and not lines[i].strip().startswith("|")
            and not re.match(r"^(\*|-|\+|\d+\.)\s+", lines[i].strip())
        ):
            para_lines.append(lines[i])
            i += 1

        if para_lines:
            html_parts.append(f"<p>{inline(' '.join(p.strip() for p in para_lines))}</p>")

    return "\n".join(html_parts)


# ---------------------------------------------------------------------------
# ViewSet
# ---------------------------------------------------------------------------

class CollaborativeRoomViewSet(viewsets.ModelViewSet):
    """
    CRUD for anonymous collaborative rooms plus custom actions:
    pulse, revisions, save-revision, rollback, backup.

    Rooms work on a "secret link" model — knowing the room ID grants
    access, like a Google Doc share link. The `list` action is disabled
    so the full room table is never exposed; you must already know a
    room's ID to retrieve, update, or otherwise act on it.
    """
    queryset = CollaborativeRoom.objects.all()
    serializer_class = CollaborativeRoomSerializer
    lookup_field = "id"

    def list(self, request, *args, **kwargs):
        return Response(
            {"detail": "Listing all rooms is disabled. Access a room directly via its id."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # ------------------------------------------------------------------
    # POST /api/rooms/<id>/pulse/
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="pulse")
    def pulse_presence(self, request, id=None):
        """Refresh a guest peer's heartbeat inside the collaborative workspace."""
        room = self.get_object()
        peer_id = request.data.get("peer_id")
        if not peer_id:
            return Response(
                {"error": "peer_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        presence, _ = GuestPresence.objects.update_or_create(
            peer_id=peer_id,
            defaults={
                "room": room,
                "name": request.data.get("name", "Anonymous Peer"),
                "color_class": request.data.get("color_class", "bg-indigo-600"),
                "avatar_style": request.data.get("avatar_style", "shapes"),
            },
        )
        return Response(GuestPresenceSerializer(presence).data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # POST /api/rooms/<id>/stop-live/
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="stop-live")
    def stop_live(self, request, id=None):
        """
        Revoke this room's live link. No new WebSocket connections will be
        accepted, and anyone currently connected is force-disconnected
        immediately — not just the peer who called this.
        """
        room = self.get_object()
        room.is_live = False
        room.save(update_fields=["is_live"])

        if get_channel_layer and async_to_sync:
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"collab_room_{room.id}",
                    {"type": "broadcast_room_closed"},
                )

        return Response(
            {"success": True, "message": "Live sharing stopped — the link is now closed for everyone."},
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # POST /api/rooms/<id>/go-live/
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="go-live")
    def go_live(self, request, id=None):
        """Re-activate a room's link after it was previously stopped."""
        room = self.get_object()
        room.is_live = True
        room.save(update_fields=["is_live"])
        return Response(CollaborativeRoomSerializer(room).data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # GET /api/rooms/<id>/revisions/
    # ------------------------------------------------------------------
    @action(detail=True, methods=["get"], url_path="revisions")
    def list_revisions(self, request, id=None):
        """List all server-side revision snapshots for this room."""
        room = self.get_object()
        serializer = DocumentRevisionSerializer(room.revisions.all(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # POST /api/rooms/<id>/save-revision/
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="save-revision")
    def save_revision(self, request, id=None):
        """Manually snapshot the current room content into revision history."""
        room = self.get_object()
        updated_by = request.data.get("updated_by_name", "Anonymous Peer")

        last = room.revisions.first()
        if last and last.content == room.content:
            return Response(
                {"info": "Content identical to latest snapshot — revision skipped."},
                status=status.HTTP_200_OK,
            )

        revision = DocumentRevision.objects.create(
            room=room, content=room.content, updated_by_name=updated_by
        )
        return Response(
            DocumentRevisionSerializer(revision).data, status=status.HTTP_201_CREATED
        )

    # ------------------------------------------------------------------
    # POST /api/rooms/<id>/rollback/
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="rollback")
    def rollback_to_revision(self, request, id=None):
        """Restore the room's content to a specific historical revision."""
        room = self.get_object()
        revision_id = request.data.get("revision_id")
        if not revision_id:
            return Response(
                {"error": "revision_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            revision = room.revisions.get(id=revision_id)
        except DocumentRevision.DoesNotExist:
            return Response(
                {"error": "Revision not found"}, status=status.HTTP_404_NOT_FOUND
            )

        room.content = revision.content
        room.save()
        return Response(
            {
                "success": True,
                "message": f"Rolled back to revision {revision.id}",
                "content": room.content,
            },
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # POST /api/rooms/backup/
    # ------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="backup")
    def restore_backup(self, request):
        """
        Accept a portable JSON workspace backup and upsert each file as a room.
        Payload: { "files": [{ "id", "name", "content" }] }
        """
        files_data = request.data.get("files", [])
        if not isinstance(files_data, list):
            return Response(
                {"error": "files must be a list"}, status=status.HTTP_400_BAD_REQUEST
            )

        imported = 0
        for doc in files_data:
            room_id = doc.get("id", "").strip()
            if not room_id:
                continue
            CollaborativeRoom.objects.update_or_create(
                id=room_id,
                defaults={
                    "name": doc.get("name", "Untitled.md"),
                    "content": doc.get("content", ""),
                },
            )
            imported += 1

        return Response(
            {"success": True, "imported_files_count": imported},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# PDF export view
# ---------------------------------------------------------------------------

def export_as_pdf(request, room_id):
    """
    Render the room's markdown as HTML and generate a PDF with ReportLab.
    Falls back to placeholder content when the room_id doesn't exist.
    """
    try:
        room = CollaborativeRoom.objects.get(id=room_id)
        content = room.content
        title = room.name
        author = "Pandocs Collaborative Editor"
    except CollaborativeRoom.DoesNotExist:
        content = "# Document Not Found\n\nThe requested room does not exist."
        title = "Document.md"
        author = "Pandocs"

    html_body = _md_to_html(content)
    rendered_html = render_to_string(
        "pdf_template.html",
        {"title": title, "body": html_body, "author": author},
    )

    # Use ReportLab via xhtml2pdf if available, else return the HTML for debugging.
    try:
        from xhtml2pdf import pisa
        import io

        buf = io.BytesIO()
        pisa_status = pisa.CreatePDF(rendered_html, dest=buf)
        if pisa_status.err:
            return HttpResponse("PDF generation failed", status=500)
        buf.seek(0)
        response = HttpResponse(buf.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{title}.pdf"'
        return response

    except ImportError:
        # xhtml2pdf not installed — return the rendered HTML so the endpoint is
        # still usable for testing without the optional dependency.
        return HttpResponse(rendered_html, content_type="text/html")
