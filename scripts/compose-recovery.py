#!/usr/bin/env python3
"""Back up and restore the database and local artifact volume of a stopped deployment."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

FILES = ("database.dump", "objects.tar")
PG_CONNECTION = '-U "$POSTGRES_USER" -d "$POSTGRES_DB"'
MUTATING = {"api", "worker", "scheduler", "frontend", "migrate"}


def checksum(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def run(args):
    compose = [
        "docker",
        "compose",
        "--env-file",
        args.env_file,
        "--project-name",
        args.project,
    ]

    def command(*parameters, **kwargs):
        return subprocess.run([*compose, *parameters], check=True, **kwargs)

    def postgres(script, **kwargs):
        return command("exec", "-T", "postgres", "sh", "-ec", script, **kwargs)

    def objects(action, **kwargs):
        return command(
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "api",
            "python",
            "-m",
            "app.ops.objects",
            action,
            **kwargs,
        )

    running = command(
        "ps", "--status", "running", "--services", capture_output=True, text=True
    )
    if MUTATING.intersection(running.stdout.split()):
        raise SystemExit(
            "Stop frontend, API, worker, scheduler and migration containers first."
        )
    command("up", "-d", "--wait", "postgres")
    directory = args.directory.resolve()
    if args.command == "backup":
        if directory.exists():
            raise SystemExit("Choose a new backup directory.")
        if not directory.parent.is_dir():
            raise SystemExit("Create the backup parent directory first.")
        with TemporaryDirectory(
            dir=directory.parent, prefix=".analyst-backup-"
        ) as scratch:
            bundle = Path(scratch) / "bundle"
            bundle.mkdir(mode=0o700)
            with (bundle / FILES[0]).open("wb") as output:
                postgres(
                    f"pg_dump {PG_CONNECTION} --format=custom --no-owner --no-acl",
                    stdout=output,
                )
            with (bundle / FILES[1]).open("wb") as output:
                objects("export", stdout=output)
            manifest = {
                "format": 1,
                "sha256": {name: checksum(bundle / name) for name in FILES},
            }
            (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            if directory.exists():
                raise SystemExit("Backup destination appeared during export.")
            bundle.rename(directory)
        print(f"Backup verified and saved at {directory}")
        return

    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest != {
        "format": 1,
        "sha256": {name: checksum(directory / name) for name in FILES},
    }:
        raise SystemExit("Backup checksum validation failed.")
    count = postgres(
        f"""psql {PG_CONNECTION} -Atc "SELECT count(*) FROM pg_class c JOIN pg_namespace n
        ON n.oid=c.relnamespace WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
        AND c.relkind IN ('r', 'p', 'v', 'm', 'S')" """,
        capture_output=True,
        text=True,
    )
    if count.stdout.strip() != "0":
        raise SystemExit("Restore requires a fresh PostgreSQL database.")
    objects("empty")
    with (directory / FILES[0]).open("rb") as dump:
        postgres(
            f"pg_restore {PG_CONNECTION} --single-transaction --exit-on-error --no-owner --no-acl",
            stdin=dump,
        )
    with (directory / FILES[1]).open("rb") as data:
        objects("restore", stdin=data)
    print(f"Restored database and objects to {args.project}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["backup", "restore"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--project", default="analyst-workspace")
    parser.add_argument("--env-file", default=".env")
    run(parser.parse_args())
