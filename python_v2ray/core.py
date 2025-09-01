# python_v2ray/core.py

import subprocess
import os
import tempfile
from typing import Optional
from .config_parser import XrayConfigBuilder
from .api_client import XrayApiClient
from typing import List, Dict, Any, Optional, Tuple
import sys
from pathlib import Path
class XrayCore:
    """
    * Manages the Xray-core process using a dynamic config builder.
    * It's designed to be used as a context manager (with statement).
    """

    def __init__(self, vendor_dir: str, config_builder: XrayConfigBuilder, api_port: Optional[int] = None, debug_mode: bool = False):
        """
        * Manages the Xray-core process using a dynamic config builder.
        * It's designed to be used as a context manager (with statement).
        """
        self.debug_mode = debug_mode
        if sys.platform == "win32":
            exe_name = "xray.exe"
        elif sys.platform == "darwin": # macOS
            exe_name = "xray_macos" # Assuming you rename it for clarity
        else: # Linux and others
            exe_name = "xray_linux" # Assuming you rename it for clarity

        # Use pathlib to build the path safely
        self.executable_path = Path(vendor_dir) / exe_name
        self.config_builder = config_builder
        self.process: Optional[subprocess.Popen] = None
        self._temp_config_file: Optional[str] = None


        self.api_port = api_port
        self._api_client: Optional[XrayApiClient] = None

        if not os.path.exists(self.executable_path):
            raise FileNotFoundError(f"Xray executable not found at: {self.executable_path}")

        if not os.path.exists(self.executable_path):
            raise FileNotFoundError(f"Xray executable not found at: {self.executable_path}")

    def _create_temp_config(self):
        """
        * Creates a temporary file to store the JSON configuration.
        * This file is automatically deleted when the core stops.
        """
        # note: Using tempfile is the standard and safest way to handle temporary files.
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json", encoding="utf-8") as f:
            f.write(self.config_builder.to_json())
            self._temp_config_file = f.name
        print(f"note: Temporary config created at: {self._temp_config_file}")

    def _remove_temp_config(self):
        """* Cleans up the temporary config file."""
        # ! In debug mode, we KEEP the file for inspection.
        if self.debug_mode:
            print(f"note: [DEBUG MODE] Temporary config file kept at: {self._temp_config_file}")
            return

        if self._temp_config_file and os.path.exists(self._temp_config_file):
            os.remove(self._temp_config_file)
            print(f"note: Temporary config file deleted: {self._temp_config_file}")
            self._temp_config_file = None

    def start(self):
        if self.is_running():
            print("note: Xray core is already running.")
            return

        self._create_temp_config()
        print("* Starting Xray core with dynamic config...")
        try:
            self.process = subprocess.Popen(
                [self.executable_path, "-c", self._temp_config_file],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            print(f"* Xray core started successfully with PID: {self.process.pid}")
        except Exception as e:
            print(f"! Failed to start Xray core: {e}")
            self.process = None
            self._remove_temp_config() # ! Clean up if start fails

    def stop(self):
        if not self.is_running():
            print("note: Xray core is not running.")
            return

        print(f"* Stopping Xray core with PID: {self.process.pid}...")
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
            print("* Xray core stopped.")
        except subprocess.TimeoutExpired:
            self.process.kill()
            print("! Xray core killed.")
        finally:
            self.process = None
            self._remove_temp_config() # * Always clean up the temp file on stop.

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None
    def get_stats(self, tag: str, reset: bool = False) -> Optional[Dict[str, int]]:
            """* A high-level method to get stats for a given outbound tag."""
            if not self.api_port:
                print("! API port not configured. Cannot get stats.")
                return None

            if not self.is_running():
                print("! Xray is not running. Cannot get stats.")
                return None

            if self._api_client is None:
                # Lazy initialization of the API client
                api_address = f"127.0.0.1:{self.api_port}"
                self._api_client = XrayApiClient(api_address)

            return self._api_client.get_stats(tag, reset)
    def __enter__(self):
        """* Special method for 'with' statement - starts the core."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """* Special method for 'with' statement - ensures the core is stopped."""
        self.stop()