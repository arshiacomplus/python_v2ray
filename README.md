# python-v2ray

[![PyPI Version](https://img.shields.io/pypi/v/python-v2ray.svg)](https://pypi.org/project/python-v2ray/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python Versions](https://img.shields.io/pypi/pyversions/python-v2ray.svg)](https://pypi.org/project/python-v2ray/)

A powerful, high-level Python wrapper for managing and testing V2Ray/Xray-core and Hysteria clients.

This library abstracts the complexities of binary management, multi-format config parsing, and concurrent connection testing, providing a clean and streamlined API for developers.

---

## ✨ Features

- **Automated Binary Management**: Automatically downloads and manages the necessary `Xray-core`, `Hysteria`, and test engine binaries for your platform (Windows, macOS, Linux).
- **Unified Config Parser**: Seamlessly parses various subscription link formats (`vless`, `vmess`, `trojan`, `ss`, `hysteria2`) into a standardized Python object model.
- **High-Speed Concurrent Testing**: Utilizes a hybrid architecture (Python + Go) to test dozens of configurations simultaneously, reporting latency and connection status in seconds.
- **Dynamic Config Builder**: A fluent builder API to programmatically construct complex Xray JSON configurations with custom inbounds, outbounds, and routing rules.
- **Live Statistics**: Connect to a running Xray-core instance's gRPC API to fetch live traffic statistics (uplink & downlink).
- **Cross-Platform**: Designed to work flawlessly across Windows, macOS, and Linux environments.

## 🚀 Installation

Install the latest stable version from PyPI:

```bash
pip install python-v2ray
```

## ⚡️ Quick Start: Test a List of Proxies

This example demonstrates the core functionality: downloading dependencies, parsing URIs, and running a connection test.

```python
from pathlib import Path
from python_v2ray.downloader import BinaryDownloader
from python_v2ray.tester import ConnectionTester
from python_v2ray.config_parser import parse_uri

def run_tests():
    """
    An example of ensuring binaries, parsing URIs, and testing their connectivity.
    """
    project_root = Path("./") # Assumes running from the project's root directory

    # --- 1. Ensure all required binaries are available ---
    print("--- Verifying binaries ---")
    try:
        downloader = BinaryDownloader(project_root)
        downloader.ensure_all()
    except Exception as e:
        print(f"Fatal Error: {e}")
        return

    # --- 2. Define your list of proxy URIs ---
    test_uris = [
        "vless://...",
        "vmess://...",
        "hysteria2://...",
        # ... add more of your configs here
    ]

    # --- 3. Parse all URIs into a unified format ---
    print("\n* Parsing URIs...")
    parsed_configs = [p for p in (parse_uri(uri) for uri in test_uris) if p]
    if not parsed_configs:
        print("No valid configurations found to test.")
        return

    print(f"* Preparing to test {len(parsed_configs)} configurations concurrently...")

    # --- 4. Initialize and run the tester ---
    tester = ConnectionTester(
        vendor_path=str(project_root / "vendor"),
        core_engine_path=str(project_root / "core_engine")
    )
    results = tester.test_uris(parsed_configs)

    # --- 5. Display the results, sorted by latency ---
    print("\n" + "="*20 + " Test Results " + "="*20)
    if results:
        sorted_results = sorted(results, key=lambda x: x.get('ping_ms', 9999))
        for result in sorted_results:
            tag = result.get('tag', 'N/A')
            ping = result.get('ping_ms', -1)
            status = result.get('status', 'error')
            
            if status == 'success':
                print(f"✅ Tag: {tag:<35} | Latency: {ping:>4} ms | Status: {status}")
            else:
                print(f"❌ Tag: {tag:<35} | Latency: {ping:>4} ms | Status: {status.split('|').strip()}")
    else:
        print("No results were received from the tester.")
    print("="*56)

if __name__ == "__main__":
    run_tests()
```

## 🏛 Architecture: The Best of Python & Go

`python-v2ray` employs a hybrid architecture for maximum efficiency:

- **Python Orchestrator**: The high-level logic, config management, binary downloading, and process orchestration are handled in Python for its readability and flexibility.
- **Go Test Engine**: Performance-critical network operations, such as concurrent TCP/SOCKS dialing and latency tests, are delegated to a compiled Go binary (`core_engine`).

Communication between the two layers is achieved via IPC (`stdin`/`stdout`) with a simple JSON-based protocol. This design combines the development speed of Python with the raw network performance of Go.

## 🛠 Advanced Usage: Running a Single Proxy

```python
from python_v2ray.core import XrayCore
from python_v2ray.config_parser import parse_uri, XrayConfigBuilder

# Your target proxy URI
uri = "vless://YOUR_UUID@your.domain.com:443?security=tls&sni=your.domain.com#MyProxy"

params = parse_uri(uri)
if params:
    # Programmatically build a configuration
    builder = XrayConfigBuilder()
    builder.add_inbound({
        "port": 10808, "listen": "127.0.0.1", "protocol": "socks",
        "settings": {"auth": "noauth", "udp": True}
    })
    outbound = builder.build_outbound_from_params(params)
    builder.add_outbound(outbound)
    
    # Run Xray with the generated config
    # The 'with' statement ensures the process is terminated automatically
    with XrayCore(config_builder=builder) as xray:
        print("Xray is running. SOCKS proxy is available on 127.0.0.1:10808")
        # Your application logic here...
        # ...
    print("Xray has been stopped.")
```

## 🙏 Acknowledgments

This project would not be possible without the incredible work of the teams behind the core technologies it relies on. Special thanks to:

- **[GFW-knocker/Xray-core](https://github.com/GFW-knocker/Xray-core)** for the powerful and versatile Xray-core.
- **[apernet/hysteria](https://github.com/apernet/hysteria)** for the feature-rich, high-performance Hysteria proxy.

## 🤝 Contributing

Contributions are welcome! Please feel free to fork the repository, make changes, and submit a pull request.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

Distributed under the GNU General Public License v3.0. See `LICENSE` for more information.
