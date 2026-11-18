"""Stream a local artifact-volume archive for the Compose recovery tool."""

import sys
import tarfile
from pathlib import Path

from app.core.config import settings

PREFIXES = {"datasets", "reports", "staging"}


def object_paths(root):
    return sorted(path for folder in PREFIXES for path in (root / folder).rglob("*") if path.is_file())


def export(root, stream):
    with tarfile.open(fileobj=stream, mode="w|") as archive:
        for path in object_paths(root):
            if path.is_symlink() or root not in path.resolve().parents:
                raise ValueError("Object storage contains a link.")
            archive.add(path, arcname=path.relative_to(root), recursive=False)


def restore(root, stream):
    if any((root / folder).exists() for folder in PREFIXES):
        raise ValueError("Restore requires an empty object volume.")
    with tarfile.open(fileobj=stream, mode="r|") as archive:
        for member in archive:
            path = Path(member.name)
            if (
                not member.isfile()
                or path.is_absolute()
                or len(path.parts) != 3
                or path.parts[0] not in PREFIXES
                or ".." in path.parts
            ):
                raise ValueError("Archive contains an unexpected object path.")
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output, archive.extractfile(member) as source:
                while chunk := source.read(65536):
                    output.write(chunk)


def main():
    config = settings()
    if config.s3_bucket:
        raise ValueError("Use the bucket's backup and restore procedure for S3 storage.")
    root = config.storage_dir.resolve()
    command = sys.argv[1]
    if command == "export":
        export(root, sys.stdout.buffer)
    elif command == "restore":
        restore(root, sys.stdin.buffer)
    elif command == "empty":
        if any((root / folder).exists() for folder in PREFIXES):
            raise ValueError("Restore requires an empty object volume.")
    else:
        raise ValueError("Unknown object backup command.")


if __name__ == "__main__":
    main()
