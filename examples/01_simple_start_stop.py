# examples/01_simple_start_stop.py

import time
import os
import sys

# * This is a clever way to make the script find our library
# * without having to install it first.
# * It adds the parent directory (the project root) to Python's path.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_v2ray.core import XrayCore
from python_v2ray.config_parser import XrayConfigBuilder
def main():
    """
    * A simple demonstration of starting and stopping the Xray core using the new architecture.
    * It dynamically builds a minimal Xray configuration (a SOCKS inbound and a direct outbound).
    """
    # note: Define paths relative to the project root.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    # vendor_path is the directory where xray.exe (or xray_linux/macos) resides.
    # It's now passed to XrayCore, which will find the executable within this directory.
    vendor_path = os.path.join(project_root, "vendor")

    # 1. Create an Xray configuration builder instance.
    # The XrayCore now expects an XrayConfigBuilder instance, not a direct config file path.
    print("* Creating a minimal Xray configuration dynamically...")
    builder = XrayConfigBuilder()

    # For this simple start/stop demo, we'll add a basic SOCKS inbound
    # and a freedom outbound to make the config valid and functional.
    # This shows how the builder is used to create the config.
    builder.add_inbound({
        "tag": "local-socks",
        "port": 10808,
        "listen": "127.0.0.1",
        "protocol": "socks",
        "settings": {"auth": "noauth", "udp": True}
    })
    builder.add_outbound({"protocol": "freedom", "tag": "direct"}) # Xray typically requires at least one outbound

    print("\n* Final JSON config generated (minimal):")
    print("="*60)
    print(builder.to_json())
    print("="*60)

    print("\n* Attempting to start Xray core...")
    try:
        # Create an instance of our core controller.
        # XrayCore now takes `vendor_path` and a `config_builder` instance.
        # The `executable_path` and `config_path` arguments are no longer used here.
        with XrayCore(vendor_path=vendor_path, config_builder=builder, debug_mode=False) as xray:
            if xray.is_running():
                print("\n* SUCCESS! Xray is running with the minimal config.")
                print("* A local SOCKS proxy is available on 127.0.0.1:10808 (if you added the inbound).")
                print("* Waiting for 10 seconds before stopping...")
                time.sleep(10)
            else:
                print("\n! Xray failed to start.")
                print("! Please check the 'vendor' path, executable permissions, or the dynamically generated config.")
                return

        print("\n* Demo finished.")

    except FileNotFoundError as e:
        print(f"\n! ERROR: A required file was not found.")
        print(f"! {e}")
        print("! Please make sure you have downloaded the Xray core executable into the 'vendor' folder.")
    except Exception as e:
        print(f"\n! An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()