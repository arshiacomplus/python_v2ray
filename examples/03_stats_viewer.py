# examples/03_stats_viewer.py

import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_v2ray.core import XrayCore
from python_v2ray.config_parser import parse_uri, XrayConfigBuilder

def main():
    """
    * Demonstrates how to run Xray with the API enabled and fetch live stats.
    """
    # ! Replace with your own REAL and WORKING VLESS URI
    vless_uri = "vless://"

    if "YOUR_UUID" in vless_uri:
        print("! Please replace the placeholder URI in the script with your own to run this demo.")
        return

    params = parse_uri(vless_uri)
    if not params:
        return

    # * The tag of our main outbound that we want to monitor
    params.tag = "proxy"
    outbound_tag_to_monitor = "proxy"

    # * The port for the gRPC API
    api_port = 62789

    print(f"* Building config to monitor outbound with tag: '{outbound_tag_to_monitor}'")
    builder = XrayConfigBuilder()
    builder.enable_api(port=api_port) # ! Enable the API service
    builder.add_inbound({
        "port": 10808,
        "listen": "127.0.0.1",
        "protocol": "socks",
        "settings": {
            "auth": "noauth",
            "udp": True,
            "userLevel": 0
        }
    })

    outbound = builder.build_outbound_from_params(params)
    builder.add_outbound(outbound)
    builder.add_outbound({"protocol": "freedom", "tag": "direct"})
    print("\n" + "="*20 + " FINAL CONFIG TO BE USED " + "="*20)
    final_config_json = builder.to_json()
    print(final_config_json)
    print("="*61 + "\n")


    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    xray_path = os.path.join(project_root, "vendor", "xray.exe")

    print("* Starting Xray with API enabled...")
    # ! Pass the api_port to the XrayCore constructor
    with XrayCore(executable_path=xray_path, config_builder=builder, api_port=api_port) as xray:
        if not xray.is_running():
            print("! Xray failed to start.")
            return

        print("\n* Xray is running. SOCKS on 10808. API on 62789.")
        print("* Now, generate some traffic through the SOCKS proxy (e.g., watch a video, run a speed test).")
        print("* Press Ctrl+C to stop.\n")

        try:
            while True:
                time.sleep(2)
                stats = xray.get_stats(tag=outbound_tag_to_monitor)
                if stats:
                    uplink_mb = stats['uplink'] / (1024 * 1024)
                    downlink_mb = stats['downlink'] / (1024 * 1024)
                    print(f"* Live Stats for '{outbound_tag_to_monitor}': Uplink: {uplink_mb:.2f} MB | Downlink: {downlink_mb:.2f} MB")
                else:
                    print(f"\r* Waiting for traffic on tag '{outbound_tag_to_monitor}'...", end="")
        except KeyboardInterrupt:
            print("\n* User stopped the stats viewer.")

    print("* Demo finished.")

if __name__ == "__main__":
    main()