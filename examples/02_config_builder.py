# examples/02_config_builder.py

import time
import os
import sys
import json
from pathlib import Path # NEW: Import Path for cleaner path handling

# * This ensures the script can find our local library files
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_v2ray.core import XrayCore # Keep for XrayCore management in the demo
from python_v2ray.config_parser import parse_uri, XrayConfigBuilder, ConfigParams # NEW: Import ConfigParams
from python_v2ray.tester import ConnectionTester # NEW: Import ConnectionTester for unified testing

def run_test_with_uri(
    vendor_path: str, # Changed from xray_path to vendor_path
    core_engine_path: str, # NEW: Added core_engine_path
    uri: str
):
    """
    * A helper function to test a single URI from start to finish using the ConnectionTester.
    """
    print("\n" + "="*60)
    print(f"* Testing URI: {uri[:50]}...")
    print("="*60)

    params = parse_uri(uri)
    if not params:
        print("! TEST FAILED: Could not parse the URI.")
        return

    # Now we have display_tag from ConfigParams
    print(f"* PARSING SUCCESS: Protocol='{params.protocol}', Address='{params.address}:{params.port}', Display Tag='{params.display_tag}'")
    # print(f"* Full Params: {params}") # note: Uncomment for deep debugging

    print("\n* Building full Xray config (internally by ConnectionTester)...")

    # Initialize ConnectionTester
    tester = ConnectionTester(vendor_path=vendor_path, core_engine_path=core_engine_path)

    # Use test_uris method which handles XrayCore lifecycle and config building
    # We pass a list of one ConfigParams object.
    results = tester.test_uris(parsed_params=[params], timeout=30)  # Added timeout

    print("\n* Test results from ConnectionTester:")
    if results:
        for result in results:
            tag = result.get('tag', 'N/A')
            ping = result.get('ping_ms', -1)
            status = result.get('status', 'error')
            if status == 'success':
                print(f"* Tag: {tag:<30} | Ping: {ping:>4} ms | Status: SUCCESS")
            else:
                print(f"! Tag: {tag:<30} | Ping: ---- ms | Status: FAILED ({status})")
    else:
        print("! No results received from the tester for this URI.")

    print(f"* Test finished for URI: {uri[:50]}...")


def main():
    """
    * Runs a series of tests with different URI types using ConnectionTester.
    """
    project_root = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    # We now pass the vendor directory, not the specific executable path
    vendor_dir = project_root / "vendor"
    core_engine_dir = project_root / "core_engine" # NEW: Path to core_engine

    # Ensure binaries are ready (This is usually done by the CLI, but good for standalone examples)
    try:
        from python_v2ray.downloader import BinaryDownloader
        downloader = BinaryDownloader(project_root)
        downloader.ensure_all()
        print("* All necessary binaries are ready.")
    except Exception as e:
        print(f"\n! FATAL ERROR: Could not ensure binaries: {e}")
        return

    # ! =======================================================================
    # ! === REPLACE THESE WITH YOUR OWN REAL TEST URIS                      ===
    # ! =======================================================================
    test_uris = [
        "trojan://02XtoczO7V@5.255.102.41:17590?type=ws&path=%2Fhishhhh123&host=mooshali.arshiacomplus.dpdns.org&security=tls&fp=firefox&alpn=http%2F1.1&sni=mooshali.arshiacomplus.dpdns.org#TR%2Bws%2Btls-xmdgfvsot", # Added Hysteria2 example
            "trojan://02XtoczO7V@5.255.102.41:17590?type=ws&path=%2Fhishhhh123&host=mooshali.arshiacomplus.dpdns.org&security=tls&fp=firefox&alpn=http%2F1.1&sni=mooshali.arshiacomplus.dpdns.org#TR%2Bws%2Btls-xmdgfvsot" # Added Hysteria2 example

    ]

    for uri in test_uris:
        if "YOUR_" in uri or "your." in uri: # Check for placeholders
            print(f"\n! Skipping placeholder URI: {uri[:50]}...")
            print("! Please replace it with your own real config URI in the 'test_uris' list to test it.")
            continue
        # Pass vendor_dir and core_engine_dir
        run_test_with_uri(str(vendor_dir), str(core_engine_dir), uri)


if __name__ == "__main__":
    main()