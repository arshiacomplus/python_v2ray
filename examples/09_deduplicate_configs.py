
# examples/09_deduplicate_configs.py

import os
import sys

# Add project root to path to find our library
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import only the necessary functions
from python_v2ray.config_parser import load_configs, deduplicate_configs

def main():
    """
    * A minimal example to demonstrate how to remove duplicate configurations
    * from a list, ignoring their tags (# remarks).
    """

    # --- Step 1: Define a list with duplicate configurations ---
    # Notice the first two VLESS configs are identical except for their tag.
    raw_uris = [
        "vless://abcdef@example.com:443?type=ws#VLESS-Config-1",
        "vless://abcdef@example.com:443?type=ws#VLESS-Config-2-DUPLICATE",
        "trojan://password@anotherexample.com:443#Trojan-Config-UNIQUE",
        "vless://123456@different.com:443?type=grpc#VLESS-Config-3-UNIQUE",
        "" # An empty line to show it gets filtered out
    ]

    print("--- Initial List of Raw URIs ---")
    for uri in raw_uris:
        print(f"- {uri}")

    # --- Step 2: Load the configs using the universal loader ---
    # This will parse the valid URIs into ConfigParams objects.
    parsed_configs = load_configs(source=raw_uris)



    print(f"\n* Initially parsed {len(parsed_configs)} valid configurations.")
    print("Tags of parsed configs:", [p.tag for p in parsed_configs])

    # --- Step 3: Apply the deduplication function ---
    print("\n--- Applying Deduplication (Ignoring Tags) ---")
    unique_configs = deduplicate_configs(parsed_configs)

    # --- Step 4: Display the final, clean list ---
    print(f"\n* Found {len(unique_configs)} unique configurations.")
    print("Tags of final unique configs:", [p.tag for p in unique_configs])

    print("\n--- Final Clean List of URIs (for verification) ---")
    # You can now use this 'unique_configs' list for testing or other operations.
    for config in unique_configs:
        # Just printing the core info to show what was kept
        print(f"- Protocol: {config.protocol}, Address: {config.address}, Tag: {config.tag}")

if __name__ == "__main__":
    main()