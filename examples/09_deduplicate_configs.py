# examples/09_deduplicate_configs.py

import os
import sys
from pathlib import Path # NEW: Import Path
from typing import List
# Add project root to path to find our library
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import only the necessary functions and ConfigParams
from python_v2ray.config_parser import load_configs, deduplicate_configs, ConfigParams # NEW: Import ConfigParams

def main():
    """
    * A minimal example to demonstrate how to remove duplicate configurations
    * from a list based on their core properties, ignoring their display tags.
    """

    # --- Step 1: Define a list with duplicate configurations ---
    # Notice the VLESS configs are identical except for their tag.
    # Also, the Hysteria2 configs are identical except for their tag.
    raw_uris = [
        "vless://uuid1@server1.com:443?security=tls&sni=server1.com&type=ws&path=/vless1#Server_One_A",
        "vless://uuid1@server1.com:443?security=tls&sni=server1.com&type=ws&path=/vless1#Server_One_B_Different_Tag", # Duplicate core config
        "vless://uuid2@server2.com:443?security=tls&sni=server2.com&type=tcp#Server_Two",
        "trojan://pass1@server3.com:443?sni=server3.com#Trojan_One",
        "trojan://pass1@server3.com:443?sni=server3.com#Trojan_One_Again", # Duplicate core config
        "hy2://pass_hy1@hy_server1.com:443?sni=hy_server1.com&obfs=none#Hysteria_Server_A",
        "hy2://pass_hy1@hy_server1.com:443?sni=hy_server1.com&obfs=none#Hysteria_Server_B_Another_Name", # Duplicate core config
        "vless://uuid3@server4.com:80?type=tcp#Server_Three"
    ]

    print("--- Initial List of Raw URIs ---")
    for uri in raw_uris:
        print(f"- {uri}")

    # --- Step 2: Load the configs using the universal loader ---
    # This will parse the valid URIs into ConfigParams objects.
    parsed_configs: List[ConfigParams] = load_configs(source=raw_uris)


    print(f"\n* Initially parsed {len(parsed_configs)} valid configurations.")
    # Now print display_tag for better readability
    print("Display Tags of parsed configs:", [p.display_tag for p in parsed_configs])

    # --- Step 3: Apply the deduplication function ---
    print("\n--- Applying Deduplication (Ignoring Tags) ---")
    unique_configs: List[ConfigParams] = deduplicate_configs(parsed_configs)

    # --- Step 4: Display the final, clean list ---
    print(f"\n* Found {len(unique_configs)} unique configurations.")
    # Print display_tag for the unique configs
    print("Display Tags of final unique configs:", [p.display_tag for p in unique_configs])

    print("\n--- Final Clean List of URIs (for verification) ---")
    # You can now use this 'unique_configs' list for testing or other operations.
    for config in unique_configs:
        # Just printing the core info to show what was kept.
        # Use display_tag for user-friendly output.
        print(f"- Protocol: {config.protocol:<10} | Address: {config.address}:{config.port:<5} | Display Tag: {config.display_tag}")

if __name__ == "__main__":
    main()