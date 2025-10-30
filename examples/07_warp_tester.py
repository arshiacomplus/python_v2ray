# examples/07_warp_tester.py

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
    * Demonstrates how to use the "WARP-on-Any" proxy chaining feature.
    * This script tests the connectivity (ping) of several configurations,
    * forcing all their traffic through a single WARP (WireGuard) outbound.
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
    # ! === STEP 1: Define your WARP config (must be a WireGuard URI)       ===
    # ! =======================================================================
    # Replace with a REAL WireGuard URI. This example uses a placeholder.
    warp_uri = "wireguard://qJPoIYFnhd/zKuLFPf8/FUyLCbwIzUSNMKvelMlFUnM=@188.114.98.224:891?address=172.16.0.2/32+2606:4700:110:846c:e510:bfa1:ea9f:5247/128&publicKey=bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=&reserved=79,60,41&keepAlive=10&mtu=1330&wnoise=quic&wnoisecount=15&wnoisedelay=1-3&wpayloadsize=1-8#Tel= @arshiacomplus wir>>IR:-1"

    # ! =======================================================================
    # ! === STEP 2: Define the primary configs to test THROUGH WARP         ===
    # ! =======================================================================
    test_uris = [
        "vless://YOUR_UUID@your.domain.com:443?security=tls&sni=your.domain.com&fp=chrome&type=ws&path=%2F#VLESS-WS-TLS-Via-Warp",
        "trojan://YOUR_PASSWORD@another.domain.com:443?sni=another.domain.com#Trojan-Via-Warp"
    ]

    # 3. Parse all configurations
    print("\n* Parsing all URIs for the WARP connectivity test...")
    parsed_warp_config = parse_uri(warp_uri)
    parsed_test_configs = [p for p in (parse_uri(uri) for uri in test_uris) if p]

    # --- Input Validation ---
    if not parsed_warp_config or "YOUR_PRIVATE_KEY" in warp_uri: # Check for placeholder
        print("\n! No valid WARP configuration found.")
        print("! Please edit the 'warp_uri' variable with a real WireGuard config.")
        return
    
    # Filter out placeholder URIs for the main test configs
    real_test_configs = [p for p in parsed_test_configs if "YOUR_" not in p.id and "your.domain.com" not in p.address and "another.domain.com" not in p.address]
    
    if not real_test_configs:
        print("\n! No valid primary configurations found to test.")
        print("! Please edit the 'test_uris' list with your real configurations.")
        return

    print(f"\n* Preparing to run connectivity test for {len(real_test_configs)} config(s) through WARP ({parsed_warp_config.display_tag})...")

    # 4. Create an instance of the tester
    tester = ConnectionTester(vendor_path=str(vendor_dir), core_engine_path=str(core_engine_dir))

    # 5. Call the test_uris function, passing the parsed WARP config as kwargs
    results = tester.test_uris(
        parsed_params=real_test_configs,
        warp_config=parsed_warp_config, # <--- Pass the WARP config here
        timeout=30
    )

    # 6. Print the results
    print("\n" + "="*20 + " WARP ON ANY PING TEST RESULTS " + "="*20)
    if results:
        # Sort results by ping time (lowest first)
        sorted_results = sorted(results, key=lambda x: x.get('ping_ms', 9999))
        for result in sorted_results:
            # Use the display_tag from the result dictionary
            tag = result.get('tag', 'N/A')
            ping = result.get('ping_ms', -1)
            status = result.get('status', 'error')

            if status == 'success' and ping > 0:
                print(f"* Tag: {tag:<30} | Ping: {ping:>4} ms | Status: SUCCESS")
            else:
                print(f"! Tag: {tag:<30} | Ping: ---- ms | Status: FAILED ({status})")
    else:
        print("! No results were received from the tester.")
    print("="*67)


if __name__ == "__main__":
    main()