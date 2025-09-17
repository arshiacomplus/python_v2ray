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
# ! =======================================================================
# ! === STEP 1: A UNIVERSAL DATA MODEL FOR ALL CONFIGS                  ===
# ! =======================================================================
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
    flow: Optional[str] = ""                 # VLESS
    encryption: Optional[str] = "none"       # VLESS
    alter_id: int = 0                        # VMess
    scy: Optional[str] = "auto"              # VMess legacy security
    password: Optional[str] = ""             # Trojan, SOCKS, SS
    ss_method: Optional[str] = "chacha20-poly1305" # ShadowSocks
    mode: Optional[str] = ""                 # gRPC, etc.
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
    A robust query parameter parser that correctly handles URL-encoded values
    without converting '+' to a space, which is critical for Base64 keys.
    """
    params = {}
    if not query:
        return params
    for pair in query.split('&'):
        if '=' in pair:
            key, value = pair.split('=', 1)
            params[urllib.parse.unquote(key)] = urllib.parse.unquote(value)
    return params
def parse_uri(config_uri: str) -> Optional[ConfigParams]:
    """
    * This is the main parsing engine. It delegates the parsing to
    * protocol-specific helper functions and validates the core components.
    """
    try:
        uri = urllib.parse.unquote(config_uri).strip()
        raw_tag = uri.split("#", 1)[1] if len(uri.split("#", 1)) > 1 else "Untitled"
        tag = re.sub(r'[^a-zA-Z0-9_.-]', '_', raw_tag) or "proxy"
        protocol = uri.split("://")[0]
        if "@" not in uri or ":" not in uri.split("@")[-1]:
            if protocol != 'vmess':
                print(f"! Invalid URI structure (missing @ or :). Skipping: {uri[:40]}...")
                return None
        parser_map = {
            "vless": _parse_vless, "mvless": _parse_vless, "vmess": _parse_vmess, "trojan": _parse_trojan,
            "ss": _parse_shadowsocks, "socks": _parse_socks, "wireguard": _parse_wireguard,
            "hysteria": _parse_hysteria, "hysteria2": _parse_hysteria, "hy2": _parse_hysteria,
        }
        parser = parser_map.get(protocol)
        if not parser:
            print(f"note: Unsupported protocol found: {protocol}")
            return None
        common = {"protocol": protocol, "tag": tag, "address": "", "port": 0}
        match = re.search(r"@([^:]+):(\d+)", uri.split("?")[0])
        if match:
            common["address"] = match.group(1)
            common["port"] = int(match.group(2))
        elif protocol != 'vmess':
            print(f"! Could not extract host/port from URI. Skipping: {uri[:40]}...")
            return None
        params = parser(uri.strip(), common)
        if protocol == "mvless" and params:
            _parse_mvless_extensions(params, uri)
        return params
    except Exception as e:
        print(f"! CRITICAL ERROR while parsing URI '{config_uri[:30]}...': {e}")
        return None
def _parse_vless(uri: str, common: dict) -> ConfigParams:
    parsed_url = urllib.parse.urlparse(uri)
    params = _parse_query_params(parsed_url.query)
    return ConfigParams(
        **common, id=parsed_url.username,
        security=params.get("security", ""), network=params.get("type", "tcp"),
        header_type=params.get("headerType", "none"), host=params.get("host", ""),
        path=params.get("path", "/"), sni=params.get("sni", params.get("host", "")),
        fp=params.get("fp", ""), alpn=params.get("alpn", ""), flow=params.get("flow", ""),
        encryption=params.get("encryption", "none"),
    )
def _parse_mvless_extensions(params: ConfigParams, uri: str):
    """Parses Mux and Fragment parameters specific to the Mvless protocol and modifies the ConfigParams object."""
    try:
        query_params = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)
        if 'mux' in query_params and query_params['mux'][0].upper() == 'ON':
            params.mux_enabled = True
            if 'muxConcurrency' in query_params:
                try:
                    params.mux_concurrency = int(query_params['muxConcurrency'][0])
                except (ValueError, IndexError):
                    pass
        if 'packets' in query_params and 'length' in query_params and 'interval' in query_params:
            params.fragment_enabled = True
            params.fragment_packets = query_params['packets'][0]
            params.fragment_length = query_params['length'][0]
            params.fragment_interval = query_params['interval'][0]
    except Exception as e:
        print(f"! Error parsing mvless extensions: {e}")
def _parse_vmess(uri: str, common: dict) -> ConfigParams:
    encoded_part = uri.replace("vmess://", "")
    decoded = json.loads(base64.b64decode(encoded_part + "==").decode("utf-8"))
    return ConfigParams(
        protocol="vmess", tag=decoded.get("ps", common['tag']),
        address=decoded.get("add", ""), port=int(decoded.get("port", 0)),
        id=decoded.get("id", ""), alter_id=int(decoded.get("aid", 0)),
        scy=decoded.get("scy", "auto"), network=decoded.get("net", "tcp"),
        header_type=decoded.get("type", "none"), host=decoded.get("host", ""),
        path=decoded.get("path", "/"), security="tls" if decoded.get("tls") else "",
        sni=decoded.get("sni", ""),
    )
def _parse_trojan(uri: str, common: dict) -> ConfigParams:
    parsed_url = urllib.parse.urlparse(uri)
    params = _parse_query_params(parsed_url.query)
    return ConfigParams(
        **common, password=parsed_url.username,
        sni=params.get("sni", common['address']), network=params.get("type", "tcp"),
        security=params.get("security", "tls"), fp=params.get("fp", ""),
        header_type=params.get("headerType", "none"), host=params.get("host", ""),
        path=params.get("path", "/"),
    )
def _parse_shadowsocks(uri: str, common: dict) -> ConfigParams:
    main_part = uri.split("#")[0].replace("ss://", "")
    if "@" not in main_part:
        # Legacy format: base64(method:password@server:port)
        decoded = base64.b64decode(main_part + "==").decode("utf-8")
        main_part = decoded
    auth_part, server_part = main_part.split("@")
    common['address'], port_str = server_part.split(":")
    common['port'] = int(port_str)
    try: # SIP002 format: base64(method:password)
        decoded_auth = base64.b64decode(auth_part + "==").decode("utf-8")
        method, password = decoded_auth.split(":", 1)
    except: # Legacy format: method:password
        method, password = urllib.parse.unquote(auth_part).split(":", 1)
    return ConfigParams(**common, ss_method=method, password=password)
def _parse_socks(uri: str, common: dict) -> ConfigParams:
    parsed_url = urllib.parse.urlparse(uri)
    return ConfigParams(**common, id=parsed_url.username, password=parsed_url.password)
def _parse_wireguard(uri: str, common: dict) -> ConfigParams:
    try:
        main_part = uri.split("://", 1)[1]
        secret_key, _ = main_part.split("@", 1)
        query_string = uri.split("?", 1)[1].split("#", 1)[0] if "?" in uri else ""
        params = _parse_query_params(query_string)
        wg_address_raw = params.get("address", "172.16.0.2/32")
        wg_address_clean = wg_address_raw.replace('+', ',')
        # ---------------------
        return ConfigParams(
            **common,
            wg_secret_key=secret_key,
            wg_address=wg_address_clean,
            pbk=params.get("publicKey", ""),
            wg_reserved=params.get("reserved", ""),
            wg_mtu=int(params.get("mtu", 1420))
        )
    except Exception as e:
        logging.error(f"Error manually parsing WireGuard URI: {e}")
        return None
def _parse_hysteria(uri: str, common: dict) -> ConfigParams:
    params = _parse_query_params(urllib.parse.urlparse(uri).query)
    password = urllib.parse.urlparse(uri).username
    return ConfigParams(
        **common,
        hy2_password=password,
        security="tls",
        sni=params.get("sni", common['address']),
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
                    "statsOutboundDownlink": True
                },
                "levels": {
                    "0": {
                        "statsuserUplink": True,
                        "statsuserDownlink": True
                    }
                }
            },
            "inbounds": [],
            "outbounds": [],
            "routing": {
                "rules": []
            }
        }
        self.warp_outbound_tag: Optional[str] = None
    def add_inbound(self, inbound_config: Dict[str, Any]):
        self.config["inbounds"].append(inbound_config); return self
    def add_outbound(self, outbound_config: Dict[str, Any]):
        self.config["outbounds"].append(outbound_config); return self
    def add_warp_outbound(self, warp_params: ConfigParams, tag: str = "warp-out"):
        """
        Builds and adds a WireGuard (WARP) outbound to the configuration.
        This outbound will be used as the final exit point for other proxies.
        """
        if self.warp_outbound_tag:
            logging.warning(f"A WARP outbound with tag '{self.warp_outbound_tag}' already exists. Skipping.")
            return self
        original_tag = warp_params.tag
        warp_params.tag = tag
        warp_outbound = self.build_outbound_from_params(warp_params)
        warp_params.tag = original_tag
        if not warp_outbound or warp_outbound.get("protocol") != "wireguard":
            raise ValueError("The provided warp_config is not a valid WireGuard configuration.")
        self.add_outbound(warp_outbound)
        self.warp_outbound_tag = tag
        logging.info(f"WARP outbound '{tag}' has been configured as the exit proxy.")
        return self
    def build_outbound_from_params(self, params: ConfigParams, fragment_config: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        * The main engine. Converts ConfigParams into a complete Xray outbound dictionary.
        * Now correctly maps short protocol names to Xray's official protocol names.
        """
        protocol_map = {
            "vless": "vless",
            "mvless" : "mvless",
            "vmess": "vmess",
            "trojan": "trojan",
            "ss": "shadowsocks",
            "socks": "socks",
            "wireguard": "wireguard",
        }
        xray_protocol_name = protocol_map.get(params.protocol)
        if not xray_protocol_name:
            # This protocol is not meant for Xray (like Hysteria)
            return None
        use_fragment = fragment_config is not None
        stream_settings = self._build_stream_settings(params, fragment=use_fragment, **kwargs)
        protocol_settings = self._build_protocol_settings(params)
        if params.protocol == "mvless" and params.mux_enabled:
            try:
                outbound["mux"] = {"enabled": True  if  outbound["mux"].upper() == "ON" else False , "concurrency": params.mux_concurrency}
            except Exception:
                print("! No mux found in mvless")
        outbound = {
            "tag": params.tag,
            "protocol": xray_protocol_name, # ! Use the correct, full protocol name
            "settings": protocol_settings,
            "streamSettings": stream_settings
        }
        if self.warp_outbound_tag and params.tag != self.warp_outbound_tag:
            if "streamSettings" not in outbound:
                outbound["streamSettings"] = {}
            if "sockopt" not in outbound["streamSettings"]:
                outbound["streamSettings"]["sockopt"] = {}
            outbound["streamSettings"]["sockopt"]["dialerProxy"] = self.warp_outbound_tag
            logging.debug(f"Chaining outbound '{params.tag}' through '{self.warp_outbound_tag}'.")
        return self._remove_empty_values(outbound)
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.config, indent=indent, ensure_ascii=False)
    def _build_stream_settings(self, params: ConfigParams, **kwargs) -> Dict[str, Any]:
        stream_settings = {"network": params.network}
        if params.security in ["tls", "reality"]:
            stream_settings["security"] = params.security
            security_settings = {"allowInsecure": kwargs.get("allow_insecure", False), "serverName": params.sni, "fingerprint": params.fp}
            if params.alpn: security_settings["alpn"] = params.alpn.split(',')
            if params.security == "reality":
                security_settings.update({"publicKey": params.pbk, "shortId": params.sid, "spiderX": params.spx})
                stream_settings["realitySettings"] = security_settings
            else:
                stream_settings["tlsSettings"] = security_settings
        header_config = {"type": params.header_type if params.header_type else "none"}
        host_for_header = params.host if params.host else params.sni
        network_map = {
            "tcp":  {"tcpSettings":  {"header": header_config}},
            "kcp":  {"kcpSettings":  {"header": header_config, "seed": params.path}},
            "ws":   {"wsSettings":   {"path": params.path, "headers": {"Host": host_for_header}}},
            "httpupgrade": {"httpupgradeSettings":{"host": [host_for_header], "path": params.path}},
            "xhttp": {"xhttpSettings":{"host": [host_for_header], "path": params.path}},
            "splithttp":  {"splithttpSettings":{"host": [host_for_header], "path": params.path}},
            "h2":   {"httpSettings": {"host": [host_for_header], "path": params.path}},
            "quic": {"quicSettings": {"security": params.host, "key": params.path, "header": header_config}},
            "grpc": {"grpcSettings": {"serviceName": params.path, "multiMode": (params.mode == "multi")}},
        }
        stream_settings.update(network_map.get(params.network, {}))
        if params.protocol == "mvless" and params.fragment_enabled:
            stream_settings["fragment"] = {
                "packets": params.fragment_packets,
                "length": params.fragment_length,
                "interval": params.fragment_interval
            }
        if kwargs.get("fragment_config") and not params.fragment_enabled:
            stream_settings["sockopt"] = {"dialerProxy": "fragment"}
        return stream_settings
    def add_fragment_outbound(self, fragment_config: Dict[str, Any]):
        """
        * Adds the special 'fragment' outbound to the configuration.
        * This outbound is used by other outbounds via sockopt.
        """
        defaults = {
            "packets": "tlshello",
            "length": "10-20",
            "interval": "10-20"
        }
        final_settings = {**defaults, **fragment_config}
        fragment_outbound = {
            "protocol": "freedom",
            "tag": "fragment",
            "settings": {
                "fragment": final_settings
            }
        }
        self.add_outbound(fragment_outbound)
        return self
    def _build_protocol_settings(self, params: ConfigParams) -> Dict[str, Any]:
        level = 0
        protocol = params.protocol
        if protocol in ["vless", "mvless"]:
            settings = {"vnext": [{"address": params.address, "port": params.port, "users": [{"id": params.id, "flow": params.flow, "encryption": "none", "level": level}]}]}
            if protocol == "mvless" and params.fragment_enabled:
                pass
            return settings
        elif protocol == "vmess": return {"vnext": [{"address": params.address, "port": params.port, "users": [{"id": params.id, "alterId": params.alter_id, "security": params.scy, "level": level}]}]}
        elif protocol == "trojan": return {"servers": [{"address": params.address, "port": params.port, "password": params.password, "level": level}]}
        elif protocol == "ss":
            return {"servers": [{"address": params.address, "port": params.port, "password": params.password, "method": params.ss_method, "level": level}]}
        elif protocol == "wireguard":
            reserved = [int(i.strip()) for i in params.wg_reserved.split(',')] if params.wg_reserved else []
            return {"secretKey": params.wg_secret_key, "address": params.wg_address.split(','), "peers": [{"publicKey": params.pbk, "endpoint": f"{params.address}:{params.port}"}], "mtu": params.wg_mtu, "reserved": reserved}
        elif protocol in ["hysteria", "hysteria2"]:
            # note: Creates a SOCKS outbound to point to an external Hysteria client
            return {"servers": [{"address": "127.0.0.1", "port": params.port}]} # Port should be local port of Hy2 client
        return {}
    def _remove_empty_values(self, data: Any) -> Any:
        if isinstance(data, dict): return {k: v for k, v in ((k, self._remove_empty_values(v)) for k, v in data.items()) if v not in [None, "", [], {}]}
        if isinstance(data, list): return [v for v in (self._remove_empty_values(item) for item in data) if v not in [None, "", [], {}]]
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
        # self.config["stats"] = {} # ! Remove this line, it's now in __init__
        self.config["routing"]["rules"].insert(0, {
            "type": "field",
            "inboundTag": [api_tag],
            "outboundTag": api_tag
        })
        self.add_inbound({
            "tag": api_tag,
            "port": port,
            "listen": listen,
            "protocol": "dokodemo-door",
            "settings": {
                "address": listen,
                "userLevel": 0
            }
        })
        return self
def fetch_from_subscription(url: str, timeout: int = 10) -> List[str]:
    """
    Fetches configuration URIs from a subscription link.
    It intelligently handles both Base64 encoded and plain text content.
    It also handles missing padding for Base64.
    """
    try:
        logging.info(f"Fetching subscription from: {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        content = response.content
        try:
            missing_padding = len(content) % 4
            if missing_padding:
                content += b'=' * (4 - missing_padding)
            decoded_bytes = base64.b64decode(content)
            decoded_content = decoded_bytes.decode('utf-8')
            logging.info("Subscription content successfully decoded as Base64.")
        except (base64.binascii.Error, UnicodeDecodeError):
            logging.warning("Failed to decode as Base64. Treating content as plain text.")
            decoded_content = content.decode('utf-8')
        uris = [uri.strip() for uri in decoded_content.splitlines() if uri.strip()]
        logging.info(f"Successfully processed {len(uris)} configs from subscription.")
        return uris
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch subscription link: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    return []
def load_configs(
    source: Union[str, List[str], Path],
    is_subscription: bool = False
) -> List[ConfigParams]:
    """
    A universal config loader that handles different sources and robustly
    returns a list of parsed configurations.
    """
    raw_uris: List[str] = []
    if isinstance(source, str) and source.startswith(('http://', 'https://')):
        if is_subscription:
            raw_uris = fetch_from_subscription(source)
        else:
            raw_uris = [source]
    elif isinstance(source, list):
        raw_uris = source
    elif isinstance(source, Path) and source.is_file():
        logging.info(f"Loading configs from file: {source}")
        content = source.read_text('utf-8').strip()
        if is_subscription:
            raw_uris = fetch_from_subscription(content)
        else:
            raw_uris = [line.strip() for line in content.splitlines() if line.strip()]
    else:
        logging.error(f"Unsupported source type or invalid path: {source}")
        return []
    raw_uris = list(raw_uris)
    parsed_configs = [p for p in (parse_uri(uri) for uri in raw_uris) if p]
    return list(parsed_configs)
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
        if config.protocol == "vmess":
            key = (config.protocol, config.address, config.port, config.id)
        else:
            key_parts = (
                config.protocol,
                config.address,
                config.port,
                config.id,
                config.password,
                config.wg_secret_key
            )
            key = tuple(sorted(str(p) for p in key_parts))
        if key not in unique_configs:
            unique_configs[key] = config
    deduplicated_list = list(unique_configs.values())
    if len(configs) > len(deduplicated_list):
        logging.info(f"Removed {len(configs) - len(deduplicated_list)} duplicate configurations.")
    return deduplicated_list
