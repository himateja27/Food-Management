import re

SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\bauthorization\s*[:=]?\s*(?:basic|bearer)\s+[^\s,;]+"),
    re.compile(r"(?i)\b(?:basic|bearer)\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\b(?:api[_ -]?key|password|passphrase|access[_ -]?token|secret)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\b(?:api[_ -]?key|password|passphrase|access[_ -]?token|secret)\s+(?:is\s+)?[^\s,;]+"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
)


def redact_sensitive_content(content: str) -> str:
    redacted = content
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub("[redacted]", redacted)
    return redacted
