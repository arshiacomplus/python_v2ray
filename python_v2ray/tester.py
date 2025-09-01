import subprocess, json, os, sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from .config_parser import XrayConfigBuilder, ConfigParams

class ConnectionTester:
    def __init__(self, vendor_path: str, core_engine_path: str):
        self.vendor_path = Path(vendor_path)
        self.core_engine_path = Path(core_engine_path)

        if sys.platform == "win32":
            self.tester_exe = "core_engine.exe"; self.xray_exe = "xray.exe"; self.hysteria_exe = "hysteria.exe"
        elif sys.platform == "darwin":
            self.tester_exe = "core_engine_macos"; self.xray_exe = "xray_macos"; self.hysteria_exe = "hysteria_macos"
        else:
            self.tester_exe = "core_engine_linux"; self.xray_exe = "xray_linux"; self.hysteria_exe = "hysteria_linux"

        if not (self.core_engine_path / self.tester_exe).is_file(): raise FileNotFoundError(f"Tester executable not found")

    def test_outbounds(self, parsed_params: List[ConfigParams], fragment_config: Optional[Dict[str, Any]] = None, timeout: int = 60) -> List[Dict[str, Any]]:
        if not parsed_params: return []

        test_configs = []
        base_port = 20800
        builder = XrayConfigBuilder()

        for i, params in enumerate(parsed_params):
            config_dict = {}
            client_path = ""
            protocol = params.protocol

            if protocol in ["hysteria", "hysteria2"]:
                protocol = "hysteria2"
                client_path = str(self.vendor_path / self.hysteria_exe)
                config_dict = {
                    "server": f"{params.address}:{params.port}",
                    "auth": params.hy2_password,
                    "socks5": {"listen": f"127.0.0.1:{base_port + i}"},
                    "tls": {"sni": params.sni, "insecure": True}
                }
            else:
                client_path = str(self.vendor_path / self.xray_exe)
                outbound = builder.build_outbound_from_params(params, fragment_config=fragment_config)
                if fragment_config:
                    if "streamSettings" not in outbound: outbound["streamSettings"] = {}
                    outbound["streamSettings"]["sockopt"] = {"dialerProxy": "fragment"}
                config_dict = outbound

            test_configs.append({
                "tag": params.tag,
                "protocol": protocol,
                "config": config_dict,
                "test_port": base_port + i,
                "client_path": client_path,
                "fragment_config": fragment_config,
            })

        input_json = json.dumps(test_configs, default=lambda o: o.__dict__)

        try:
            with subprocess.Popen([str(self.core_engine_path / self.tester_exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8') as process:
                stdout, stderr = process.communicate(input=input_json, timeout=timeout)
                if process.returncode != 0: print(f"! Go engine error:\n{stderr}"); return []
                return json.loads(stdout) if stdout else []
        except Exception as e:
            print(f"! Tester execution error: {e}"); return []