# examples/01_simple_start_stop.py

import time
from pathlib import Path

from python_v2ray.downloader import BinaryDownloader
from python_v2ray.config_parser import XrayConfigBuilder, parse_uri
from python_v2ray.core import XrayCore

def main():

    print("--- Python-V2Ray Simple Start/Stop Example ---")


    project_root = Path(__file__).parent.parent
    vendor_dir = project_root / "vendor"

    print(f"Project root detected at: {project_root}")
    print(f"Vendor directory set to: {vendor_dir}")


    try:
        downloader = BinaryDownloader(project_root)
        downloader.ensure_all()
    except Exception as e:
        print(f"\n! FATAL: {e}")
        return


    sample_vless_uri = "trojan://2ee85121-31de-4581-a492-eb00f606e392@198.46.152.83:443?mux=&security=tls&headerType=none&type=tcp&muxConcurrency=-1&sni=sj3.freeguard.org#trojan:4349S"

    params = parse_uri(sample_vless_uri)
    if not params:
        print("! Failed to parse the sample URI. Exiting.")
        return

    builder = XrayConfigBuilder()

    local_socks_port = 10808
    builder.add_inbound({
        "port": local_socks_port,
        "listen": "127.0.0.1",
        "protocol": "socks",
        "settings": {
            "auth": "noauth",
            "udp": True,
            "ip": "127.0.0.1"
        },
        "tag": "socks_in"
    })

    outbound_config = builder.build_outbound_from_params(params)
    builder.add_outbound(outbound_config)

    builder.config["routing"]["rules"].append({
        "type": "field",
        "inboundTag": ["socks_in"],
        "outboundTag": outbound_config["tag"]
    })

    print(f"* Configuration created. SOCKS proxy will be available at 127.0.0.1:{local_socks_port}")

    try:

        with XrayCore(vendor_dir=str(vendor_dir), config_builder=builder, debug_mode=True) as xray_process:
            if xray_process.is_running():
                print(f"* Xray core is running with PID: {xray_process.process.pid}")
                print("* The process will run for 15 seconds before shutting down.")
                print("* You can now configure an application (e.g., a web browser) to use the SOCKS proxy.")
                time.sleep(15)
            else:
                print("! Failed to start the Xray core process.")

    except FileNotFoundError:
        print("! Error: Could not find the Xray executable. Please check the vendor path.")
    except Exception as e:
        print(f"! An unexpected error occurred: {e}")

    print("--- Example finished ---")

if __name__ == "__main__":
    main()