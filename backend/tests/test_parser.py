from pathlib import Path

from app.core.config import DatasetConfig
from app.services.parser import FilenameParser


def test_filename_parser_valid_patterns() -> None:
    cfg = DatasetConfig(
        mask_regex=r"^(?P<group_key>.+)_mask\.png$",
        generated_regex=r"^(?P<group_key>.+)_gen_[0-9]+\.png$",
        allowed_extensions=[".png"],
    )
    parser = FilenameParser(cfg)

    assert parser.parse_mask_group_key(Path("scene123_mask.png")) == "scene123"
    assert parser.parse_generated_group_key(Path("scene123_gen_4.png")) == "scene123"


def test_filename_parser_rejects_invalid_names() -> None:
    cfg = DatasetConfig(mask_regex=r"^(?P<group_key>.+)_mask\.png$", generated_regex=r"^(?P<group_key>.+)_gen_[0-9]+\.png$")
    parser = FilenameParser(cfg)

    assert parser.parse_mask_group_key(Path("scene123.png")) is None
    assert parser.parse_generated_group_key(Path("scene123_output.png")) is None
