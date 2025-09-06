# examples/04_connection_tester.py

import os
import sys
from pathlib import Path

# * This ensures the script can find our local library files
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_v2ray.downloader import BinaryDownloader
from python_v2ray.tester import ConnectionTester
from python_v2ray.config_parser import parse_uri

def main():
    """
    * Demonstrates how to use the high-speed, multi-client connection tester.
    """
    project_root = Path(__file__).parent.parent

    try:
        downloader = BinaryDownloader(project_root)
        downloader.ensure_all()
    except Exception as e:
        print(f"\n! FATAL: {e}")
        return

    vendor_dir = project_root / "vendor"
    core_engine_dir = project_root / "core_engine"


    test_uris = [
        "vless:///"
        # ... Add your other real URIs here ...
    ]

    fragment_settings = { "packets": "tlshello", "length": "10-20", "interval": "10-20"}
    # mux_settings = {"enabled": True, "concurrency": 8} # ! It's better to be flase
    fragment_settings= None
    mux_settings = None
    print("* Parsing all URIs...")
    parsed_configs = [p for p in (parse_uri(uri) for uri in test_uris) if p]

    if not parsed_configs:
        print("\n! No valid URIs found to test. Please edit the 'test_uris' list in the script.")
        return

    print(f"\n* Preparing to test {len(parsed_configs)} configurations concurrently...")

    tester = ConnectionTester(vendor_path=str(vendor_dir), core_engine_path=str(core_engine_dir))

    results = tester.test_uris(
        parsed_params=parsed_configs,
        fragment_config=fragment_settings,
        mux_config=mux_settings
    )
    print("\n" + "="*20 + " TEST RESULTS " + "="*20)
    if results:
        sorted_results = sorted(results, key=lambda x: x.get('ping_ms', 9999))
        for result in sorted_results:
            tag = result.get('tag', 'N/A')
            ping = result.get('ping_ms', -1)
            status = result.get('status', 'error')
            if status == 'success':
                print(f"* Tag: {tag:<30} | Ping: {ping:>4} ms | Status: {status}")
            else:
                print(f"! Tag: {tag:<30} | Ping: {ping:>4} ms | Status: {status}")
    else:
        print("! No results received from the tester.")
    print("="*64)

if __name__ == "__main__":
    main()