"""Scope and safety guardrails for Trinity agent command execution."""

from __future__ import annotations

import ipaddress
import re
from typing import Iterable, Optional, Tuple, Union

from ..config import settings

# Accept IPv4 addresses optionally suffixed with a port (e.g., 10.0.0.5:22)
_IP_TARGET = re.compile(r"^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})(?::(?P<port>\d{1,5}))?$")


ParsedTarget = Union[ipaddress.IPv4Address, ipaddress.IPv4Network]


def _parse_target(target: str) -> ParsedTarget:
    """Parse a target as either an IPv4 host or an IPv4 CIDR network."""

    candidate = target.strip()

    match = _IP_TARGET.match(candidate)
    if match:
        ip_literal = match.group("ip")
        ip = ipaddress.IPv4Address(ip_literal)  # raises if invalid octets
        return ip

    # Support CIDR notation (e.g., 192.168.1.0/24) - no port supported here.
    try:
        return ipaddress.IPv4Network(candidate, strict=False)
    except ValueError:
        raise ValueError(
            "Target must be an IPv4 address optionally followed by a port (e.g., 192.168.1.10 or 192.168.1.10:443) "
            "or an IPv4 CIDR subnet (e.g., 192.168.1.0/24)."
        )


def split_target_host_port(target: str) -> tuple[str, Optional[int]]:
    """Split an IPv4 target into host + optional port.

    Examples:
    - "10.10.0.11" -> ("10.10.0.11", None)
    - "10.10.0.11:3000" -> ("10.10.0.11", 3000)
    - "10.10.0.0/24" -> ("10.10.0.0/24", None)
    """

    candidate = (target or "").strip()
    match = _IP_TARGET.match(candidate)
    if match:
        ip_literal = match.group("ip")
        port_literal = match.group("port")
        if port_literal:
            try:
                return ip_literal, int(port_literal)
            except ValueError:
                return ip_literal, None
        return ip_literal, None
    return candidate, None


def validate_scope(target: str, subnet: str | None = None) -> Tuple[bool, str]:
    """Return whether the supplied target lives inside the allowed subnet."""

    network_cidr = subnet or settings.SCOPE_SUBNET
    network = ipaddress.IPv4Network(network_cidr, strict=False)

    try:
        parsed = _parse_target(target)
    except ValueError as exc:  # malformed address
        return False, str(exc)

    if isinstance(parsed, ipaddress.IPv4Address):
        if parsed in network:
            return True, "target within scope"
        return False, f"Target {parsed} not in authorised subnet {network_cidr}."

    # IPv4Network target
    if parsed.subnet_of(network):
        return True, "target subnet within scope"

    return False, f"Target subnet {parsed} not within authorised subnet {network_cidr}."


def validate_safety(command: str, blocked_tokens: Iterable[str] | None = None) -> Tuple[bool, str]:
    """Check the command string for disallowed substrings."""

    candidates = blocked_tokens or settings.BLOCKED_COMMANDS
    normalised = command.lower()

    for token in candidates:
        needle = token.lower()
        if not needle:
            continue
        if needle in normalised:
            return False, f"Command contains blocked token: {token}"

    return True, "command approved"
