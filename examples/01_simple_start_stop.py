# examples/01_simple_start_stop.py

import time
import os
import sys

# * This is a clever way to make the script find our library
# * without having to install it first.
# * It adds the parent directory (the project root) to Python's path.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_v2ray.core import XrayCore

def main():
    """
    * A simple demonstration of starting and stopping the Xray core.
    """
    # note: Define paths relative to the project root.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    xray_path = os.path.join(project_root, "vendor", "xray.exe") # ? On Linux/Mac, this would be just "xray"
    config_path = os.path.join(project_root, "config.json")

    print(f"note: Using Xray executable at: {xray_path}")
    print(f"note: Using config file at: {config_path}")

    try:
        # Create an instance of our core controller
        xray = XrayCore(executable_path=xray_path, config_path=config_path)

        # Start the core
        xray.start()

        if xray.is_running():
            print("\n* Xray is running. You can check your Task Manager.")
            print("* Waiting for 10 seconds before stopping...")
            time.sleep(10)
        else:
            print("\n! Xray failed to start. Check the paths and permissions.")
            return

        # Stop the core
        xray.stop()
        print("\n* Demo finished.")

    except FileNotFoundError as e:
        print(f"\n! ERROR: A required file was not found.")
        print(f"! {e}")
        print("! Please make sure you have downloaded the Xray core into the 'vendor' folder.")
    except Exception as e:
        print(f"\n! An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()