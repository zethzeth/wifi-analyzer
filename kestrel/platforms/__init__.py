import sys

from kestrel.models import Connection

if sys.platform == 'darwin':
    from kestrel.platforms.macos import dns_server, gateway, link, networks
else:
    from kestrel.platforms.linux import dns_server, gateway, link, networks

__all__ = ['connection', 'dns_server', 'gateway', 'link', 'networks']


def connection() -> Connection:
    router_ip, interface = gateway()
    return Connection(router_ip, interface, dns_server(interface), link(interface))
