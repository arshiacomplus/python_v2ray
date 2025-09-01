# python_v2ray/hysteria_manager.py

import subprocess
import os
import sys
import json
from typing import Optional
from .config_parser import ConfigParams
from pathlib import Path

class HysteriaCore:
    """
    * Manages a standalone Hysteria client process.
    * It creates a YAML config, runs the client, and provides a local SOCKS proxy.
    """
    def __init__(self, vendor_path: str, params: ConfigParams, local_port: int = 10809):
        if sys.platform == "win32":
            exe_name = "hysteria.exe"
        elif sys.platform == "darwin":
            exe_name = "hysteria_macos"
        else:
            exe_name = "hysteria_linux"
        self.executable_path = os.path.join(vendor_path, exe_name)
        self.params = params
        self.local_port = local_port
        self.process: Optional[subprocess.Popen] = None
        self._config_path: Optional[str] = None

        if not os.path.exists(self.executable_path):
            raise FileNotFoundError(f"Hysteria executable not found at: {self.executable_path}")

    def _create_config(self):
        """* Creates the YAML config file needed by the Hysteria client."""
        config = {
            "server": f"{self.params.address}:{self.params.port}",
            "auth": self.params.hy2_password,
            "socks5": {
                "listen": f"127.0.0.1:{self.local_port}"
            },
            "tls": {
                "sni": self.params.sni,
                "insecure": True
            }
        }
        if self.params.hy2_obfs:
            config["obfs"] = {
                "type": self.params.hy2_obfs,
                "password": self.params.hy2_obfs_password
            }

        # note: We use JSON for simplicity as most Hysteria clients accept it too.
        config_path = os.path.join(os.path.dirname(self.executable_path), "hysteria_config.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        self._config_path = config_path

    def start(self):
        if self.process: return
        self._create_config()
        print(f"* Starting Hysteria client, connecting to {self.params.address}...")
        self.process = subprocess.Popen([self.executable_path, "client", "-c", self._config_path])
        print(f"* Hysteria client started. Local SOCKS proxy on 127.0.0.1:{self.local_port}")

    def stop(self):
        if self.process:
            print("* Stopping Hysteria client...")
            self.process.terminate()
            self.process.wait()
            self.process = None
        if self._config_path and os.path.exists(self._config_path):
            os.remove(self._config_path)

    def __enter__(self): self.start(); return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.stop()