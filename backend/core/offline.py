"""Simulated offline mode for demos/tests: refuse every outbound (non-loopback) connection and DNS lookup, so each
network call fails fast like a machine without internet. Enabled by env LLD_OFFLINE=1 (see api/main.py) or by tests."""
import ipaddress
import socket

_orig = {}
_LOCAL = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


def _is_local(host):
    if host in _LOCAL:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def block_network():
    """Idempotent. Returns a function that restores the original socket functions."""
    if _orig:
        return unblock_network
    _orig.update(connect=socket.socket.connect, getaddrinfo=socket.getaddrinfo)

    def connect(self, addr, *a, **k):
        if isinstance(addr, tuple) and not _is_local(str(addr[0])):
            raise OSError(101, f"network blocked (simulated offline): {addr[0]}")
        return _orig["connect"](self, addr, *a, **k)

    def getaddrinfo(host, *a, **k):
        if host is not None and not _is_local(str(host)):
            raise socket.gaierror(-3, f"network blocked (simulated offline): {host}")
        return _orig["getaddrinfo"](host, *a, **k)

    socket.socket.connect = connect
    socket.getaddrinfo = getaddrinfo
    return unblock_network


def unblock_network():
    if _orig:
        socket.socket.connect = _orig.pop("connect")
        socket.getaddrinfo = _orig.pop("getaddrinfo")
