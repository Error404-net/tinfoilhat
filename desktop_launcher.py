"""PyInstaller entry point; keep package-relative imports intact."""

from tinfoilhat.desktop import main

if __name__ == "__main__":
    raise SystemExit(main())
