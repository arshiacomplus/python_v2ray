
# examples/06_upload_tester.py

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
    * Demonstrates how to use the standalone upload speed test functionality.
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

    # ! =======================================================================
    # ! === PLACE YOUR REAL URIS HERE FOR THE UPLOAD TEST                   ===
    # ! =======================================================================
    test_uris = [
        "vless://"
        # ... Add your other real URIs here ...
    ]

    print("\n* Parsing all URIs for the upload test...")
    parsed_configs = [p for p in (parse_uri(uri) for uri in test_uris) if p]

    # Filter out placeholder URIs
    real_configs = [p for p in parsed_configs if "YOUR_" not in getattr(p, 'id', '') and "YOUR_" not in getattr(p, 'hy2_password', '')]

    if not real_configs:
        print("\n! No valid configurations found to test.")
        print("! Please edit the 'test_uris' list in this script with your real configurations.")
        return

    print(f"\n* Preparing to run upload test on {len(real_configs)} configuration(s)...")

    # 2. Create an instance of the tester
    tester = ConnectionTester(vendor_path=str(vendor_dir), core_engine_path=str(core_engine_dir))

    # 3. Call the test_upload method
    # This will test the upload speed by sending 5MB (5,000,000 bytes) of data
    results = tester.test_upload(
        parsed_params=real_configs,
        upload_bytes=100000
    )

    # 4. Print the results in a formatted way
    print("\n" + "="*20 + " UPLOAD TEST RESULTS " + "="*20)
    if results:
        # Sort results from fastest to slowest
        sorted_results = sorted(results, key=lambda x: x.get('upload_mbps', 0), reverse=True)

        for result in sorted_results:
            tag = result.get('tag', 'N/A')
            speed = result.get('upload_mbps', 0.0)
            status = result.get('status', 'error')

            if status == 'success' and speed > 0:
                print(f"* Tag: {tag:<30} | Upload Speed: {speed:>5.2f} Mbps")
            else:
                # Use the status message from Go as the reason for failure
                print(f"! Tag: {tag:<30} | Upload Speed:  FAIL    | Reason: {status}")
    else:
        print("! No results were received from the tester.")
    print("="*65)


if __name__ == "__main__":
    main()