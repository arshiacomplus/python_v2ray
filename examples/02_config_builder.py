# examples/02_config_builder.py

import time
import os
import sys
import json

# * This ensures the script can find our local library files
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_v2ray.core import XrayCore
from python_v2ray.config_parser import parse_uri, XrayConfigBuilder

def run_test_with_uri(xray_path: str, uri: str):
    """
    * A helper function to test a single URI from start to finish.
    """
    print("\n" + "="*60)
    print(f"* Testing URI: {uri[:50]}...")
    print("="*60)

    params = parse_uri(uri)
    if not params:
        print("! TEST FAILED: Could not parse the URI.")
        return

    print(f"* PARSING SUCCESS: Protocol='{params.protocol}', Address='{params.address}:{params.port}'")
    # print(f"* Full Params: {params}") # note: Uncomment for deep debugging

    print("\n* Building full Xray config...")
    builder = XrayConfigBuilder()

    # * Add a local SOCKS inbound for our apps to connect to
    builder.add_inbound({
        "port": 10808, "listen": "127.0.0.1", "protocol": "socks",
        "settings": {"auth": "noauth", "udp": True}
    })

    # * Build the outbound using our powerful engine
    outbound_dict = builder.build_outbound_from_params(params)
    builder.add_outbound(outbound_dict)

    # * Add default direct and block outbounds (good practice)
    builder.add_outbound({"protocol": "freedom", "tag": "direct"})
    builder.add_outbound({"protocol": "blackhole", "tag": "block"})

    print("\n* Final JSON config generated:")
    print(builder.to_json())


    print("\n* Attempting to start Xray core...")
    try:
        with XrayCore(executable_path=xray_path, config_builder=builder) as xray:
            if xray.is_running():
                print("\n* SUCCESS! Xray is running with this config.")
                print("* Local SOCKS proxy is available on 127.0.0.1:10808")
                print("* Running for 5 seconds...")
                time.sleep(5)
            else:
                print("\n! TEST FAILED: Xray did not start.")
    except Exception as e:
        print(f"\n! TEST FAILED: An error occurred during Xray execution: {e}")

    print(f"* Test finished for URI: {uri[:50]}...")


def main():
    """
    * Runs a series of tests with different URI types.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    xray_path = os.path.join(project_root, "vendor", "xray.exe") # ? On Linux/Mac, this would be "xray"

    if not os.path.exists(xray_path):
        print(f"! FATAL ERROR: Xray executable not found at '{xray_path}'")
        print("! Please download it and place it in the 'vendor' folder.")
        return

    # ! =======================================================================
    # ! === REPLACE THESE WITH YOUR OWN REAL TEST URIS                      ===
    # ! =======================================================================
    test_uris = [
        "vless://YOUR_UUID@your.domain.com:443?security=tls&sni=your.domain.com&fp=chrome&type=ws&path=%2F#VLESS-WS-TLS",
        "vmess://ewogICJ2IjogIjIiLAogICJwcyI6ICJWbWVzcy1URU5UIEtleSIsCiAgImFkZCI6ICJzb21lLmRvbWFpbi5jb20iLAogICJwb3J0IjogIjgwODAiLAogICJpZCI6ICJZV1JzTFRrM1pHRXRaV1UwTnkxa05EVm1MVGhsWm1NdFkyVTVNRFJsWWpkaE5XRmpZdyIsCiAgImFpZCI6ICIwIiwKICAic2N5IjogImF1dG8iLAogICJuZXQiOiAidGNwIiwKICAidHlwZSI6ICJub25lIiwKICAiaG9zdCI6ICIiLAogICJwYXRoIjogIi8iLAogICJ0bHMiOiAiIiwKICAic25pIjogIiIKfQ==",
        "trojan://YOUR_PASSWORD@your.domain.com:443?sni=your.domain.com#Trojan-Test",
        "ss://YWVzLTI1Ni1nY206eW91cl9wYXNzd29yZA==@your.domain.com:8443#ShadowSocks-Test"
    ]

    for uri in test_uris:
        if "YOUR_" in uri:
            print(f"\n! Skipping placeholder URI: {uri[:50]}...")
            print("! Please replace it with your own real config URI in the 'test_uris' list to test it.")
            continue
        run_test_with_uri(xray_path, uri)


if __name__ == "__main__":
    main()