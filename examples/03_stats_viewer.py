# examples/03_stats_viewer.py

import time
import os
import sys
from pathlib import Path # NEW: Import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_v2ray.core import XrayCore
from python_v2ray.config_parser import parse_uri, XrayConfigBuilder
from python_v2ray.api_client import XrayApiClient # <--- NEW: Import XrayApiClient

def main():
    """
    * Demonstrates how to run Xray with the API enabled and fetch live stats.
    * This uses the XrayApiClient to communicate with Xray's gRPC StatsService.
    """
    # ! Replace with your own REAL and WORKING VLESS URI
    # This URI will be the outbound we monitor for traffic stats.
    vless_uri = "vless://YOUR_UUID@your.domain.com:443?security=tls&sni=your.domain.com&fp=chrome&type=ws&path=%2F#MyVLESSProxy"

    if "YOUR_UUID" in vless_uri:
        print("! Please replace the placeholder URI in the script with your own to run this demo.")
        return

    params = parse_uri(vless_uri)
    if not params:
        print("! Failed to parse the VLESS URI.")
        return

    # * We will use the parsed display_tag for reporting and the internal tag for Xray config
    outbound_display_tag = params.display_tag
    outbound_internal_tag = params.tag # This is the cleaned-up tag for Xray's internal use

    # * The port for the local SOCKS inbound that user connects to
    local_socks_port = 10808
    # * The port for the gRPC API (it will be exposed on 127.0.0.1)
    api_port = 62789
    api_address = f"127.0.0.1:{api_port}"

    print(f"* Building Xray configuration to monitor outbound with tag: '{outbound_internal_tag}' (Display: '{outbound_display_tag}')")
    builder = XrayConfigBuilder()
    builder.enable_api(port=api_port) # ! Enable the API service on the specified port

    # Add a local SOCKS inbound for user applications to connect to
    builder.add_inbound({
        "tag": f"inbound-socks-{local_socks_port}",
        "port": local_socks_port,
        "listen": "127.0.0.1",
        "protocol": "socks",
        "settings": {
            "auth": "noauth",
            "udp": True,
            "userLevel": 0
        }
    })

    # Build the main outbound from the parsed URI parameters
    # We ensure the tag used by the outbound is the internal_tag for API stats to work
    outbound = builder.build_outbound_from_params(params, explicit_tag=outbound_internal_tag)
    if not outbound:
        print(f"! Failed to build outbound for '{outbound_display_tag}'. Exiting.")
        return

    builder.add_outbound(outbound)
    builder.add_outbound({"protocol": "freedom", "tag": "direct"}) # Add a direct outbound for completeness

    print("\n" + "="*20 + " FINAL XRAY CONFIG TO BE USED " + "="*20)
    final_config_json = builder.to_json()
    print(final_config_json)
    print("="*61 + "\n")

    project_root = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    vendor_path = project_root / "vendor" # The directory containing xray.exe

    print(f"* Starting Xray with API enabled on {api_address}...")

    # NEW: XrayCore constructor now takes vendor_path and config_builder
    # debug_mode=True can be useful here to keep the config file for inspection
    with XrayCore(vendor_path=str(vendor_path), config_builder=builder, debug_mode=False) as xray:
        if not xray.is_running():
            print("! Xray failed to start. Check logs for errors.")
            return

        print(f"\n* Xray is running. SOCKS proxy on 127.0.0.1:{local_socks_port}. API on {api_address}.")
        print("* Now, generate some traffic through the SOCKS proxy (e.g., configure your browser or use curl via 127.0.0.1:10808).")
        print(f"* Monitoring stats for outbound tag: '{outbound_display_tag}' (internal: '{outbound_internal_tag}')")
        print("* Press Ctrl+C to stop.\n")

        # NEW: Create an XrayApiClient instance to interact with the API
        api_client = XrayApiClient(api_address=api_address)

        try:
            while True:
                time.sleep(2)
                # The tag to query the API for must be the internal tag used in the config
                stats = api_client.get_stats(tag=outbound_internal_tag)
                if stats:
                    uplink_mb = stats.get('uplink', 0) / (1024 * 1024)
                    downlink_mb = stats.get('downlink', 0) / (1024 * 1024)
                    print(f"\r* Live Stats for '{outbound_display_tag}': Uplink: {uplink_mb:.2f} MB | Downlink: {downlink_mb:.2f} MB", end="", flush=True)
                else:
                    print(f"\r* Waiting for traffic on tag '{outbound_display_tag}'...", end="", flush=True)
        except KeyboardInterrupt:
            print("\n* User stopped the stats viewer.")
        except Exception as e:
            print(f"\n! An error occurred while fetching stats: {e}")

    print("\n* Demo finished.")

if __name__ == "__main__":
    main()