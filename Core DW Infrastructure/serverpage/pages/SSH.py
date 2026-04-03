import streamlit as st
import psutil
import datetime
import pandas as pd

st.title("🔐 SSH Connections")
st.markdown("---")

connections = []

for conn in psutil.net_connections(kind="inet"):
    if conn.laddr and conn.laddr.port == 22 and conn.status == psutil.CONN_ESTABLISHED:
        connections.append({
            "Local Address": f"{conn.laddr.ip}:{conn.laddr.port}",
            "Remote Address": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A",
            "PID": conn.pid,
            "Process": psutil.Process(conn.pid).name() if conn.pid else "N/A",
            "Time Checked": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

if connections:
    df = pd.DataFrame(connections)
    st.success(f"Active SSH connections: {len(df)}")
    st.dataframe(df, use_container_width=True)
else:
    st.info("No active SSH connections found.")
