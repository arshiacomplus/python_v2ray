



# examples/03_stats_viewer.py

import time
from pathlib import Path

from python_v2ray.downloader import BinaryDownloader
from python_v2ray.core import XrayCore
from python_v2ray.config_parser import parse_uri, XrayConfigBuilder

def main():
    """
    * Demonstrates how to run Xray with the API enabled and fetch live stats.
    * This version uses the ORIGINAL printing logic.
    """

    project_root = Path(__file__).parent.parent
    vendor_dir = project_root / "vendor"
    try:
        downloader = BinaryDownloader(project_root)
        downloader.ensure_all()
    except Exception as e:
        print(f"\n! FATAL: {e}")
        return
    test_uri = "vless://"

    params = parse_uri(test_uri)
    if not params:
        return

    outbound_tag_to_monitor = "proxy"
    params.tag = outbound_tag_to_monitor
    api_port = 62789

    builder = XrayConfigBuilder()
    builder.enable_api(port=api_port)

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


    builder.config["routing"]["rules"].append({
        "type": "field",
        "inboundTag": ["socks_in"],
        "outboundTag": outbound_tag_to_monitor
    })

    try:
        with XrayCore(vendor_dir=str(vendor_dir), config_builder=builder, api_port=api_port) as xray:
            if not xray.is_running():
                print("! Xray failed to start.")
                return

            print(f"\n* Xray is running. SOCKS on 10808. API on {api_port}.")
            print("* Generate some traffic through the SOCKS proxy.")
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

    except Exception as e:
        print(f"\n! An error occurred: {e}")

    print("\n* Demo finished.")

if __name__ == "__main__":
    main()