# examples/06_upload_tester.py

import os
import sys
from pathlib import Path

# * This ensures the script can find our local library files
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_v2ray.downloader import BinaryDownloader
from python_v2ray.tester import ConnectionTester
from python_v2ray.config_parser import parse_uri, ConfigParams # NEW: Import ConfigParams

def main():
    """
    * Demonstrates how to use the standalone upload speed test functionality.
    * It also shows how to pass Mux and Fragment settings from the script.
    """
    project_root = Path(__file__).parent.parent

    # 1. Ensure all necessary binaries are downloaded
    try:
        print("* Checking for required binaries...")
        downloader = BinaryDownloader(project_root)
        downloader.ensure_all()
        print("* All binaries are ready.")
    except Exception as e:
        print(f"\n! FATAL: {e}")
        return

    vendor_dir = project_root / "vendor"
    core_engine_dir = project_root / "core_engine"

    # ! =======================================================================
    # ! === PLACE YOUR REAL URIS HERE FOR THE UPLOAD TEST                   ===
    # ! =======================================================================
    test_uris = [
        "vless://YOUR_UUID@your.domain.com:443?security=tls&sni=your.domain.com&fp=chrome&type=ws&path=%2F#VLESS-WS-TLS",
        "vmess://ewogICJ2IjogIjIiLAogICJwcyI6ICJWbWVzcy1URU5UIEtleSIsCiAgImFkZCI6ICJzb21lLmRvbWFpbi5jb20iLAogICJwb3J0IjogIjgwODAiLAogICJpZCI6ICJZV1JzTFRrM1pHRXRaV1UwTnkxa05EVm1MVGhsWm1NdFkyVTVNRFJsWWpkaE5XRmpZdyIsCiAgImFpZCI6ICIwIiwKICAic2N5IjogImF1dG8iLAogICJuZXQiOiAidGNwIiwKICAidHlwZSI6ICJub25lIiwKICAiaG9zdCI6ICIiLAogICJwYXRoIjogIi8iLAogICJ0bHMiOiAiIiwKICAic25pIjogIiIKfQ==",
        "trojan://YOUR_PASSWORD@your.domain.com:443?sni=your.domain.com#Trojan-Test",
        "ss://YWVzLTI1Ni1nY206eW91cl9wYXNzd29yZA==@your.domain.com:8443#ShadowSocks-Test",
        "hy2://YOUR_HYSTERIA_PASSWORD@your.hy2server.com:443?sni=your.hy2server.com&obfs=none#Hysteria2-Test",
        "mvless://YOUR_MVLESS_ID@your.mvless.com:443?security=tls&type=ws&path=/path&mux=on&muxConcurrency=8&packets=tlshello&length=10-20&interval=10-20#Mvless-Mux-Frag-Test"
    ]

    # ! =======================================================================
    # ! === CUSTOM MUX AND FRAGMENT SETTINGS (OPTIONAL - WILL OVERRIDE URI) ===
    # ! =======================================================================
    # These settings will apply to Xray-compatible configs (VLESS, VMess, Trojan, SS, SOCKS).
    # They will override any mux/fragment settings parsed directly from a mvless URI.

    # Example: To globally enable Mux for all Xray-compatible configs
    # custom_mux_settings = {"enabled": True, "concurrency": 16}
    custom_mux_settings = {} # Default: No global Mux override

    # Example: To globally enable Fragment for all Xray-compatible configs
    # This will cause them to use a separate 'fragment' outbound in Xray.
    # custom_fragment_settings = {
    #     "packets": "tlshello", 
    #     "length": "10-20", 
    #     "interval": "10-20"
    # }
    custom_fragment_settings = None # Default: No global Fragment override

    print("\n* Parsing all URIs for the upload test...")
    parsed_configs = [p for p in (parse_uri(uri) for uri in test_uris) if p]

    # Filter out placeholder URIs
    real_configs = [p for p in parsed_configs if "YOUR_" not in p.id and "YOUR_" not in getattr(p, 'hy2_password', '') and "your.domain.com" not in p.address and "your.mvless.com" not in p.address]

    if not real_configs:
        print("\n! No valid configurations found to test.")
        print("! Please edit the 'test_uris' list in this script with your real configurations.")
        return

    print(f"\n* Preparing to run upload test on {len(real_configs)} configuration(s)...")

    # 2. Create an instance of the tester
    tester = ConnectionTester(vendor_path=str(vendor_dir), core_engine_path=str(core_engine_dir))

    # 3. Call the test_upload method
    # This will test the upload speed by sending 100KB (100,000 bytes) of data
    # The timeout for each individual test in Go is 45s (from main.go)
    results = tester.test_upload(
        parsed_params=real_configs,
        upload_bytes=100000,
        timeout=60, # Overall timeout for the Go tester process
        mux_config=custom_mux_settings,         # <--- Pass custom Mux settings
        fragment_config=custom_fragment_settings # <--- Pass custom Fragment settings
    )

    # 4. Print the results in a formatted way
    print("\n" + "="*20 + " UPLOAD TEST RESULTS " + "="*20)
    if results:
        # Sort results from fastest to slowest
        sorted_results = sorted(results, key=lambda x: x.get('upload_mbps', 0), reverse=True)

        for result in sorted_results:
            # Use the display_tag from the result dictionary
            tag = result.get('tag', 'N/A')
            speed = result.get('upload_mbps', 0.0)
            status = result.get('status', 'error')

            if status == 'success' and speed > 0:
                print(f"* Tag: {tag:<30} | Upload Speed: {speed:>5.2f} Mbps")
            else:
                # If failed, use the status message from Go as the reason
                print(f"! Tag: {tag:<30} | Upload Speed:  FAIL    | Reason: {status}")
    else:
        print("! No results were received from the tester.")
    print("="*65)


if __name__ == "__main__":
    main()