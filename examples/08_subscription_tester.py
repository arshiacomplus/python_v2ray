# examples/08_subscription_tester.py

import os
import sys
from pathlib import Path
from typing import  List
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_v2ray.downloader import BinaryDownloader
from python_v2ray.tester import ConnectionTester
# ! Import the new universal config loader and ConfigParams
from python_v2ray.config_parser import load_configs, ConfigParams 

def main():
    """
    * Demonstrates how to load configurations from a subscription link (or file/list)
    * and then use them with the ConnectionTester for ping tests.
    """
    project_root = Path(__file__).parent.parent

    # --- Ensure binaries are ready ---
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
    # ! === USAGE EXAMPLE: Provide your subscription link here              ===
    # ! =======================================================================
    # You can also use a list of URIs or a file path.

    # --- Option 1: Load from a Subscription URL ---
    # Replace with your actual subscription URL. This example uses a placeholder.
    subscription_url = "https://raw.githubusercontent.com/mahsanet/MahsaFreeConfig/main/mtn/sub_4.txt"
    # subscription_url = "https://raw.githubusercontent.com/arshiacomplus/v2rayExtractor/refs/heads/main/vless.html" # Another example

    print(f"\n* Attempting to load configurations from subscription: {subscription_url}")
    # The `is_subscription=True` flag tells the loader to fetch and decode it.
    # `load_configs` now returns a List[ConfigParams] directly.
    parsed_configs: List[ConfigParams] = load_configs(subscription_url, is_subscription=True)

    # --- Option 2: Load from a local file (one URI per line) ---
    # file_path = Path("my_configs.txt")
    # print(f"\n* Attempting to load configurations from file: {file_path}")
    # parsed_configs: List[ConfigParams] = load_configs(file_path)

    # --- Option 3: Load from a list of strings ---
    # uri_list = [
    #     "vless://...", 
    #     "trojan://...",
    #     "hy2://..."
    # ]
    # print(f"\n* Attempting to load configurations from a list.")
    # parsed_configs: List[ConfigParams] = load_configs(uri_list)


    if not parsed_configs:
        print("\n! No valid configurations were loaded. Check your source or subscription content.")
        return

    print(f"\n* Successfully loaded {len(parsed_configs)} configurations.")

    tester = ConnectionTester(
        vendor_path=str(vendor_dir),
        core_engine_path=str(core_engine_dir)
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
            # Use the display_tag from the result dictionary
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