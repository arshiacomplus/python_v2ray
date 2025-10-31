import json
import os
import sys
from typing import List
import logging

from .config_parser import ConfigParams
from .process_manager import BaseProcessManager


class HysteriaCore(BaseProcessManager):
    """
    Manages a standalone Hysteria client process by inheriting from BaseProcessManager.
    """

    def __init__(self, vendor_path: str, params: ConfigParams, local_port: int = 10809):
        super().__init__(vendor_path)
        self.params = params
        self.local_port = local_port

    def _get_executable_name(self) -> str:
        if sys.platform == "win32":
            return "hysteria.exe"
        if sys.platform == "darwin":
            return "hysteria_macos"
        return "hysteria_linux"

    def _get_start_command(self) -> List[str]:
        return [str(self.executable_path), "client", "-c", self._config_file_path]

    def _create_config(self) -> None:
        """Creates the JSON config file needed by the Hysteria client."""
        config = {
            "server": f"{self.params.address}:{self.params.port}",
            "auth": self.params.hy2_password,
            "socks5": {"listen": f"127.0.0.1:{self.local_port}"},
            "tls": {
                "sni": self.params.sni,
                "insecure": True,  # Typically needed for client-side testing
            },
        }
        if self.params.hy2_obfs:
            config["obfs"] = {
                "type": self.params.hy2_obfs,
                "password": self.params.hy2_obfs_password,
            }

        config_path = self.vendor_path / "hysteria_config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        self._config_file_path = str(config_path)
        logging.info(f"Hysteria config created at: {self._config_file_path}")
