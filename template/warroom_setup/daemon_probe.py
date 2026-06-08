"""Local mailbox-daemon liveness probe (T5). Stdlib only, Python >=3.9.

This is the ONLY module in the package permitted to import `socket`, and it does
so purely for an AF_UNIX *local IPC* liveness check — never outbound network,
never an HTTP client, and never an import of `mailbox.client`. Confining the
import here keeps test_security.test_no_network_imports_in_package meaningful
for the rest of the wizard package (surfaced to team-lead as a plan/invariant
reconciliation).
"""
import socket


def ping_socket(path, timeout=1.0):
    # type: (str, float) -> bool
    """Return True iff a UNIX-domain socket at `path` accepts a connection within
    `timeout` seconds. Never spawns anything. Any failure -> False."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(str(path))
        return True
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout, OSError):
        return False
    finally:
        try:
            s.close()
        except OSError:
            pass
