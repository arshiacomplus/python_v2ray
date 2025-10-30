# examples/04_connection_tester.py

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
    * Demonstrates how to use the high-speed, multi-client connection tester for ping tests.
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
        print(f"\n! FATAL: Could not download necessary files: {e}")
        return

    vendor_dir = project_root / "vendor"
    core_engine_dir = project_root / "core_engine"


    # ! =======================================================================
    # ! === PLACE YOUR REAL TEST URIS HERE                                  ===
    # ! =======================================================================
    test_uris = [

        "vmess://eyJhZGQiOiI0NS4xMjguNTQuODQiLCJhaWQiOiIwIiwiYWxwbiI6IiIsImVjaENvbmZpZ0xpc3QiOiIiLCJlY2hGb3JjZVF1ZXJ5IjoiIiwiZWNoU2VydmVyS2V5cyI6IiIsImZha2Vob3N0X2RvbWFpbiI6IiIsImZwIjoiIiwiaG9zdCI6IiIsImlkIjoiNzJmZWI4MzMtNDE5Ni00YTcwLWEzZjUtYWViMDExZjdkNTM0IiwiaW50ZXJ2YWwiOiIiLCJsZW5ndGgiOiIiLCJtdXgiOiIiLCJtdXhDb25jdXJyZW5jeSI6IiIsIm5ldCI6InRjcCIsInBhY2tldHMiOiIiLCJwYXRoIjoiIiwicG9ydCI6IjM3MzEzIiwicHMiOiIwODQgXHUyNzAyXHVmZTBmLVx1ZDgzY1x1ZGRlNlx1ZDgzY1x1ZGRmZkFaLShAR2hleWNoaUFtb296ZXNoKTo5MjciLCJzY3kiOiJhdXRvIiwic25pIjoiIiwidGxzIjoiIiwidHlwZSI6Im5vbmUiLCJ2IjoiMiJ9"
        ]

    # ! =======================================================================
    # ! === CUSTOM MUX AND FRAGMENT SETTINGS (OPTIONAL - WILL OVERRIDE URI) ===
    # ! =======================================================================
    # These settings will apply to Xray-compatible configs (VLESS, VMess, Trojan, SS, SOCKS).
    # They will override any mux/fragment settings parsed directly from a mvless URI,
    # if `mux_override` or `fragment_override` are passed to the tester method.

    # Example 1: To globally enable Mux for all Xray-compatible configs
    # custom_mux_settings = {"enabled": True, "concurrency": 8}
    custom_mux_settings = {} # Default: No global Mux override

    # Example 2: To globally enable Fragment for all Xray-compatible configs
    # This will cause them to use a separate 'fragment' outbound in Xray.
    # custom_fragment_settings = {
    #     "packets": "tlshello", 
    #     "length": "10-20", 
    #     "interval": "10-20"
    # }
    custom_fragment_settings = None # Default: No global Fragment override


    print("* Parsing all URIs...")
    parsed_configs = [p for p in (parse_uri(uri) for uri in test_uris) if p]

    # Filter out placeholder URIs
    real_configs = [p for p in parsed_configs if "YOUR_" not in p.id and "YOUR_" not in getattr(p, 'hy2_password', '') and "your.domain.com" not in p.address and "your.mvless.com" not in p.address]

    if not real_configs:
        print("\n! No valid configurations found to test.")
        print("! Please edit the 'test_uris' list in this script with your real configurations.")
        return

    print(f"\n* Preparing to test {len(real_configs)} configurations concurrently...")

    tester = ConnectionTester(vendor_path=str(vendor_dir), core_engine_path=str(core_engine_dir))

    # Now we pass the custom mux/fragment settings as kwargs
    results = tester.test_uris(
        parsed_params=real_configs,
        timeout=15,
        mux_config=custom_mux_settings,         # <--- Pass custom Mux settings
        fragment_config=custom_fragment_settings # <--- Pass custom Fragment settings
    )
    
    print("\n" + "="*20 + " CONNECTION TEST RESULTS " + "="*20)
    if results:
        sorted_results = sorted(results, key=lambda x: x.get('ping_ms', 9999))
        for result in sorted_results:
            # Use the display_tag from the result dictionary
            tag = result.get('tag', 'N/A') 
            ping = result.get('ping_ms', -1)
            status = result.get('status', 'error')
            if status == 'success':
                print(f"* Tag: {tag:<30} | Ping: {ping:>4} ms | Status: {status}")
            else:
                print(f"! Tag: {tag:<30} | Ping: ---- ms | Status: FAILED ({status})") # Ping -1 now shows '----'
    else:
        print("! No results received from the tester.")
    print("="*64)

if __name__ == "__main__":
    main()