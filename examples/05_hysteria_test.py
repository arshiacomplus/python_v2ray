# examples/05_hysteria_test.py

import os
import sys
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_v2ray.config_parser import parse_uri, XrayConfigBuilder
from python_v2ray.core import XrayCore
from python_v2ray.hysteria_manager import HysteriaCore

def main():
    # ! Replace with your own REAL Hysteria2 URI
    hysteria_uri = "hysteria2://YOUR_PASSWORD@your.domain.com:443?sni=your.domain.com#Hysteria-Test"
    local_hysteria_port = 10809

    if "YOUR_PASSWORD" in hysteria_uri:
        print("! Please provide a real Hysteria2 URI to test.")
        return

    hy_params = parse_uri(hysteria_uri)
    if not hy_params: return

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    vendor_dir = os.path.join(project_root, "vendor")


    with HysteriaCore(vendor_path=vendor_dir, params=hy_params, local_port=local_hysteria_port) as hysteria:
        time.sleep(2)

        builder = XrayConfigBuilder()
        builder.add_inbound({"port": 10808, "protocol": "socks"}) # Main app inbound

        builder.add_outbound({
            "protocol": "socks",
            "tag": "proxy",
            "settings": {"servers": [{"address": "127.0.0.1", "port": local_hysteria_port}]}
        })

        with XrayCore(vendor_path=vendor_dir, config_builder=builder) as xray:
            print("\n* Xray is running and routing traffic through the Hysteria client.")
            print("* Your main SOCKS proxy is on 127.0.0.1:10808")
            print("* Press Ctrl+C to stop both processes.")
            try:
                while True: time.sleep(1)
            except KeyboardInterrupt:
                print("\n* Stopping...")

if __name__ == "__main__":
    main()