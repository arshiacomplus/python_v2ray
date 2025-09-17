
# examples/07_warp_tester.py

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
    warp_uri = "wireguard://qJPoIYFnhd/zKuLFPf8/FUyLCbwIzUSNMKvelMlFUnM=@188.114.98.224:891?address=172.16.0.2/32+2606:4700:110:846c:e510:bfa1:ea9f:5247/128&publicKey=bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=&reserved=79,60,41&keepAlive=10&mtu=1330&wnoise=quic&wnoisecount=15&wnoisedelay=1-3&wpayloadsize=1-8#Tel= @arshiacomplus wir>>IR:-1"

    # ! =======================================================================
    # ! === STEP 2: Define the primary configs to test THROUGH WARP         ===
    # ! =======================================================================
    test_uris = [
        "vmess://eyJhZGQiOiI0NS4xMjguNTQuODQiLCJhaWQiOiIwIiwiYWxwbiI6IiIsImVjaENvbmZpZ0xpc3QiOiIiLCJlY2hGb3JjZVF1ZXJ5IjoiIiwiZWNoU2VydmVyS2V5cyI6IiIsImZha2Vob3N0X2RvbWFpbiI6IiIsImZwIjoiIiwiaG9zdCI6IiIsImlkIjoiNzJmZWI4MzMtNDE5Ni00YTcwLWEzZjUtYWViMDExZjdkNTM0IiwiaW50ZXJ2YWwiOiIiLCJsZW5ndGgiOiIiLCJtdXgiOiIiLCJtdXhDb25jdXJyZW5jeSI6IiIsIm5ldCI6InRjcCIsInBhY2tldHMiOiIiLCJwYXRoIjoiIiwicG9ydCI6IjM3MzEzIiwicHMiOiIwODQgXHUyNzAyXHVmZTBmLVx1ZDgzY1x1ZGRlNlx1ZDgzY1x1ZGRmZkFaLShAR2hleWNoaUFtb296ZXNoKTo5MjciLCJzY3kiOiJhdXRvIiwic25pIjoiIiwidGxzIjoiIiwidHlwZSI6Im5vbmUiLCJ2IjoiMiJ9",
        "trojan://2ee85121-31de-4581-a492-eb00f606e392@198.46.152.83:443?mux=&security=tls&headerType=none&type=tcp&muxConcurrency=-1&sni=sj3.freeguard.org#trojan:5038",
    ]

    # 3. Parse all configurations
    print("\n* Parsing all URIs for the WARP connectivity test...")
    parsed_warp_config = parse_uri(warp_uri)
    parsed_test_configs = [p for p in (parse_uri(uri) for uri in test_uris) if p]

    # --- Input Validation ---
    if not parsed_warp_config or "YOUR_PRIVATE_KEY" in warp_uri:
        print("\n! No valid WARP configuration found.")
        print("! Please edit the 'warp_uri' variable with a real WireGuard config.")
        return

    real_test_configs = [p for p in parsed_test_configs if "YOUR_" not in str(p)]
    if not real_test_configs:
        print("\n! No valid primary configurations found to test.")
        print("! Please edit the 'test_uris' list with your real configurations.")
        return

    print(f"\n* Preparing to run connectivity test for {len(real_test_configs)} config(s) through WARP...")

    # 4. Create an instance of the tester
    tester = ConnectionTester(vendor_path=str(vendor_dir), core_engine_path=str(core_engine_dir))

    # 5. Call the test_uris function, passing the parsed WARP config
    results = tester.test_uris(
        parsed_params=real_test_configs,
        warp_config=parsed_warp_config,
        timeout=30
    )

    # 6. Print the results
    print("\n" + "="*20 + " WARP ON ANY PING TEST RESULTS " + "="*20)
    if results:
        # Sort results by ping time (lowest first)
        sorted_results = sorted(results, key=lambda x: x.get('ping_ms', 9999))
        for result in sorted_results:
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