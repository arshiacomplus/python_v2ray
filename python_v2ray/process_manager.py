import abc
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional
import logging

class BaseProcessManager(abc.ABC):
    """
    An abstract base class for managing external command-line processes.

    It handles the common logic for starting, stopping, and cleaning up processes
    and their configuration files, designed to be used as a context manager.
    """
    def __init__(self, vendor_path: str):
        self.vendor_path = Path(vendor_path)
        self.executable_path = self.vendor_path / self._get_executable_name()
        self.process: Optional[subprocess.Popen] = None
        self._config_file_path: Optional[str] = None

        if not self.executable_path.is_file():
            raise FileNotFoundError(f"Executable not found at: {self.executable_path}")

    @abc.abstractmethod
    def _get_executable_name(self) -> str:
        """Subclasses must implement this to return the platform-specific executable name."""
        pass

    @abc.abstractmethod
    def _create_config(self) -> None:
        """Subclasses must implement this to create the config file and set self._config_file_path."""
        pass

    @abc.abstractmethod
    def _get_start_command(self) -> List[str]:
        """Subclasses must implement this to return the full command to start the process."""
        pass

    def _cleanup_config(self) -> None:
        """Cleans up the temporary config file if it exists."""
        if self._config_file_path and os.path.exists(self._config_file_path):
            try:
                os.remove(self._config_file_path)
                logging.debug(f"Config file deleted: {self._config_file_path}")
                self._config_file_path = None
            except OSError as e:
                logging.error(f"Error removing config file {self._config_file_path}: {e}")

    def start(self) -> None:
        if self.is_running():
            logging.info(f"{self.__class__.__name__} is already running.")
            return

        self._create_config()
        command = self._get_start_command()

        logging.info(f"Starting {self.__class__.__name__} with command: {' '.join(command)}")
        try:
            self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            logging.info(f"{self.__class__.__name__} started successfully with PID: {self.process.pid}")
        except Exception as e:
            logging.error(f"Failed to start {self.__class__.__name__}: {e}")
            self.process = None
            self._cleanup_config() # Clean up if start fails

    def stop(self) -> None:
        if not self.is_running():
            return

        logging.info(f"Stopping {self.__class__.__name__} with PID: {self.process.pid}...")
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
            logging.info(f"{self.__class__.__name__} stopped.")
        except subprocess.TimeoutExpired:
            self.process.kill()
            logging.warning(f"{self.__class__.__name__} was killed forcefully.")
        finally:
            self.process = None
            self._cleanup_config()

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
