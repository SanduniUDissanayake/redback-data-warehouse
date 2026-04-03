import streamlit as st
import socket
import pandas as pd
from typing import List, Tuple
from auth import require_login

require_login()

try:
    import psutil
except ImportError:
    psutil = None

st.set_page_config(page_title="Open Ports Viewer", layout="wide")
st.title("🔓 Open Ports")
st.markdown("Automatically showing all listening TCP/UDP ports on this machine.")

def human_ports_df(rows: List[Tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["Protocol", "Local IP", "Port", "Process"])

def list_open_ports_psutil():
    rows = []
    for c in psutil.net_connections(kind="inet"):
        if not c.laddr:
            continue

        ip = getattr(c.laddr, "ip", c.laddr[0])
        port = getattr(c.laddr, "port", c.laddr[1])

        if c.type == socket.SOCK_STREAM:
            proto = "TCP"
            if c.status != psutil.CONN_LISTEN:
                continue
        else:
            proto = "UDP"

        pid = c.pid or None
        pname = "-"
        if pid:
            try:
                pname = psutil.Process(pid).name()
            except Exception:
                pass

        rows.append((proto, ip, port, pname))

    return human_ports_df(rows)

if psutil:
    df = list_open_ports_psutil()
else:
    df = list_open_ports_netstat()

df = df.sort_values(["Protocol", "Port"]).reset_index(drop=True)

if df.empty:
    st.info("No open ports detected or missing permissions.")
else:
    st.success(f"Found {len(df)} listening ports:")

    st.table(df)
