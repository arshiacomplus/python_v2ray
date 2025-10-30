import subprocess, json, os, sys, time, logging, socket
from pathlib import Path
from typing import List, Dict, Any, Optional
# // from .speed_tester import SpeedTester
from .hysteria_manager import HysteriaCore
from .core import XrayCore
from .config_parser import ConfigParams, XrayConfigBuilder
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
import functools
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
def proxy_manager(func):
    """
    A decorator that manages the lifecycle of proxy processes (Xray, Hysteria)
    for a test function. It handles setup, teardown, and passes a list of
    proxy jobs to the wrapped function.
    """
    @functools.wraps(func)
    def wrapper(self: 'ConnectionTester', parsed_params: List[ConfigParams], **kwargs):
        if not parsed_params:
            return []
        logging.info(f"Orchestrating proxies for '{func.__name__}'...")
        base_port = 20800
        jobs_to_run = []
        proxies_to_manage = []
        xray_params_to_merge = []
        warp_config = kwargs.get('warp_config')
        debug_mode = kwargs.get('debug_mode', False)
        for i, params in enumerate(parsed_params):
            local_port = base_port + i
            jobs_to_run.append({"params": params, "local_port": local_port, "tag": params.display_tag,"listen_ip": "127.0.0.1" })
            if params.protocol in ["hysteria", "hysteria2", "hy2"]:
                proxies_to_manage.append(HysteriaCore(str(self.vendor_path), params, local_port=local_port))
            else:
                xray_params_to_merge.append((params, local_port))
        if xray_params_to_merge:
            builder = XrayConfigBuilder()
            if warp_config:
                logging.info(f"Enabling WARP-on-Any mode with config: {warp_config.tag}")
                builder.add_warp_outbound(warp_config)
            for i, (params, local_port) in enumerate(xray_params_to_merge):
                internal_xray_outbound_tag = f"proxy_out_xray_{i}"
                builder.add_inbound({"tag": f"inbound-{local_port}", "port": local_port, "listen": "127.0.0.1", "protocol": "socks", "settings": {"auth": "noauth", "udp": True}})
                outbound = builder.build_outbound_from_params(params, explicit_tag=internal_xray_outbound_tag)
                if outbound:
                    builder.add_outbound(outbound)
                    builder.config["routing"]["rules"].append({"type": "field", "inboundTag": [f"inbound-{local_port}"], "outboundTag": outbound["tag"]})
                else:
                    logging.warning(f"Skipping Xray outbound for protocol '{params.protocol}' and tag '{params.tag}' (not supported or failed to build).")
            builder.add_outbound({"protocol": "freedom", "tag": "direct"})
            builder.add_outbound({"protocol": "blackhole", "tag": "block"})
            proxies_to_manage.append(XrayCore(str(self.vendor_path), builder, debug_mode=debug_mode))
        try:
            logging.info(f"Starting {len(proxies_to_manage)} proxy manager(s)...")
            for proxy in proxies_to_manage:
                proxy.start()
            logging.info("Waiting for proxy servers to become ready...")
            expected_ports = {job["local_port"] for job in jobs_to_run}
            ready_ports = set()
            max_wait_attempts = 40
            for attempt in range(max_wait_attempts):
                all_expected_ports_ready = True
                ports_to_check_in_this_attempt = expected_ports - ready_ports
                if not ports_to_check_in_this_attempt:
                    break
                for port in ports_to_check_in_this_attempt:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                            ready_ports.add(port)
                    except (socket.timeout, ConnectionRefusedError):
                        all_expected_ports_ready = False
                        break
                if all_expected_ports_ready and len(ready_ports) == len(expected_ports):
                    logging.info(f"All {len(expected_ports)} proxy SOCKS ports are ready after {attempt+1} attempts.")
                    break
                time.sleep(0.25)
            else:
                logging.warning(f"Timeout: Not all proxy SOCKS ports became ready. {len(ready_ports)}/{len(expected_ports)} ports ready.")
            return func(self, jobs_to_run, **kwargs)
        finally:
            logging.info("Stopping all proxy managers...")
            for proxy in reversed(proxies_to_manage):
                proxy.stop()
    return wrapper
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
    @proxy_manager
    def test_uris(
        self, jobs_to_run: List[Dict],
        timeout: int = 10,
        ping_url: str = "http://www.google.com/generate_204",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        * Takes a list of PRE-PARSED ConfigParams objects and tests them using the correct client.
        * This version is robust against failing individual configs and duplicate tags.
        * It now leverages the proxy_manager decorator to handle Xray/Hysteria lifecycle.
        """
        if not jobs_to_run:
            return []
        go_tester_payload = []
        for job in jobs_to_run:
            params = job["params"]
            if params.protocol in ["hysteria", "hysteria2", "hy2"]:
                go_tester_payload.append({
                    "tag": job["tag"],
                    "protocol": "hysteria2",
                    "config_uri": f"{params.protocol}://{params.hy2_password}@{params.address}:{params.port}?sni={params.sni}",
                    "listen_ip": job["listen_ip"],
                    "test_port": job["local_port"],
                    "client_path": str(self.vendor_path / self.hysteria_exe),
                    "ping_url": ping_url
                })
            else:
                go_tester_payload.append({
                    "tag": job["tag"],
                    "listen_ip": job["listen_ip"],
                    "test_port": job["local_port"],
                    "ping_url": ping_url
                })
        logging.info(f"Sending {len(go_tester_payload)} test jobs to Go engine...")
        all_results = self._run_go_tester(go_tester_payload, timeout)
        return all_results
    @proxy_manager
    def test_speed(self, jobs: List[Dict], **kwargs) -> List[Dict[str, Any]]:
        download_bytes = kwargs.get('download_bytes', 10000000)
        download_url = kwargs.get('download_url', "https://speed.cloudflare.com/__down")
        timeout = kwargs.get('timeout', 60)
        go_jobs = [
            {
                "tag": job["params"].tag,
                "listen_ip": "127.0.0.1",
                "test_port": job["local_port"],
                "download_url": download_url,
                "download_bytes": download_bytes,
            }
            for job in jobs
        ]
        logging.info("Delegating download speed tests to Go engine...")
        return self._run_go_tester(go_jobs, timeout=timeout)
    @proxy_manager
    def test_upload(self, jobs: List[Dict], **kwargs) -> List[Dict[str, Any]]:
        upload_bytes = kwargs.get('upload_bytes', 5000000)
        upload_url = kwargs.get('upload_url', "https://speed.cloudflare.com/__up")
        timeout = kwargs.get('timeout', 60)
        go_jobs = [
            {
                "tag": job["params"].tag,
                "listen_ip": "127.0.0.1",
                "test_port": job["local_port"],
                "upload_url": upload_url,
                "upload_bytes": upload_bytes,
            }
            for job in jobs
        ]
        logging.info("Delegating upload speed tests to Go engine...")
        return self._run_go_tester(go_jobs, timeout=timeout)
    def _run_go_tester(self, payload: List[Dict[str, Any]], timeout: int = 30) -> List[Dict[str, Any]]:
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
        except FuturesTimeoutError:
            logging.error(f"Go engine timed out after {timeout} seconds. Terminating process.")
            process.kill()
            _, stderr = process.communicate()
            if stderr:
                logging.error(f"Go engine error log (on timeout):\n{stderr}")
            return []
        except Exception as e:
            logging.error(f"An error occurred while running the Go tester: {e}")
            if process.poll() is None:
                process.kill()
            return []
    def _test_individual_clients(
        self, params_list: List[ConfigParams],
        client_exe: str, protocol_name: str,
        timeout: int,
        ping_url: str
        ) -> List[Dict[str, Any]]:
        test_jobs = []
        base_port = 30800
        ip_counter = 2
        for i, params in enumerate(params_list):
            test_jobs.append({
                "tag": params.tag, "protocol": protocol_name,
                "config_uri": f"{params.protocol}://{params.hy2_password}@{params.address}:{params.port}?sni={params.sni}",
                "listen_ip": f"127.0.0.{ip_counter}", "test_port": base_port + i,
                "client_path": str(self.vendor_path / client_exe),
                "ping_url": ping_url
            })
            ip_counter += 1
        return self._run_go_tester(test_jobs, timeout)