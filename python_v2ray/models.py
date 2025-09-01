# python_v2ray/models.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

# note: We'll use dataclasses to create structured, type-hinted models.
# note: This makes the code much cleaner and easier to work with.

@dataclass
class StreamSettings:
    """ * Models the streamSettings object for an outbound. """
    network: Optional[str] = "tcp"
    security: Optional[str] = ""
    # todo: Add specific settings for wsSettings, grpcSettings, etc. as needed.
    # For now, we'll use a flexible dictionary.
    extra_settings: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Outbound:
    """ * Represents a single outbound configuration. """
    tag: str
    protocol: str
    settings: Dict[str, Any]
    stream_settings: Optional[StreamSettings] = None
    mux: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """ * Converts the dataclass to a dictionary ready for JSON. """
        data = {
            "tag": self.tag,
            "protocol": self.protocol,
            "settings": self.settings,
        }
        if self.stream_settings:
            # fixme: This needs to be expanded to handle all stream types correctly.
            stream_dict = {
                "network": self.stream_settings.network,
                "security": self.stream_settings.security,
            }
            # Merge extra settings like wsSettings, grpcSettings
            stream_dict.update(self.stream_settings.extra_settings)
            data["streamSettings"] = stream_dict

        if self.mux:
            data["mux"] = self.mux

        return data