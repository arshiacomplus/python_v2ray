import os
import sys
import tempfile
from typing import Optional, List, Dict
from pathlib import Path
import logging

from .config_parser import XrayConfigBuilder
from .process_manager import BaseProcessManager

# NOTE: api_client import is no longer needed here if get_stats is removed or refactored
# // from .api_client import XrayApiClient


class XrayCore(BaseProcessManager):
    """
    Manages the Xray-core process by inheriting from BaseProcessManager.
    It implements the Xray-specific logic for configuration and startup.
    """

    def __init__(
        self,
        vendor_path: str,
        config_builder: XrayConfigBuilder,
        debug_mode: bool = False,
    ):
        super().__init__(vendor_path)
        self.config_builder = config_builder
        self.debug_mode = debug_mode
        # self.api_port = api_port #! This logic can be refactored if needed
        # // self._api_client = None

    def _get_executable_name(self) -> str:
        if sys.platform == "win32":
            return "xray.exe"
        if sys.platform == "darwin":
            return "xray_macos"
        return "xray_linux"

    def _get_start_command(self) -> List[str]:
        return [str(self.executable_path), "-c", self._config_file_path]

    def _create_config(self) -> None:
        """Creates a temporary file for the Xray JSON configuration."""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        ) as f:
            f.write(self.config_builder.to_json())
            self._config_file_path = f.name
        logging.info(f"Temporary Xray config created at: {self._config_file_path}")

    def _cleanup_config(self) -> None:
        """Overrides cleanup to respect debug_mode."""
        if self.debug_mode:
            logging.info(
                f"[DEBUG MODE] Xray temporary config file kept at: {self._config_file_path}"
            )
            return
        super()._cleanup_config()
