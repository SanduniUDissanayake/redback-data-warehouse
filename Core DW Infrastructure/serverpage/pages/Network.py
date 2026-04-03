import streamlit as st
import subprocess
import socket
import re
from auth import require_login

require_login()

st.title("🌐 Network")
st.markdown("---")

hostname = socket.gethostname()
st.header("🖥️ Hostname")
st.code(hostname)

ip_address = socket.gethostbyname(hostname)
st.header("📡 Local IP Address")
st.code(ip_address)
