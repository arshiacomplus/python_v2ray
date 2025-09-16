import requests
import time
import logging
from typing import Dict, Optional
class SpeedTester:
    """
    * A dedicated tool to measure download speed through a SOCKS proxy.
    """
    def __init__(self, download_url: str = "https://speed.cloudflare.com/__down"):
        self.base_url = download_url
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
    def test_download_speed(self, proxy_address: str, download_bytes: int = 10000000) -> Dict[str, float]:
        """
        * Performs a download test through the specified proxy.
        Args:
            proxy_address (str): The address of the SOCKS proxy (e.g., "127.0.0.1:20800").
            download_bytes (int): The number of bytes to download for the test.
        Returns:
            A dictionary containing the download speed in Mbps and bytes downloaded.
        """
        proxies = {
            'http': f'socks5h://{proxy_address}',
            'https': f'socks5h://{proxy_address}',
        }
        test_url = f"{self.base_url}?bytes={download_bytes}"
        total_bytes_downloaded = 0
        start_time = 0
        duration = 0
        try:
            logging.info(f"Starting speed test for proxy {proxy_address} using URL: {test_url}")
            start_time = time.perf_counter()
            with requests.get(test_url, proxies=proxies, stream=True, timeout=30) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=8192):
                    total_bytes_downloaded += len(chunk)
            duration = time.perf_counter() - start_time
            if duration == 0:
                return {"download_mbps": float('inf'), "bytes_downloaded": total_bytes_downloaded}
            speed_bps = total_bytes_downloaded / duration
            speed_mbps = (speed_bps * 8) / (1024 * 1024)
            logging.info(f"Speed test for {proxy_address} completed: {speed_mbps:.2f} Mbps")
            return {"download_mbps": round(speed_mbps, 2), "bytes_downloaded": total_bytes_downloaded}
        except requests.exceptions.RequestException as e:
            logging.error(f"Speed test for {proxy_address} failed: {e}")
            return {"download_mbps": 0.0, "bytes_downloaded": total_bytes_downloaded}
        except Exception as e:
            logging.error(f"An unexpected error occurred during speed test for {proxy_address}: {e}")
            return {"download_mbps": 0.0, "bytes_downloaded": total_bytes_downloaded}
