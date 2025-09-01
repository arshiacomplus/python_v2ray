
import subprocess
import json
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

class ConnectionTester:
    """
    * This class acts as a bridge between Python and the high-performance Go tester engine.
    """

    def __init__(self, vendor_path: str, core_engine_path: str):
        """
        Args:
            vendor_path (str): Path to the 'vendor' directory (for xray executable).
            core_engine_path (str): Path to the 'core_engine' directory (for go engine).
        """
        if sys.platform == "win32":
            tester_exe_name = "core_engine.exe"
            xray_exe_name = "xray.exe"
        elif sys.platform == "darwin":
            tester_exe_name = "core_engine_macos"
            xray_exe_name = "xray_macos"
        else: # Linux and others
            tester_exe_name = "core_engine_linux"
            xray_exe_name = "xray_linux"

        # * Use pathlib for safe and cross-platform path construction
        self.tester_path = str(Path(core_engine_path) / tester_exe_name)
        self.xray_path = str(Path(vendor_path) / xray_exe_name)

        if not os.path.exists(self.tester_path):
            raise FileNotFoundError(f"Tester executable not found at: {self.tester_path}")
        if not os.path.exists(self.xray_path):
            raise FileNotFoundError(f"Xray executable not found at: {self.xray_path}")
    def test_outbounds(self, outbounds: List[Dict[str, Any]], fragment_config: Optional[Dict[str, Any]] = None, timeout: int = 60) -> List[Dict[str, Any]]:
        """
        * Tests a list of outbound configs concurrently using the Go engine, with optional fragmentation.

        Args:
            outbounds (List[Dict[str, Any]]): A list of Xray outbound config dictionaries.
            fragment_config (Optional[Dict[str, Any]]): Settings for TLS fragmentation.
            timeout (int): Total time in seconds to wait for all tests to complete.

        Returns:
            A list of result dictionaries.
        """
        if not outbounds:
            return []
        fragment_json_bytes = json.dumps(fragment_config).encode('utf-8') if fragment_config else b'null'

        test_configs = []
        base_port = 20800
        for i, outbound in enumerate(outbounds):
            if fragment_config and outbound.get("protocol") not in ["freedom", "blackhole"]:
                if "streamSettings" not in outbound:
                    outbound["streamSettings"] = {}
                outbound["streamSettings"]["sockopt"] = {"dialerProxy": "fragment"}

            test_configs.append({
                "tag": outbound.get("tag", f"outbound_{i}"),
                "config": outbound,
                "test_port": base_port + i,
                "xray_path": self.xray_path,
                "fragment_config": json.loads(fragment_json_bytes),
            })

        input_json = json.dumps(test_configs)

        try:
            with subprocess.Popen(
                [self.tester_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            ) as process:
                stdout, stderr = process.communicate(input=input_json, timeout=timeout)

                if process.returncode != 0:
                    print(f"! Go engine exited with an error (return code {process.returncode}):")
                    print(f"--- STDERR ---:\n{stderr}\n--------------")
                    return []

                if not stdout:
                    print("! Go engine returned no output.")
                    return []

                results = json.loads(stdout)
                return results

        except subprocess.TimeoutExpired:
            process.kill()
            print(f"! Testing process timed out after {timeout} seconds.")
            return []
        except json.JSONDecodeError:
            print("! Failed to decode JSON from Go engine. Raw output:")
            print(f"--- STDOUT ---:\n{stdout}\n--------------")
            return []
        except Exception as e:
            print(f"! An unexpected error occurred while running the tester: {e}")
            return []