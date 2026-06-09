"""Shell command safety guard.

Deterministic pre-execution checks for shell commands. The template layer can
map casual language ("remove that folder") straight to shell commands, so the
guard is the last line of defence against catastrophic operations — especially
important because templates and tools are mutated by the self-improvement loop.
"""

import re
from typing import Optional


# Patterns that are never allowed, regardless of sandbox mode.
_BLOCKED_PATTERNS = [
    # Recursive deletion of root, home, or volume paths
    (r"rm\s+(-\w*\s+)*(/|~|\$HOME|/Users/\w+|/home/\w+)(\s|$)", "recursive delete of root/home path"),
    (r"rm\s+-\w*[rf]\w*\s+\*", "recursive wildcard delete"),
    # Disk / filesystem destruction
    (r"\bmkfs(\.\w+)?\b", "filesystem format command"),
    (r"\bdd\b.*\bof=/dev/", "raw write to device"),
    (r">\s*/dev/sd[a-z]", "raw write to device"),
    # Privilege escalation
    (r"\bsudo\b", "privilege escalation"),
    (r"\bsu\s+root\b", "privilege escalation"),
    # System control
    (r"\b(shutdown|reboot|halt|poweroff)\b", "system power command"),
    # Fork bomb
    (r":\(\)\s*\{.*\};\s*:", "fork bomb"),
    # Piping remote content into a shell
    (r"\b(curl|wget)\b[^|;]*\|\s*(ba)?sh", "piping remote script into shell"),
    # Recursive permission destruction on root paths
    (r"chmod\s+(-\w+\s+)*777\s+/(\s|$)", "world-writable root"),
    (r"chown\s+(-\w+\s+)*.*\s+/(\s|$)", "ownership change of root"),
    # Shell history / credential exfiltration helpers
    (r"\bhistory\s+-c\b", "history wipe"),
]

# rm targets must stay relative (sandbox-confined). Absolute paths are refused.
_RM_ABSOLUTE = re.compile(r"\brm\b[^|;&]*\s(/[^\s]*|~[^\s]*)", re.IGNORECASE)


def check_command(command: str) -> Optional[str]:
    """Return a rejection reason if the command is unsafe, else None."""
    if not command or not command.strip():
        return None

    normalized = command.strip()

    for pattern, reason in _BLOCKED_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return f"Blocked unsafe command ({reason}): {normalized!r}"

    if _RM_ABSOLUTE.search(normalized):
        return (
            f"Blocked unsafe command (rm on absolute path; deletions must stay "
            f"inside the sandbox workspace): {normalized!r}"
        )

    return None
