# python_v2ray/config_parser.py
import json
import base64
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union
import logging
import requests
from pathlib import Path


@dataclass
class ConfigParams:
    """
    * This is the universal data structure that holds all possible parameters
    * parsed from any type of config URI. It's the "lingua franca" of our library.
    * It's based on your original comprehensive dataclass.
    """

    # * Core Fields
    protocol: str
    address: str
    port: int
    tag: Optional[str] = "proxy"
    display_tag: Optional[str] = "Untitled"
    # * Common Fields (VLESS/VMess/Trojan)
    id: Optional[str] = ""
    security: Optional[str] = ""
    network: Optional[str] = "tcp"
    header_type: Optional[str] = "none"
    host: Optional[str] = ""
    path: Optional[str] = ""
    # * TLS / Reality Fields
    sni: Optional[str] = ""
    fp: Optional[str] = ""
    alpn: Optional[str] = ""
    pbk: Optional[str] = ""
    sid: Optional[str] = ""
    spx: Optional[str] = ""
    # * Protocol-Specific Fields
    flow: Optional[str] = ""  # VLESS
    encryption: Optional[str] = "none"  # VLESS
    alter_id: int = 0  # VMess
    scy: Optional[str] = "auto"  # VMess legacy security
    password: Optional[str] = ""  # Trojan, SOCKS, SS
    ss_method: Optional[str] = "chacha20-poly1305"  # ShadowSocks
    mode: Optional[str] = ""  # gRPC, etc.
    # * WireGuard Fields
    wg_secret_key: Optional[str] = ""
    wg_address: Optional[str] = "172.16.0.2/32"
    wg_reserved: Optional[str] = ""
    wg_mtu: int = 1420
    # * Hysteria Fields
    hy2_password: Optional[str] = ""
    hy2_obfs: Optional[str] = ""
    hy2_obfs_password: Optional[str] = ""
    # * Mvless Extra Fields
    mux_enabled: bool = False
    mux_concurrency: int = 8
    fragment_enabled: bool = False
    fragment_packets: Optional[str] = ""
    fragment_length: Optional[str] = ""
    fragment_interval: Optional[str] = ""


def _parse_query_params(query: str) -> Dict[str, str]:
    """
    A robust query parameter parser that correctly handles URL-encoded values.
    """
    params = {}
    if not query:
        return params
    parsed_qs = urllib.parse.parse_qs(query)
    for key, values in parsed_qs.items():
        if values:
            params[key] = values[-1]
    return params


def parse_uri(config_uri: str) -> Optional[ConfigParams]:
    """
    A heavily refactored and robust URI parser that handles non-standard formats,
    including IPv6 and URL-encoded characters in unexpected places.
    """
    try:
        uri = config_uri.strip()
        if not uri:
            return None

        protocol = uri.split("://")[0]
        if protocol not in [
            "vless",
            "mvless",
            "vmess",
            "trojan",
            "ss",
            "socks",
            "wireguard",
            "hysteria",
            "hysteria2",
            "hy2",
        ]:
            return None

        if protocol != "vmess":
            try:
                uri = urllib.parse.unquote(uri)
            except Exception:
                pass

            parsed_url = urllib.parse.urlparse(uri, scheme=protocol)

            decoded_display_tag = (
                urllib.parse.unquote(parsed_url.fragment)
                if parsed_url.fragment
                else "Untitled"
            )
            internal_safe_tag = (
                re.sub(r"[^a-zA-Z0-9_.-]", "_", decoded_display_tag) or "proxy"
            )

            common = {
                "protocol": protocol,
                "tag": internal_safe_tag,
                "display_tag": decoded_display_tag,
                "address": parsed_url.hostname or "",
                "port": parsed_url.port or 0,
            }
        else:
            main_part = uri.split("#", 1)[0]
            raw_tag_from_uri = uri.split("#", 1)[1] if "#" in uri else "Untitled"
            decoded_display_tag = urllib.parse.unquote(raw_tag_from_uri)
            internal_safe_tag = (
                re.sub(r"[^a-zA-Z0-9_.-]", "_", decoded_display_tag) or "proxy"
            )
            common = {
                "protocol": "vmess",
                "tag": internal_safe_tag,
                "display_tag": decoded_display_tag,
            }
            parsed_url = None

        parser_map = {
            "vless": _parse_vless,
            "mvless": _parse_vless,
            "vmess": _parse_vmess,
            "trojan": _parse_trojan,
            "ss": _parse_shadowsocks,
            "socks": _parse_socks,
            "wireguard": _parse_wireguard,
            "hysteria": _parse_hysteria,
            "hysteria2": _parse_hysteria,
            "hy2": _parse_hysteria,
        }
        parser = parser_map.get(protocol)
        if not parser:
            return None

        params = parser(uri, common, parsed_url)

        if not params:
            return None

        if not params.address or not params.port or params.port <= 0:
            logging.warning(
                f"Parsed config '{params.display_tag}' is missing a valid address or port. Skipping."
            )
            return None

        if protocol == "mvless":
            _parse_mvless_extensions(params, uri)

        return params

    except Exception as e:
        logging.error(
            f"CRITICAL ERROR while parsing URI '{config_uri[:50]}...': {e}",
            exc_info=False,
        )
        return None


# Note: All parser functions now accept an optional `parsed_url` object
def _parse_vless(
    uri: str, common: dict, parsed_url: Optional[urllib.parse.ParseResult]
) -> Optional[ConfigParams]:
    if not parsed_url:
        return None
    params = _parse_query_params(parsed_url.query)

    network_type = params.get("type", "tcp")
    path = params.get("path", "")
    host = params.get("host", "")
    sni = params.get("sni", host)

    if network_type == "grpc" and not path:
        path = params.get("serviceName", sni or host)
        if not path:
            logging.warning(
                f"gRPC config '{common['display_tag']}' missing serviceName/path and has no fallback SNI/Host. Skipping."
            )
            return None

    return ConfigParams(
        **common,
        id=parsed_url.username or "",
        security=params.get("security", "none"),
        network=network_type,
        header_type=params.get("headerType", "none"),
        host=host,
        path=path,
        sni=sni,
        fp=params.get("fp", ""),
        alpn=params.get("alpn", ""),
        flow=params.get("flow", ""),
        encryption=params.get("encryption", "none"),
    )


def _parse_mvless_extensions(params: ConfigParams, uri: str):
    """Parses Mux and Fragment parameters specific to the Mvless protocol and modifies the ConfigParams object."""
    try:
        query_params = _parse_query_params(urllib.parse.urlparse(uri).query)
        if "mux" in query_params and query_params["mux"].upper() == "ON":
            params.mux_enabled = True
            if "muxConcurrency" in query_params:
                try:
                    params.mux_concurrency = int(query_params["muxConcurrency"])
                except (ValueError, IndexError):
                    pass
        if (
            "packets" in query_params
            and "length" in query_params
            and "interval" in query_params
        ):
            params.fragment_enabled = True
            params.fragment_packets = query_params["packets"]
            params.fragment_length = query_params["length"]
            params.fragment_interval = query_params["interval"]
    except Exception as e:
        logging.warning(f"! Error parsing mvless extensions: {e}")


def _parse_vmess(
    uri: str, common: dict, parsed_url: Optional[urllib.parse.ParseResult]
) -> Optional[ConfigParams]:
    try:
        encoded_part = uri.replace("vmess://", "").split("#")[0]
        decoded = json.loads(base64.b64decode(encoded_part + "==").decode("utf-8"))

        display_tag = decoded.get("ps", common["display_tag"])
        common["display_tag"] = display_tag
        common["tag"] = re.sub(r"[^a-zA-Z0-9_.-]", "_", display_tag) or "proxy"

        network_type = decoded.get("net", "tcp")
        path = decoded.get("path", "")
        host = decoded.get("host", "")
        sni = decoded.get("sni", host)

        if network_type == "grpc" and not path:
            path = decoded.get("serviceName", sni or host)
            if not path:
                logging.warning(
                    f"gRPC config '{display_tag}' missing serviceName/path and has no fallback SNI/Host. Skipping."
                )
                return None

        return ConfigParams(
            **common,
            address=decoded.get("add", ""),
            port=int(decoded.get("port", 0)),
            id=decoded.get("id", ""),
            alter_id=int(decoded.get("aid", 0)),
            scy=decoded.get("scy", "auto"),
            network=network_type,
            header_type=decoded.get("type", "none"),
            host=host,
            path=path,
            security="tls" if decoded.get("tls") else "none",
            sni=sni,
        )
    except Exception as e:
        logging.error(f"Failed to parse VMess URI '{uri[:50]}...': {e}. Skipping.")
        return None


def _parse_trojan(
    uri: str, common: dict, parsed_url: Optional[urllib.parse.ParseResult]
) -> Optional[ConfigParams]:
    if not parsed_url:
        return None
    params = _parse_query_params(parsed_url.query)

    network_type = params.get("type", "tcp")
    path = params.get("path", "/")
    host = params.get("host", "")
    sni = params.get("sni", common.get("address", ""))

    if network_type == "grpc" and (not path or path == "/"):
        path = params.get("serviceName", sni or host)
        if not path:
            logging.warning(
                f"gRPC config '{common['display_tag']}' missing serviceName/path and has no fallback. Skipping."
            )
            return None

    return ConfigParams(
        **common,
        password=parsed_url.username or "",
        sni=sni,
        network=network_type,
        security=params.get("security", "tls"),
        fp=params.get("fp", ""),
        header_type=params.get("headerType", "none"),
        host=host,
        path=path,
    )


def _parse_shadowsocks(
    uri: str, common: dict, parsed_url: Optional[urllib.parse.ParseResult]
) -> Optional[ConfigParams]:
    if not parsed_url:
        return None

    auth_part = parsed_url.username or ""
    if ":" not in auth_part and parsed_url.password is None:
        try:
            decoded_auth = base64.b64decode(
                str(parsed_url.netloc.split("@")[0]) + "=="
            ).decode("utf-8")
            if ":" in decoded_auth:
                method, password = decoded_auth.split(":", 1)
                return ConfigParams(**common, ss_method=method, password=password)
        except Exception:
            pass

    if ":" in auth_part:
        method, password = auth_part.split(":", 1)
        return ConfigParams(**common, ss_method=method, password=password)
    else:
        params = _parse_query_params(parsed_url.query)
        method = params.get("method", "chacha20-poly1305")
        return ConfigParams(**common, ss_method=method, password=auth_part)


def _parse_socks(
    uri: str, common: dict, parsed_url: Optional[urllib.parse.ParseResult]
) -> Optional[ConfigParams]:
    if not parsed_url:
        return None
    return ConfigParams(**common, id=parsed_url.username, password=parsed_url.password)


def _parse_wireguard(
    uri: str, common: dict, parsed_url: Optional[urllib.parse.ParseResult]
) -> Optional[ConfigParams]:
    if not parsed_url:
        return None
    params = _parse_query_params(parsed_url.query)

    wg_address_raw = params.get("address", "172.16.0.2/32")
    wg_address_clean = [addr.strip() for addr in wg_address_raw.split(",")]

    return ConfigParams(
        **common,
        wg_secret_key=parsed_url.username or "",
        wg_address=",".join(wg_address_clean),
        pbk=params.get("publicKey", ""),
        wg_reserved=params.get("reserved", ""),
        wg_mtu=int(params.get("mtu", 1420)),
    )


def _parse_hysteria(
    uri: str, common: dict, parsed_url: Optional[urllib.parse.ParseResult]
) -> Optional[ConfigParams]:
    if not parsed_url:
        return None
    params = _parse_query_params(parsed_url.query)
    return ConfigParams(
        **common,
        hy2_password=parsed_url.username or "",
        security="tls",
        sni=params.get("sni", common.get("address", "")),
        alpn=params.get("alpn"),
        hy2_obfs=params.get("obfs"),
        hy2_obfs_password=params.get("obfs-password"),
    )


class XrayConfigBuilder:
    def __init__(self):
        self.config: Dict[str, Any] = {
            "log": {"loglevel": "warning"},
            "stats": {},
            "policy": {
                "system": {
                    "statsInboundUplink": True,
                    "statsInboundDownlink": True,
                    "statsOutboundUplink": True,
                    "statsOutboundDownlink": True,
                },
                "levels": {"0": {"statsuserUplink": True, "statsuserDownlink": True}},
            },
            "inbounds": [],
            "outbounds": [],
            "routing": {"rules": []},
        }
        self.warp_outbound_tag: Optional[str] = None

    def add_inbound(self, inbound_config: Dict[str, Any]):
        self.config["inbounds"].append(inbound_config)
        return self

    def add_outbound(self, outbound_config: Dict[str, Any]):
        self.config["outbounds"].append(outbound_config)
        return self

    def add_warp_outbound(self, warp_params: ConfigParams, tag: str = "warp-out"):
        """
        Builds and adds a WireGuard (WARP) outbound to the configuration.
        This outbound will be used as the final exit point for other proxies.
        """
        if self.warp_outbound_tag:
            logging.warning(
                f"A WARP outbound with tag '{self.warp_outbound_tag}' already exists. Skipping."
            )
            return self
        original_tag = warp_params.tag
        warp_params.tag = tag
        warp_outbound = self.build_outbound_from_params(warp_params)
        warp_params.tag = original_tag
        if not warp_outbound or warp_outbound.get("protocol") != "wireguard":
            raise ValueError(
                "The provided warp_config is not a valid WireGuard configuration."
            )
        self.add_outbound(warp_outbound)
        self.warp_outbound_tag = tag
        logging.info(f"WARP outbound '{tag}' has been configured as the exit proxy.")
        return self

    def build_outbound_from_params(
        self,
        params: ConfigParams,
        explicit_tag: Optional[str] = None,
        fragment_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        * The main engine. Converts ConfigParams into a complete Xray outbound dictionary.
        * Now correctly maps short protocol names to Xray's official protocol names.
        """
        protocol_map = {
            "vless": "vless",
            "mvless": "vless",
            "vmess": "vmess",
            "trojan": "trojan",
            "ss": "shadowsocks",
            "socks": "socks",
            "wireguard": "wireguard",
        }
        xray_protocol_name = protocol_map.get(params.protocol)
        if not xray_protocol_name:
            return None  # Not for Xray

        stream_settings = self._build_stream_settings(params, **kwargs)
        protocol_settings = self._build_protocol_settings(params)

        final_outbound_tag = explicit_tag if explicit_tag is not None else params.tag
        outbound = {
            "tag": final_outbound_tag,
            "protocol": xray_protocol_name,
            "settings": protocol_settings,
            "streamSettings": stream_settings,
        }

        if params.protocol == "mvless" and params.mux_enabled:
            outbound["mux"] = {
                "enabled": True,
                "concurrency": params.mux_concurrency,
            }

        if self.warp_outbound_tag and params.tag != self.warp_outbound_tag:
            if "sockopt" not in outbound["streamSettings"]:
                outbound["streamSettings"]["sockopt"] = {}
            outbound["streamSettings"]["sockopt"][
                "dialerProxy"
            ] = self.warp_outbound_tag
            logging.debug(
                f"Chaining outbound '{params.tag}' through '{self.warp_outbound_tag}'."
            )

        return self._remove_empty_values(outbound)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.config, indent=indent, ensure_ascii=False)

    def _build_stream_settings(self, params: ConfigParams, **kwargs) -> Dict[str, Any]:
        stream_settings = {"network": params.network}

        if params.security in ["tls", "reality"]:
            stream_settings["security"] = params.security
            security_settings = {
                "allowInsecure": kwargs.get("allow_insecure", False),
                "serverName": params.sni,
                "fingerprint": params.fp,
            }
            if params.alpn:
                security_settings["alpn"] = [
                    val.strip() for val in params.alpn.split(",")
                ]

            if params.security == "reality":
                security_settings.update(
                    {
                        "publicKey": params.pbk,
                        "shortId": params.sid,
                        "spiderX": params.spx,
                    }
                )
                stream_settings["realitySettings"] = security_settings
            else:
                stream_settings["tlsSettings"] = security_settings

        header_config = (
            {"type": params.header_type} if params.header_type != "none" else None
        )
        host_for_header = params.host or params.sni

        network_settings = {}
        if params.network == "tcp" and header_config:
            network_settings = {"tcpSettings": {"header": header_config}}
        elif params.network == "kcp" and header_config:
            network_settings = {
                "kcpSettings": {"header": header_config, "seed": params.path}
            }
        elif params.network == "ws":
            network_settings = {
                "wsSettings": {
                    "path": params.path,
                    "headers": {"Host": host_for_header},
                }
            }
        elif params.network == "h2":
            network_settings = {
                "httpSettings": {"host": [host_for_header], "path": params.path}
            }
        elif params.network == "quic":
            network_settings = {
                "quicSettings": {
                    "security": params.host,
                    "key": params.path,
                    "header": header_config,
                }
            }
        elif params.network == "grpc":
            network_settings = {
                "grpcSettings": {
                    "serviceName": params.path,
                    "multiMode": (params.mode == "multi"),
                }
            }

        stream_settings.update(network_settings)

        if params.protocol == "mvless" and params.fragment_enabled:
            stream_settings["sockopt"] = {"dialerProxy": "fragment_tag"}

        return stream_settings

    def add_fragment_outbound(self, fragment_config: Dict[str, Any]):
        """
        * Adds the special 'fragment' outbound to the configuration.
        * This outbound is used by other outbounds via sockopt.
        """
        defaults = {"packets": "tlshello", "length": "10-20", "interval": "10-20"}
        final_settings = {**defaults, **fragment_config}
        fragment_outbound = {
            "protocol": "freedom",
            "tag": "fragment_tag",
            "settings": {"fragment": final_settings},
        }
        self.add_outbound(fragment_outbound)
        return self

    def _build_protocol_settings(self, params: ConfigParams) -> Dict[str, Any]:
        level = 0
        protocol = params.protocol
        if protocol in ["vless", "mvless"]:
            return {
                "vnext": [
                    {
                        "address": params.address,
                        "port": params.port,
                        "users": [
                            {
                                "id": params.id,
                                "flow": params.flow,
                                "encryption": "none",
                                "level": level,
                            }
                        ],
                    }
                ]
            }
        elif protocol == "vmess":
            return {
                "vnext": [
                    {
                        "address": params.address,
                        "port": params.port,
                        "users": [
                            {
                                "id": params.id,
                                "alterId": params.alter_id,
                                "security": params.scy,
                                "level": level,
                            }
                        ],
                    }
                ]
            }
        elif protocol == "trojan":
            return {
                "servers": [
                    {
                        "address": params.address,
                        "port": params.port,
                        "password": params.password,
                        "level": level,
                    }
                ]
            }
        elif protocol == "ss":
            return {
                "servers": [
                    {
                        "address": params.address,
                        "port": params.port,
                        "password": params.password,
                        "method": params.ss_method,
                        "level": level,
                    }
                ]
            }
        elif protocol == "wireguard":
            reserved = (
                [int(i.strip()) for i in params.wg_reserved.split(",")]
                if params.wg_reserved
                else []
            )
            return {
                "secretKey": params.wg_secret_key,
                "address": params.wg_address.split(","),
                "peers": [
                    {
                        "publicKey": params.pbk,
                        "endpoint": f"{params.address}:{params.port}",
                    }
                ],
                "mtu": params.wg_mtu,
                "reserved": reserved,
            }
        elif protocol == "socks":
            server = {"address": params.address, "port": params.port, "level": level}
            if params.id:
                server["users"] = [{"user": params.id, "pass": params.password or ""}]
            return {"servers": [server]}
        return {}

    def _remove_empty_values(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: v
                for k, v in ((k, self._remove_empty_values(v)) for k, v in data.items())
                if v is not None and v not in ["", [], {}]
            }
        if isinstance(data, list):
            return [
                v
                for v in (self._remove_empty_values(item) for item in data)
                if v is not None and v not in ["", [], {}]
            ]
        return data

    def enable_api(self, port: int = 62789, listen: str = "127.0.0.1"):
        """
        * Adds the necessary 'api' and 'stats' sections to the config
        * to enable the gRPC StatsService.
        """
        api_tag = "api"
        self.config["api"] = {
            "tag": api_tag,
            "services": ["StatsService"],
        }
        self.config["routing"]["rules"].insert(
            0, {"type": "field", "inboundTag": [api_tag], "outboundTag": api_tag}
        )
        self.add_inbound(
            {
                "tag": api_tag,
                "port": port,
                "listen": listen,
                "protocol": "dokodemo-door",
                "settings": {"address": listen, "userLevel": 0},
            }
        )
        return self


def fetch_from_subscription(
    url: str, timeout: int = 10, max_configs: Optional[int] = None
) -> List[str]:
    """
    Fetches configuration URIs from a subscription link.
    It can now limit the number of configs returned.
    """
    try:
        logging.info(f"Fetching subscription from: {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        content = response.content
        try:
            decoded_content = base64.b64decode(content).decode("utf-8")
        except (base64.binascii.Error, UnicodeDecodeError):
            decoded_content = content.decode("utf-8")
        uris = [uri.strip() for uri in decoded_content.splitlines() if uri.strip()]
        if max_configs and max_configs > 0:
            logging.info(f"Limiting configs to a maximum of {max_configs}.")
            uris = uris[:max_configs]
        logging.info(f"Successfully processed {len(uris)} configs from subscription.")
        return uris
    except Exception as e:
        logging.error(f"Failed to fetch or process subscription: {e}")
        return []


def load_configs(
    source: Union[str, List[str], Path],
    is_subscription: bool = False,
    max_configs: Optional[int] = None,
) -> List[ConfigParams]:
    """
    A universal config loader that now supports limiting the number of configs
    fetched from a subscription.
    """
    raw_uris: List[str] = []
    if isinstance(source, str) and source.startswith(("http", "https")):
        if is_subscription:
            raw_uris = fetch_from_subscription(source, max_configs=max_configs)
        else:
            raw_uris = [source]
    elif isinstance(source, list):
        raw_uris = source
    elif isinstance(source, Path) and source.is_file():
        content = source.read_text("utf-8").strip()
        if is_subscription or content.startswith(("http", "https")):
            raw_uris = fetch_from_subscription(content, max_configs=max_configs)
        else:
            raw_uris = [line.strip() for line in content.splitlines() if line.strip()]
    else:
        raw_uris = [str(source)]

    if (
        isinstance(source, (Path, list))
        and not is_subscription
        and max_configs
        and max_configs > 0
    ):
        logging.info(f"Limiting configs from file/list to a maximum of {max_configs}.")
        raw_uris = raw_uris[:max_configs]

    parsed_configs = [p for p in (parse_uri(uri) for uri in raw_uris) if p]
    return parsed_configs


def deduplicate_configs(configs: List[ConfigParams]) -> List[ConfigParams]:
    """
    Removes duplicate configurations from a list based on their core properties,
    ignoring the 'tag'.
    The first occurrence of a unique configuration is kept.
    Args:
        configs: A list of ConfigParams objects.
    Returns:
        A list of unique ConfigParams objects.
    """
    unique_configs = {}
    for config in configs:
        key_parts = (
            config.protocol,
            config.address,
            config.port,
            config.id,
            config.password,
            config.wg_secret_key,
            config.hy2_password,
            config.path,
            config.sni,
            config.host,
        )
        key = tuple(str(p) for p in key_parts)
        if key not in unique_configs:
            unique_configs[key] = config

    deduplicated_list = list(unique_configs.values())
    if len(configs) > len(deduplicated_list):
        logging.info(
            f"Removed {len(configs) - len(deduplicated_list)} duplicate configurations."
        )

    return deduplicated_list
