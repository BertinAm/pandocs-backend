"""
Dumps the Postgres database to a timestamped .sql file via pg_dump,
and optionally uploads it to S3-compatible storage.

Usage:
    python manage.py backup_db
    python manage.py backup_db --output-dir backups

Environment variables:
    DATABASE_URL          Required. Postgres connection string to dump.
    BACKUP_S3_BUCKET      Optional. If set, uploads the dump to this S3 bucket.
    AWS_ACCESS_KEY_ID     Required if BACKUP_S3_BUCKET is set.
    AWS_SECRET_ACCESS_KEY Required if BACKUP_S3_BUCKET is set.
    AWS_REGION            Optional, defaults to us-east-1.
"""
import datetime
import os
import subprocess

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Dumps the Postgres database to a timestamped .sql file (and optionally uploads to S3)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default="backups",
            help="Local directory to write the dump file to (default: backups/)",
        )

    def handle(self, *args, **options):
        database_url = os.getenv("DATABASE_URL")
        if not database_url or database_url.startswith("sqlite"):
            self.stderr.write(
                self.style.ERROR(
                    "DATABASE_URL is not set to a Postgres connection string — "
                    "pg_dump only works against Postgres, not the local SQLite fallback."
                )
            )
            return

        output_dir = options["output_dir"]
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        dump_path = os.path.join(output_dir, f"pandocs-{timestamp}.sql")

        self.stdout.write(f"Dumping database to {dump_path} ...")
        result = subprocess.run(
            ["pg_dump", database_url, "-f", dump_path, "--no-owner", "--no-privileges"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.stderr.write(self.style.ERROR(f"pg_dump failed: {result.stderr}"))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS(f"Backup written to {dump_path}"))

        bucket = os.getenv("BACKUP_S3_BUCKET")
        if bucket:
            self._upload_to_s3(dump_path, bucket)

    def _upload_to_s3(self, dump_path, bucket):
        try:
            import boto3
        except ImportError:
            self.stderr.write(
                self.style.WARNING("boto3 not installed — skipping S3 upload. Run: pip install boto3")
            )
            return

        key = f"backups/{os.path.basename(dump_path)}"
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        s3.upload_file(dump_path, bucket, key)
        self.stdout.write(self.style.SUCCESS(f"Uploaded to s3://{bucket}/{key}"))
