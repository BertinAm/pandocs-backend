from django.core.management.base import BaseCommand
from rooms.models import CollaborativeRoom

DEFAULT_CONTENT = """# Welcome to Pandocs

Pandocs is a secure, collaborative, real-time Markdown editor. No sign-up required.

## Key Features

* **Real-time Live Rooms**: Work with teammates completely sign-up free.
* **Astounding Outline Navigation**: Fast, dynamic Table of Contents jumps.
* **Portable Office Backup**: Instantly run backups to local JSON and restore configurations.
* **PDF Export**: Generate beautiful PDFs directly from your markdown.

## Getting Started

1. Create a new room or join an existing one via the `?room=` query parameter.
2. Share the URL with your team — they can join instantly.
3. All edits broadcast in real-time through WebSocket channels.

> Tip: Use the sidebar to navigate between documents and toggle dark mode.

---

*Happy writing!*
"""


class Command(BaseCommand):
    help = "Seeds the database with default Pandocs markdown templates"

    def handle(self, *args, **options):
        room, created = CollaborativeRoom.objects.get_or_create(
            id="default-welcome-room",
            defaults={
                "name": "Welcome to Pandocs.md",
                "content": DEFAULT_CONTENT,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Seeded default welcome room."))
        else:
            self.stdout.write(self.style.WARNING("Default welcome room already exists — skipped."))
