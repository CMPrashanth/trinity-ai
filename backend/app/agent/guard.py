"""Scope and safety guardrails for Trinity agent command execution."""

from __future__ import annotations

import ipaddress
import re
from typing import Iterable, Tuple

from ..config import settings

# Accept IPv4 addresses optionally suffixed with a port (e.g., 10.0.0.5:22)
_IP_TARGET = re.compile(r"^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})(?::\d{1,5})?$")


def _parse_target_ip(target: str) -> str:
    """Extract and validate the IPv4 portion of a scan target string."""

    candidate = target.strip()
    match = _IP_TARGET.match(candidate)
    if not match:
        raise ValueError("Target must be an IPv4 address optionally followed by a port (e.g., 192.168.1.10 or 192.168.1.10:443).")

    ip_literal = match.group("ip")
    ipaddress.IPv4Address(ip_literal)  # raises if invalid octets
    return ip_literal


def validate_scope(target: str, subnet: str | None = None) -> Tuple[bool, str]:
    """Return whether the supplied target lives inside the allowed subnet."""

    network_cidr = subnet or settings.SCOPE_SUBNET
    network = ipaddress.IPv4Network(network_cidr, strict=False)

    try:
        ip_literal = _parse_target_ip(target)
    except ValueError as exc:  # malformed address
        return False, str(exc)

    if ipaddress.IPv4Address(ip_literal) in network:
        return True, "target within scope"

    return False, f"Target {ip_literal} not in authorised subnet {network_cidr}."


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
