"""
Migration: Rename tts.providers to tts.models in config file.

Unifies naming convention with llm.models for consistency.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class Migration:
    id = "v0_1_0_002_tts_providers_to_models"
    description = "Rename tts.providers to tts.models in config file"

    @staticmethod
    def run() -> int:
        """Migrate conf.yaml: tts.providers -> tts.models"""
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "config" / "conf.yaml"

        if not config_path.exists():
            logger.info("No conf.yaml found, skipping config migration")
            return 0

        content = config_path.read_text(encoding="utf-8")

        # Check if migration needed
        if "tts:" not in content:
            logger.info("No tts section in config")
            return 0

        # Find tts section and check for providers key
        tts_match = re.search(r"^tts:\s*\n((?:[ \t]+.*\n)*)", content, re.MULTILINE)
        if not tts_match:
            return 0

        tts_section = tts_match.group(1)
        has_providers = re.search(r"^\s+providers:", tts_section, re.MULTILINE)
        has_models = re.search(r"^\s+models:", tts_section, re.MULTILINE)

        if has_models and not has_providers:
            logger.info("Config already migrated (tts.models exists)")
            return 0

        if not has_providers:
            logger.info("No tts.providers found in config")
            return 0

        # Replace providers with models
        new_content = re.sub(
            r"(^tts:\s*\n(?:[ \t]+(?!providers:).*\n)*)([ \t]+)providers:",
            r"\1\2models:",
            content,
            flags=re.MULTILINE,
        )

        if new_content != content:
            config_path.write_text(new_content, encoding="utf-8")
            logger.info("Migrated tts.providers -> tts.models in conf.yaml")
            return 1

        return 0
