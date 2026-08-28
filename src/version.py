"""Single source of truth for the app version.

Bump __version__ on every release. The version is:
- reported by /health so the dashboard can show it
- compared against the latest GitHub Release tag by the updater
- embedded in the built exe's filename by event-printer.spec

Keep it a plain "MAJOR.MINOR.PATCH" string (no leading "v") — the updater
tolerates a "v" prefix on the release tag, but the canonical value here
stays clean.
"""

__version__ = "1.0.0"
