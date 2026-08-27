"""Privacy and synthetic boundary scan for offline fixtures (e04s02)."""

import re
from pathlib import Path

from nz_vehicle_data_pipeline.normalization.staging_models import SYNTHETIC_DISCLAIMER

# Prohibited patterns: credit cards, authorization headers, private keys
FORBIDDEN_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE),
    re.compile(r"BEGIN\s+(RSA|OPENSSH|EC|PRIVATE)\s+KEY", re.IGNORECASE),
    re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b"),  # Visa/Mastercard
    re.compile(r"password\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE),
]


def test_fixtures_contain_no_secrets_or_private_data() -> None:
    """Scan all fixture files to ensure no credentials, secrets, or private data exist."""
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    if not fixtures_dir.exists():
        return

    for file_path in fixtures_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix in {".json", ".xml", ".csv"}:
            content = file_path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_PATTERNS:
                assert not pattern.search(content), (
                    f"Prohibited pattern {pattern.pattern} matched in {file_path}"
                )

            # If it is a synthetic dealer or risk file, verify disclaimer
            if "synth" in file_path.name or "dealer" in file_path.name or "risk" in file_path.name:
                assert SYNTHETIC_DISCLAIMER in content, (
                    f"Synthetic fixture {file_path} missing mandatory disclaimer"
                )
