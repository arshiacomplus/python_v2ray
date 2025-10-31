# python_v2ray/api_client.py

import grpc
from typing import Optional, Dict

# * Import the classes we just generated from the .proto files.
# * The path is relative to the project structure we created.
from .protos.app.stats.command import command_pb2
from .protos.app.stats.command import command_pb2_grpc


class XrayApiClient:
    """
    * A gRPC client for communicating with the Xray-core's built-in API.
    * This class handles the low-level details of making RPC calls.
    """

    def __init__(self, api_address: str):
        """
        Args:
            api_address (str): The address of the Xray API, e.g., '127.0.0.1:62789'
        """
        self.api_address = api_address
        self._stub: Optional[command_pb2_grpc.StatsServiceStub] = None

    def _connect(self):
        """* Establishes a connection to the gRPC server if not already connected."""
        if self._stub is None:
            # note: Using an insecure channel as the API is only exposed locally.
            channel = grpc.insecure_channel(self.api_address)
            self._stub = command_pb2_grpc.StatsServiceStub(channel)

    def get_stats(self, tag: str, reset: bool = False) -> Optional[Dict[str, int]]:
        """
        * Fetches statistics for a specific tag (inbound or outbound).
        """
        try:
            self._connect()

            # ! We need two separate requests: one for uplink and one for downlink.
            up_request = command_pb2.GetStatsRequest(
                name=f"outbound>>>{tag}>>>traffic>>>uplink", reset=reset
            )
            up_response = self._stub.GetStats(up_request)
            uplink_value = (
                up_response.stat.value if up_response and up_response.stat else 0
            )

            down_request = command_pb2.GetStatsRequest(
                name=f"outbound>>>{tag}>>>traffic>>>downlink", reset=reset
            )
            down_response = self._stub.GetStats(down_request)
            downlink_value = (
                down_response.stat.value if down_response and down_response.stat else 0
            )

            return {"uplink": uplink_value, "downlink": downlink_value}

        except grpc.RpcError as e:
            # * This error is now expected if there's no traffic yet.
            # * We will handle it gracefully in the example script.
            if "not found" in e.details():
                return {
                    "uplink": 0,
                    "downlink": 0,
                }  # Return 0 if the stat entry doesn't exist yet
            print(f"! gRPC Error while getting stats for tag '{tag}': {e.details()}")
            return None
