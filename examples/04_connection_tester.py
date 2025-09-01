# examples/04_connection_tester.py

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pathlib import Path
from python_v2ray.config_parser import parse_uri, XrayConfigBuilder
from python_v2ray.tester import ConnectionTester
from python_v2ray.downloader import BinaryDownloader

def main():
    """
    * Runs a series of tests with different URI types.
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
    # Set to None to disable fragmentation
    fragment_settings = {
        "packets": "tlshello",
        "length": "10-30",
        "interval": "1-5"
    }

    test_uris = [
        "vless://8b63cf90-830c-4fd8-a911-9e84fd7a5898@172.67.74.104:443?path=%2F%3FJoin---i10VPN---Join---i10VPN---Join---i10VPN---Join---i10VPN%3Fed%3D512&security=tls&encryption=none&alpn=http%2F1.1&host=s.s.google.com.b5r.ir.&fp=chrome&type=ws&sni=b5r.ir#vless",
        "hy2://dongtaiwang.com@208.87.243.187:22222/?insecure=1&sni=www.bing.com#hy2",
        "hy2://dongtaiwang.com@51.159.111.32:5355/?insecure=1&sni=www.bing.com#hy2",
        "hy2://7GEEGxAfgQaVPQX0PGk7lIuj3I@158.41.110.234:10820/?insecure=1&sni=bing.com#hy2",
        "vmess://eyJhZGQiOiJucG1qcy5jb20iLCJhaWQiOiIwIiwiYWxwbiI6IiIsImVjaENvbmZpZ0xpc3QiOiIiLCJlY2hGb3JjZVF1ZXJ5IjoiIiwiZWNoU2VydmVyS2V5cyI6IiIsImZha2Vob3N0X2RvbWFpbiI6IiIsImZwIjoiIiwiaG9zdCI6Im5hc25ldC0xMjgxNDAxMTIyMy5raGFzdGVobmFiYXNoaS5jb20iLCJpZCI6Im5hc25ldCIsImludGVydmFsIjoiIiwibGVuZ3RoIjoiIiwibXV4IjoiIiwibXV4Q29uY3VycmVuY3kiOiIiLCJuZXQiOiJ3cyIsInBhY2tldHMiOiIiLCJwYXRoIjoiL05BU05FVC9jZG4iLCJwb3J0IjoiODA4MCIsInBzIjoiXHUwMDNlXHUwMDNlQEZyZWFrQ29uZmlnOjpERSIsInNjeSI6ImF1dG8iLCJzbmkiOiIiLCJ0bHMiOiIiLCJ0eXBlIjoiIiwidiI6IjIifQ==",
        "trojan://2ee85121-31de-4581-a492-eb00f606e392@198.46.152.83:443?mux=&security=tls&headerType=none&type=tcp&muxConcurrency=-1&sni=sj3.freeguard.org#20%F0%9F%8E%A1%40oneclickvpnkeys",
        "ss://Y2hhY2hhMjAtaWV0Zi1wb2x5MTMwNTpmOGY3YUN6Y1BLYnNGOHAz@185.213.23.226:990#%3E%3E%40free4allVPN%3A%3ANO",
        # ... Add your other real URIs here ...
    ]

    print("* Parsing all URIs...")
    outbounds_to_test = []
    builder = XrayConfigBuilder()

    for uri in test_uris:
        if "YOUR_" in uri or "..." in uri:
            print(f"! Skipping placeholder URI: {uri}")
            continue
        params = parse_uri(uri)
        if params:
            outbound_dict = builder.build_outbound_from_params(params)
            outbounds_to_test.append(outbound_dict)

    if not outbounds_to_test:
        print("\n! No valid URIs found to test. Please edit the 'test_uris' list in the script.")
        return

    print(f"\n* Preparing to test {len(outbounds_to_test)} configurations concurrently...")

    tester = ConnectionTester(vendor_path=str(vendor_dir), core_engine_path=str(core_engine_dir))
    results = tester.test_outbounds(outbounds_to_test)

    print("\n" + "="*20 + " TEST RESULTS " + "="*20)
    if results:
        sorted_results = sorted(results, key=lambda x: x.get('ping_ms', 9999))
        for result in sorted_results:
            tag = result.get('tag', 'N/A')
            ping = result.get('ping_ms', -1)
            status = result.get('status', 'error')
            if status == 'success':
                print(f"* Tag: {tag:<20} | Ping: {ping:>4} ms | Status: {status}")
            else:
                print(f"! Tag: {tag:<20} | Ping: {ping:>4} ms | Status: {status}")
    else:
        print("! No results received from the tester.")
    print("="*54)

if __name__ == "__main__":
    main()