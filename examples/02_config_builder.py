# examples/02_config_builder.py

import time
from pathlib import Path
import json


from python_v2ray.downloader import BinaryDownloader
from python_v2ray.core import XrayCore
from python_v2ray.config_parser import parse_uri, XrayConfigBuilder

def run_test_with_uri(vendor_dir: Path, uri: str):
    """
    A helper function to test a single URI from start to finish.
    It builds a config, runs Xray, waits, and then stops.
    """
    print("\n" + "="*60)
    print(f"* Testing URI: {uri[:50]}...")
    print("="*60)

    # Step A: Parse the URI
    params = parse_uri(uri)
    if not params:
        print("! TEST FAILED: Could not parse the URI.")
        return

    print(f"* PARSING SUCCESS: Protocol='{params.protocol}', Address='{params.address}:{params.port}'")

    # Step B: Build the configuration
    print("\n* Building full Xray config...")
    builder = XrayConfigBuilder()

    # Add inbound with a specific tag
    builder.add_inbound({
        "port": 10808, "listen": "127.0.0.1", "protocol": "socks",
        "settings": {"auth": "noauth", "udp": True},
        "tag": "socks_in" # Add a tag to reference in routing
    })

    # Build and add outbound
    outbound_dict = builder.build_outbound_from_params(params)
    builder.add_outbound(outbound_dict)

    # Add a routing rule to connect inbound to outbound
    builder.config["routing"]["rules"].append({
        "type": "field",
        "inboundTag": ["socks_in"],
        "outboundTag": outbound_dict["tag"]
    })

    print("* Final JSON config generated:")

    print(json.dumps(builder.config, indent=2))

    # Step C: Run Xray with the generated config
    print("\n* Attempting to start Xray core...")
    try:
        with XrayCore(vendor_dir=str(vendor_dir), config_builder=builder) as xray:
            if xray.is_running():
                print("\n* SUCCESS! Xray is running with this config.")
                print("* Local SOCKS proxy is available on 127.0.0.1:10808")
                print("* Running for 5 seconds before next test...")
                time.sleep(5)
            else:
                print("\n! TEST FAILED: Xray did not start.")
    except Exception as e:
        print(f"\n! TEST FAILED: An error occurred during Xray execution: {e}")

    print(f"* Test finished for URI: {uri[:50]}...")


def main():
    """
    Runs a series of tests with a list of different URI types.
    """
    project_root = Path(__file__).parent.parent
    vendor_dir = project_root / "vendor"

    print("--- Running Python-V2Ray Batch URI Tester ---")
    print(f"Vendor directory set to: {vendor_dir}")
    try:
        downloader = BinaryDownloader(project_root)
        downloader.ensure_all()
    except Exception as e:
        print(f"\n! FATAL: {e}")
        return

    # ! =======================================================================
    # ! === REPLACE THESE WITH A REAL TEST URI                              ===
    # ! =======================================================================
    test_uris = [
        "vless://YOUR_UUID@your.domain.com:443?security=tls&sni=your.domain.com&fp=chrome&type=ws&path=%2F#VLESS-WS-TLS",
        "vmess://ewogICJ2IjogIjIiLAogICJwcyI6ICJWbWVzcy1URU5UIEtleSIsCiAgImFkZCI6ICJzb21lLmRvbWFpbi5jb20iLAogICJwb3J0IjogIjgwODAiLAogICJpZCI6ICJZV1JzTFRrM1pHRXRaV1UwTnkxa05EVm1MVGhsWm1NdFkyVTVNRFJsWWpkaE5XRmpZdyIsCiAgImFpZCI6ICIwIiwKICAic2N5IjogImF1dG8iLAogICJuZXQiOiAidGNwIiwKICAidHlwZSI6ICJub25lIiwKICAiaG9zdCI6ICIiLAogICJwYXRoIjogIi8iLAogICJ0bHMiOiAiIiwKICAic25pIjogIiIKfQ==",
        "trojan://YOUR_PASSWORD@your.domain.com:443?sni=your.domain.com#Trojan-Test",
        "ss://YWVzLTI1Ni1nY206eW91cl9wYXNzd29yZA==@your.domain.com:8443#ShadowSocks-Test"
    ]


    for uri in test_uris:
        if "YOUR_" in uri or "your.domain.com" in uri:
            continue
        run_test_with_uri(vendor_dir, uri)


if __name__ == "__main__":
    main()