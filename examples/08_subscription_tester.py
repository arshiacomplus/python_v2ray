# examples/08_subscription_tester.py

import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_v2ray.downloader import BinaryDownloader
from python_v2ray.tester import ConnectionTester
# ! Import the new universal config loader
from python_v2ray.config_parser import load_configs

def main():
    project_root = Path(__file__).parent.parent

    # --- Ensure binaries are ready ---
    downloader = BinaryDownloader(project_root)
    downloader.ensure_all()

    # ! =======================================================================
    # ! === USAGE EXAMPLE: Provide your subscription link here              ===
    # ! =======================================================================
    # You can also use a list of URIs or a file path.

    # --- Option 1: Load from a Subscription URL ---
    subscription_url = "https://raw.githubusercontent.com/arshiacomplus/v2rayExtractor/refs/heads/main/vless.html"

    # The `is_subscription=True` flag tells the loader to fetch and decode it.
    parsed_configs = [load_configs(subscription_url, is_subscription=True)]

    # --- Option 2: Load from a local file (one URI per line) ---
    # file_path = Path("my_configs.txt")
    # parsed_configs = load_configs(file_path)

    # --- Option 3: Load from a list of strings ---
    # uri_list = ["vless://...", "trojan://..."]
    # parsed_configs = load_configs(uri_list)

    if not parsed_configs:
        print("\n! No valid configurations were loaded. Check your source.")
        return

    print(f"\n* Successfully loaded {len(parsed_configs)} configurations.")

    tester = ConnectionTester(
        vendor_path=str(project_root / "vendor"),
        core_engine_path=str(project_root / "core_engine")
    )

    # Now you can use the loaded configs with any tester function
    print("\n--- Running Connectivity Test on Subscription Configs ---")
    results = tester.test_uris(
        parsed_params=parsed_configs,
        timeout=15
    )

    if results:
        sorted_results = sorted(results, key=lambda x: x.get('ping_ms', 9999))
        for result in sorted_results:
            tag = result.get('tag', 'N/A')
            ping = result.get('ping_ms', -1)
            status = result.get('status', 'error')

            if status == 'success':
                print(f"* Tag: {tag:<40} | Ping: {ping:>4} ms")
            else:
                print(f"! Tag: {tag:<40} | Ping: FAILED ({status})")
    else:
        print("! No results were received from the tester.")

if __name__ == "__main__":
    main()