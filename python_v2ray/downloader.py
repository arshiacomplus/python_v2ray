# python_v2ray/downloader.py

import requests, sys, os, zipfile, io, platform
from pathlib import Path
from typing import Optional

XRAY_REPO = "GFW-knocker/Xray-core"
OWN_REPO = "arshiacomplus/python_v2ray"
HYSTERIA_REPO = "apernet/hysteria"

class BinaryDownloader:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.vendor_path = self.project_root / "vendor"
        self.core_engine_path = self.project_root / "core_engine"
        self.os_name = self._get_os_name()
        self.arch = self._get_arch_name()

    def _get_os_name(self) -> str:
        if sys.platform == "win32": return "windows"
        if sys.platform == "darwin": return "darwin"
        return "linux"

    def _get_arch_name(self) -> str:
        machine = platform.machine().lower()
        if "amd64" in machine or "x86_64" in machine: return "amd64"
        if "arm64" in machine or "aarch64" in machine: return "arm64"
        if "386" in machine or "x86" in machine: return "386"
        return "unsupported"

    def _get_asset_url(self, assets: list, name_prefix: str) -> Optional[str]:
        # * This logic is now smarter to handle different naming conventions

        if name_prefix == "hysteria":
            asset_name = f"{name_prefix}-{self.os_name}-{self.arch}"
            if self.os_name == "windows":
                asset_name += ".exe"
        elif name_prefix == "Xray":
            arch_name = "64" if self.arch == "amd64" else self.arch
            os_name = "macos" if self.os_name == "darwin" else self.os_name # Xray uses macos
            asset_name = f"{name_prefix}-{os_name}-{arch_name}.zip"
        else:
            arch_name = "64" if self.arch == "amd64" else self.arch
            os_name = "macos" if self.os_name == "darwin" else self.os_name
            asset_name = f"{name_prefix}-{os_name}-{arch_name}.zip"

        print(f"note: Searching for asset: {asset_name}")
        for asset in assets:
            if asset['name'].lower() == asset_name.lower():
                return asset['browser_download_url']
        return None

    def ensure_binary(self, name: str, target_dir: Path, repo: str) -> bool:
        exe_name = f"{name}.exe" if sys.platform == "win32" else name
        target_file = target_dir / exe_name

        if target_file.is_file():
            print(f"* Binary '{exe_name}' already exists.")
            return True

        print(f"! Binary '{exe_name}' not found. Downloading from '{repo}'...")
        try:
            if name == "hysteria":
                release_url = f"https://api.github.com/repos/{repo}/releases/tags/app%2Fv2.6.2" # ! Hardcoded to a specific stable version
            else:
                release_url = f"https://api.github.com/repos/{repo}/releases/latest"

            response = requests.get(release_url, timeout=10)
            response.raise_for_status()
            assets = response.json().get("assets", [])

            asset_prefix = "Xray" if name == "xray" else name
            download_url = self._get_asset_url(assets, asset_prefix)

            if not download_url:
                print(f"! ERROR: Could not find downloadable asset for '{name}'.")
                return False

            print(f"* Downloading: {download_url}")
            asset_response = requests.get(download_url, timeout=120, stream=True)
            asset_response.raise_for_status()

            if not download_url.endswith('.zip'):
                with open(target_file, "wb") as f:
                    f.write(asset_response.content)
            else:
                with zipfile.ZipFile(io.BytesIO(asset_response.content)) as z:
                    for member_name in z.namelist():
                        if Path(member_name).name.lower() == exe_name.lower():
                            source = z.open(member_name)
                            target = open(target_file, "wb")
                            with source, target: target.write(source.read())

                            for dat_file in ["geoip.dat", "geosite.dat"]:
                                if dat_file in z.namelist():
                                    with z.open(dat_file) as source_dat, open(target_dir / dat_file, "wb") as target_dat:
                                        target_dat.write(source_dat.read())

            print(f"* Successfully downloaded '{exe_name}'.")
            if sys.platform != "win32":
                os.chmod(target_file, 0o755)
            return True

        except Exception as e:
            print(f"! ERROR during download/extraction for '{name}': {e}")
            return False

    def ensure_all(self):
        print("--- Checking for necessary binaries & databases ---")
        self.vendor_path.mkdir(exist_ok=True)
        self.core_engine_path.mkdir(exist_ok=True)
        xray_ok = self.ensure_binary("xray", self.vendor_path, XRAY_REPO)
        engine_ok = self.ensure_binary("core_engine", self.core_engine_path, OWN_REPO)
        hysteria_ok = self.ensure_binary("hysteria", self.vendor_path, HYSTERIA_REPO)

        print("-------------------------------------------------")
        if not (xray_ok and engine_ok and hysteria_ok):
            raise RuntimeError("Could not obtain all necessary binaries.")