import subprocess, json, os, sys, time, logging, socket
from pathlib import Path
from typing import List, Dict, Any, Optional
from .speed_tester import SpeedTester
from .hysteria_manager import HysteriaCore
from .core import XrayCore
from .config_parser import ConfigParams, XrayConfigBuilder
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
class ConnectionTester:
    def __init__(self, vendor_path: str, core_engine_path: str):
        self.vendor_path = Path(vendor_path)
        self.core_engine_path = Path(core_engine_path)
        if sys.platform == "win32":
            self.tester_exe, self.xray_exe, self.hysteria_exe = "core_engine.exe", "xray.exe", "hysteria.exe"
        elif sys.platform == "darwin":
            self.tester_exe, self.xray_exe, self.hysteria_exe = "core_engine_macos", "xray_macos", "hysteria_macos"
        else:
            self.tester_exe, self.xray_exe, self.hysteria_exe = "core_engine_linux", "xray_linux", "hysteria_linux"
        if not (self.core_engine_path / self.tester_exe).is_file(): raise FileNotFoundError("Tester executable not found")
    def test_uris(self, parsed_params: List[ConfigParams], fragment_config: Optional[Dict[str, Any]] = None, mux_config: Optional[Dict[str, Any]] = None, timeout: int = 90) -> List[Dict[str, Any]]:
        """
        * Takes a list of PRE-PARSED ConfigParams objects and tests them using the correct client.
        """
        if not parsed_params: return []
        hysteria_params = []
        xray_params = []
        for params in parsed_params:
            if params.protocol in ["hysteria", "hysteria2", "hy2"]:
                hysteria_params.append(params)
            else:
                xray_params.append(params)
        all_results = []
        if hysteria_params:
            logging.info(f"Testing {len(hysteria_params)} Hysteria configuration(s) individually...")
            hysteria_results = self._test_individual_clients(hysteria_params, self.hysteria_exe, "hysteria2", timeout)
            all_results.extend(hysteria_results)
        if xray_params:
            logging.info(f"Testing {len(xray_params)} Xray configuration(s) with one merged instance...")
            base_port = 20800
            builder = XrayConfigBuilder()
            tests_to_run = []
            for i, params in enumerate(xray_params):
                inbound_port = base_port + i
                inbound_tag = f"inbound_{i}"
                # outbound = builder.build_outbound_from_params(params, fragment_config=fragment_config)
                # builder.add_outbound(outbound)
                # builder.add_inbound({"tag": inbound_tag, "port": inbound_port, "listen": "127.0.0.1", "protocol": "socks", "settings": {"auth": "noauth", "udp": True, "userLevel": 0}})
                # builder.config["routing"]["rules"].append({"type": "field", "inboundTag": [inbound_tag], "outboundTag": outbound["tag"]})
                # tests_to_run.append({"tag": outbound["tag"], "test_port": inbound_port, "listen_ip": "127.0.0.1"})
                outbound = builder.build_outbound_from_params(params)
                if mux_config and not params.mux_enabled:
                    if "mux" not in outbound:
                        outbound["mux"] = {}
                    outbound["mux"]["enabled"] = mux_config.get("enabled", True)
                    outbound["mux"]["concurrency"] = mux_config.get("concurrency", 8)
                outbound_tag_for_routing = outbound["tag"]
                if fragment_config and not params.fragment_enabled:
                    outbound_tag_for_routing = "fragment"
                builder.add_outbound(outbound)
                builder.add_inbound({
                    "tag": inbound_tag, "port": inbound_port, "listen": "127.0.0.1",
                    "protocol": "socks", "settings": {"auth": "noauth", "udp": True, "userLevel": 0}
                })
                builder.config["routing"]["rules"].append({
                    "type": "field", "inboundTag": [inbound_tag], "outboundTag": outbound_tag_for_routing
                })
                tests_to_run.append({"tag": params.tag, "test_port": inbound_port, "listen_ip": "127.0.0.1"})
            builder.add_outbound({"protocol": "freedom", "tag": "direct"})
            builder.add_outbound({"protocol": "blackhole", "tag": "block"})
            if fragment_config:
                builder.add_fragment_outbound(fragment_config)
            temp_config_path = self.core_engine_path / "merged_xray_config.json"
            with open(temp_config_path, "w", encoding='utf-8') as f: f.write(builder.to_json())
            xray_process = None
            try:
                xray_process = subprocess.Popen([str(self.vendor_path / self.xray_exe), "-c", str(temp_config_path)])
                logging.info(f"Merged Xray instance started (PID: {xray_process.pid}). Waiting for initialization...")
                last_port_to_check = base_port + len(xray_params) - 1
                is_ready = False
                for _ in range(20):
                    try:
                        with socket.create_connection(("127.0.0.1", last_port_to_check), timeout=0.25):
                            is_ready = True
                            logging.info("Xray instance is ready.")
                            break
                    except (socket.timeout, ConnectionRefusedError):
                        time.sleep(0.25)
                if not is_ready:
                    logging.error("Xray instance failed to start up in time. Stopping test.")
                    raise RuntimeError("Xray startup timeout")
                logging.info(f"Sending {len(tests_to_run)} Xray test jobs to Go engine...")
                xray_results = self._run_go_tester(tests_to_run, timeout)
                all_results.extend(xray_results)
            finally:
                if xray_process: xray_process.terminate(); xray_process.wait()
                # if temp_config_path.exists(): temp_config_path.unlink()
        return all_results
    def test_speed(self, parsed_params: List[ConfigParams], download_bytes: int = 10000000, download_url: str = "https://speed.cloudflare.com/__down", timeout: int = 60) -> List[Dict[str, Any]]:
        if not parsed_params:
            return []
        logging.info(f"Orchestrating proxies for speed test on {len(parsed_params)} configs...")
        base_port = 20800
        jobs_to_run = []
        proxies_to_manage = []
        xray_params_to_merge = []
        for i, params in enumerate(parsed_params):
            local_port = base_port + i
            job = {
                "tag": params.tag, "listen_ip": "127.0.0.1", "test_port": local_port,
                "download_url": download_url, "download_bytes": download_bytes,
            }
            jobs_to_run.append(job)
            if params.protocol in ["hysteria", "hysteria2", "hy2"]:
                proxies_to_manage.append(HysteriaCore(str(self.vendor_path), params, local_port=local_port))
            else:
                xray_params_to_merge.append((params, local_port))
        if xray_params_to_merge:
            builder = XrayConfigBuilder()
            for params, local_port in xray_params_to_merge:
                builder.add_inbound({
                    "tag": f"inbound-{local_port}", "port": local_port, "listen": "127.0.0.1",
                    "protocol": "socks", "settings": {"auth": "noauth", "udp": True}
                })
                outbound = builder.build_outbound_from_params(params)
                builder.add_outbound(outbound)
                builder.config["routing"]["rules"].append({
                    "type": "field", "inboundTag": [f"inbound-{local_port}"], "outboundTag": outbound["tag"]
                })
            proxies_to_manage.append(XrayCore(str(self.vendor_path), builder))
        results = []
        try:
            logging.info(f"Starting {len(proxies_to_manage)} proxy manager(s)...")
            for proxy in proxies_to_manage:
                proxy.start()
            logging.info("Waiting for proxy servers to become ready...")
            time.sleep(2.5)
            logging.info("Delegating speed tests to Go engine...")
            results = self._run_go_tester(jobs_to_run, timeout=timeout)
        finally:
            logging.info("Stopping all proxy managers...")
            for proxy in reversed(proxies_to_manage):
                proxy.stop()
        return results
    def test_upload(self, parsed_params: List[ConfigParams], upload_bytes: int = 5000000, upload_url: str = "https://speed.cloudflare.com/__up", timeout: int = 60) -> List[Dict[str, Any]]:
        if not parsed_params:
            return []
        logging.info(f"Orchestrating proxies for upload test on {len(parsed_params)} configs...")
        base_port = 20800
        jobs_to_run = []
        proxies_to_manage = []
        xray_params_to_merge = []
        for i, params in enumerate(parsed_params):
            local_port = base_port + i
            job = {
                "tag": params.tag, "listen_ip": "127.0.0.1", "test_port": local_port,
                "upload_url": upload_url, "upload_bytes": upload_bytes,
            }
            jobs_to_run.append(job)
            if params.protocol in ["hysteria", "hysteria2", "hy2"]:
                proxies_to_manage.append(HysteriaCore(str(self.vendor_path), params, local_port=local_port))
            else:
                xray_params_to_merge.append((params, local_port))
        if xray_params_to_merge:
            builder = XrayConfigBuilder()
            for params, local_port in xray_params_to_merge:
                builder.add_inbound({
                    "tag": f"inbound-{local_port}", "port": local_port, "listen": "127.0.0.1",
                    "protocol": "socks", "settings": {"auth": "noauth", "udp": True}
                })
                outbound = builder.build_outbound_from_params(params)
                builder.add_outbound(outbound)
                builder.config["routing"]["rules"].append({
                    "type": "field", "inboundTag": [f"inbound-{local_port}"], "outboundTag": outbound["tag"]
                })
            proxies_to_manage.append(XrayCore(str(self.vendor_path), builder))
        results = []
        try:
            logging.info(f"Starting {len(proxies_to_manage)} proxy manager(s)...")
            for proxy in proxies_to_manage:
                proxy.start()
            logging.info("Waiting for proxy servers to become ready...")
            time.sleep(2.5)
            logging.info("Delegating upload tests to Go engine...")
            results = self._run_go_tester(jobs_to_run, timeout=timeout)
        finally:
            logging.info("Stopping all proxy managers...")
            for proxy in reversed(proxies_to_manage):
                proxy.stop()
        return results
    def _run_go_tester(self, payload: List[Dict[str, Any]], timeout: int) -> List[Dict[str, Any]]:
        if not payload:
            return []
        input_json = json.dumps(payload)
        try:
            tester_exe_path = str(self.core_engine_path / self.tester_exe)
            with subprocess.Popen(
                [tester_exe_path],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8'
            ) as process:
                stdout, stderr = process.communicate(input=input_json, timeout=timeout)
                if stderr:
                    logging.error(f"Go engine error log:\n{stderr}")
                if process.returncode != 0:
                    logging.error(f"Go engine exited with non-zero code: {process.returncode}")
                    return []
                return json.loads(stdout) if stdout else []
        except subprocess.TimeoutExpired:
            logging.error(f"Go engine timed out after {timeout} seconds.")
            return []
        except Exception as e:
            logging.error(f"An error occurred while running the Go tester: {e}")
            return []
    def _test_individual_clients(self, params_list: List[ConfigParams], client_exe: str, protocol_name: str, timeout: int) -> List[Dict[str, Any]]:
        test_jobs = []
        base_port = 30800
        ip_counter = 2
        for i, params in enumerate(params_list):
            test_jobs.append({
                "tag": params.tag, "protocol": protocol_name,
                "config_uri": f"{params.protocol}://{params.hy2_password}@{params.address}:{params.port}?sni={params.sni}",
                "listen_ip": f"127.0.0.{ip_counter}", "test_port": base_port + i,
                "client_path": str(self.vendor_path / client_exe)
            })
            ip_counter += 1
        return self._run_go_tester(test_jobs, timeout)