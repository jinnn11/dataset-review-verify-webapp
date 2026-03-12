from __future__ import annotations

import re
from pathlib import Path

from app.core.config import DatasetConfig


class FilenameParser:
    def __init__(self, config: DatasetConfig):
        self.config = config
        self.mask_pattern = re.compile(config.mask_regex)
        self.generated_pattern = re.compile(config.generated_regex)
        self.allowed_extensions = {ext.lower() for ext in config.allowed_extensions}

    def is_supported(self, path: Path) -> bool:
        return path.suffix.lower() in self.allowed_extensions

    def parse_mask_group_key(self, path: Path) -> str | None:
        if not self.is_supported(path):
            return None
        match = self.mask_pattern.match(path.name)
        if not match:
            return None
        return match.group("group_key")

    def parse_generated_group_key(self, path: Path) -> str | None:
        if not self.is_supported(path):
            return None
        match = self.generated_pattern.match(path.name)
        if not match:
            return None
        return match.group("group_key")
