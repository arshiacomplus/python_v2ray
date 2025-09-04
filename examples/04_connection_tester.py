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
        "vless://8b63cf90-830c-4fd8-a911-9e84fd7a5898@172.67.74.104:443?path=%2F%3FJoin---i10VPN---Join---i10VPN---Join---i10VPN---Join---i10VPN%3Fed%3D512&security=tls&encryption=none&alpn=http%2F1.1&host=s.s.google.com.b5r.ir.&fp=chrome&type=ws&sni=b5r.ir#vless",
        "hy2://dongtaiwang.com@208.87.243.187:22222/?insecure=1&sni=www.bing.com#hy2",
        "hy2://dongtaiwang.com@51.159.111.32:5355/?insecure=1&sni=www.bing.com#hy2",
        "hy2://7GEEGxAfgQaVPQX0PGk7lIuj3I@158.41.110.234:10820/?insecure=1&sni=bing.com#hy2",
        "vmess://eyJhZGQiOiI0NS4xMjguNTQuODQiLCJhaWQiOiIwIiwiYWxwbiI6IiIsImVjaENvbmZpZ0xpc3QiOiIiLCJlY2hGb3JjZVF1ZXJ5IjoiIiwiZWNoU2VydmVyS2V5cyI6IiIsImZha2Vob3N0X2RvbWFpbiI6IiIsImZwIjoiIiwiaG9zdCI6IiIsImlkIjoiNzJmZWI4MzMtNDE5Ni00YTcwLWEzZjUtYWViMDExZjdkNTM0IiwiaW50ZXJ2YWwiOiIiLCJsZW5ndGgiOiIiLCJtdXgiOiIiLCJtdXhDb25jdXJyZW5jeSI6IiIsIm5ldCI6InRjcCIsInBhY2tldHMiOiIiLCJwYXRoIjoiIiwicG9ydCI6IjM3MzEzIiwicHMiOiIwODQg4pyC77iPLfCfh6bwn4e/QVotKEBHaGV5Y2hpQW1vb3plc2gpIiwic2N5IjoiYXV0byIsInNuaSI6IiIsInRscyI6IiIsInR5cGUiOiJub25lIiwidiI6IjIifQ==",
        "trojan://2ee85121-31de-4581-a492-eb00f606e392@198.46.152.83:443?mux=&security=tls&headerType=none&type=tcp&muxConcurrency=-1&sni=sj3.freeguard.org#trojan",
        "ss://Y2hhY2hhMjAtaWV0Zi1wb2x5MTMwNTpmOGY3YUN6Y1BLYnNGOHAz@185.213.23.226:990#ss",
        # ... Add your other real URIs here ...
    ]

    fragment_settings = { "packets": "tlshello", "length": "10-30", "interval": "1-5"}

    print("* Parsing all URIs...")
    parsed_configs = [p for p in (parse_uri(uri) for uri in test_uris) if p]

    if not parsed_configs:
        print("\n! No valid URIs found to test. Please edit the 'test_uris' list in the script.")
        return

    print(f"\n* Preparing to test {len(parsed_configs)} configurations concurrently...")

    tester = ConnectionTester(vendor_path=str(vendor_dir), core_engine_path=str(core_engine_dir))

    results = tester.test_uris(parsed_configs, fragment_config=fragment_settings)

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