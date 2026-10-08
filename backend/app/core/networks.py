import ipaddress

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_networks(value: str) -> list[Network]:
    """Comma-separated IPs or CIDR ranges, e.g. "192.168.1.20, 10.0.0.0/24"."""
    networks = []
    for part in value.split(","):
        part = part.strip()
        if part:
            networks.append(ipaddress.ip_network(part, strict=False))
    return networks


def normalize_ip(ip: str) -> str:
    """ "::ffff:192.168.1.5" -> "192.168.1.5", so IPv4 entries in settings still match."""
    try:
        address = ipaddress.ip_address(ip.strip())
    except ValueError:
        return ip.strip()
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return str(address.ipv4_mapped)
    return str(address)


def in_networks(ip: str, networks: list[Network]) -> bool:
    try:
        address = ipaddress.ip_address(normalize_ip(ip))
    except ValueError:
        return False
    return any(address in network for network in networks)
