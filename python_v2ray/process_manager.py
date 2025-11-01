import abc
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional
import logging
import time


class BaseProcessManager(abc.ABC):
    def __init__(self, vendor_path: str):
        self.vendor_path = Path(vendor_path)
        self.executable_path = self.vendor_path / self._get_executable_name()
        self.process: Optional[subprocess.Popen] = None
        self._config_file_path: Optional[str] = None
        if not self.executable_path.is_file():
            raise FileNotFoundError(f"Executable not found at: {self.executable_path}")

    @abc.abstractmethod
    def _get_executable_name(self) -> str:
        pass

    @abc.abstractmethod
    def _create_config(self) -> None:
        pass

    @abc.abstractmethod
    def _get_start_command(self) -> List[str]:
        pass

    def _cleanup_config(self) -> None:
        if hasattr(self, "debug_mode") and self.debug_mode:
            logging.info(
                f"[DEBUG MODE] Xray temporary config file kept at: {self._config_file_path}"
            )
            return
        if self._config_file_path and os.path.exists(self._config_file_path):
            try:
                os.remove(self._config_file_path)
                logging.debug(f"Config file deleted: {self._config_file_path}")
                self._config_file_path = None
            except OSError as e:
                logging.error(
                    f"Error removing config file {self._config_file_path}: {e}"
                )

    def start(self) -> None:
        if self.is_running():
            logging.info(f"{self.__class__.__name__} is already running.")
            return

        self._create_config()
        command = self._get_start_command()
        logging.info(
            f"Starting {self.__class__.__name__} with command: {' '.join(command)}"
        )

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            time.sleep(0.5)

            if self.process.poll() is not None:
                stdout_data, stderr_data = self.process.communicate()
                logging.error(
                    f"{self.__class__.__name__} exited immediately with code {self.process.returncode}."
                )

                if stdout_data:
                    logging.error(
                        f"--- CAPTURED XRAY STDOUT ---\n{stdout_data.strip()}\n--------------------------"
                    )
                if stderr_data:
                    logging.error(
                        f"--- CAPTURED XRAY STDERR ---\n{stderr_data.strip()}\n----------------------------"
                    )

                self.process = None
                self._cleanup_config()
                return

            logging.info(
                f"{self.__class__.__name__} started successfully with PID: {self.process.pid}"
            )
        except Exception as e:
            logging.error(
                f"Failed to start {self.__class__.__name__}: {e}", exc_info=True
            )
            self.process = None
            self._cleanup_config()

    def stop(self) -> None:
        if not self.is_running():
            return
        logging.info(
            f"Stopping {self.__class__.__name__} with PID: {self.process.pid}..."
        )
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            logging.warning(f"{self.__class__.__name__} was killed forcefully.")
        finally:
            self.process = None
            self._cleanup_config()  # Cleanup happens in __exit__ or here

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
