import requests
import sys
import os
import zipfile
import io
import platform
from pathlib import Path
from typing import Optional

XRAY_REPO = "GFW-knocker/Xray-core"
OWN_REPO = "arshiacomplus/python_v2ray"

class BinaryDownloader:
    """
    * Handles the logic of downloading and extracting necessary binaries
    * from GitHub Releases for the current operating system and architecture.
    """
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.vendor_path = self.project_root / "vendor"
        self.core_engine_path = self.project_root / "core_engine"
        self.os_name = self._get_os_name()
        self.arch = self._get_arch_name()

    def _get_os_name(self) -> str:
        """* Determines the OS name used in release assets."""
        if sys.platform == "win32": return "windows"
        if sys.platform == "darwin": return "macos"
        return "linux"

    def _get_arch_name(self) -> str:
        """* Determines the architecture name (e.g., 64, 32, arm64-v8a)."""
        machine = platform.machine().lower()
        if "amd64" in machine or "x86_64" in machine:
            return "64"
        if "arm64" in machine or "aarch64" in machine:
            return "arm64-v8a"
        if "386" in machine or "x86" in machine:
            return "32"
        return "unsupported"

    def _get_asset_url(self, assets: list, name_prefix: str) -> Optional[str]:
        """
        * It finds the download URL for a specific asset based on OS and arch.
        """
        asset_name = f"{name_prefix}-{self.os_name}-{self.arch}.zip"
        print(f"note: Searching for asset: {asset_name}")

        for asset in assets:
            if asset['name'].lower() == asset_name.lower():
                return asset['browser_download_url']
        return None

    def ensure_binary(self, name: str, target_dir: Path, repo: str) -> bool:
        """
        * Checks for a binary, and if not found, downloads and extracts the
        * entire contents of the zip file (including .dat files).
        """
        exe_name = f"{name}.exe" if sys.platform == "win32" else name
        target_file = target_dir / exe_name

        geoip_file = target_dir / "geoip.dat"

        if target_file.is_file() and (name != "xray" or geoip_file.is_file()):
            print(f"* Binary '{exe_name}' and necessary assets already exist.")
            return True

        print(f"! Binary '{exe_name}' not found. Attempting to download from '{repo}'...")

        try:
            release_url = f"https://api.github.com/repos/{repo}/releases/latest"
            response = requests.get(release_url, timeout=10)
            response.raise_for_status()
            assets = response.json().get("assets", [])

            asset_prefix = "Xray" if name == "xray" else name
            download_url = self._get_asset_url(assets, asset_prefix)

            if not download_url:
                print(f"! ERROR: Could not find downloadable asset for '{name}' matching '{self.os_name}-{self.arch}' in repo '{repo}'.")
                return False

            print(f"* Downloading from: {download_url}")
            asset_response = requests.get(download_url, timeout=120, stream=True)
            asset_response.raise_for_status()

            print(f"* Extracting all files to '{target_dir}'...")
            with zipfile.ZipFile(io.BytesIO(asset_response.content)) as z:
                z.extractall(path=target_dir)
            print(f"* Successfully downloaded and extracted all assets for '{name}'.")

            if sys.platform != "win32" and target_file.is_file():
                os.chmod(target_file, 0o755)

            return True

        except Exception as e:
            print(f"! ERROR during download/extraction: {e}")
            return False

    def ensure_all(self):
        """* Ensures all necessary binaries are present."""
        print("--- Checking for necessary binaries & databases ---")
        self.vendor_path.mkdir(exist_ok=True)
        self.core_engine_path.mkdir(exist_ok=True)

        xray_ok = self.ensure_binary("xray", self.vendor_path, XRAY_REPO)
        engine_ok = self.ensure_binary("core_engine", self.core_engine_path, OWN_REPO)

        print("-------------------------------------------------")
        if not (xray_ok and engine_ok):
            raise RuntimeError("Could not obtain all necessary files.")