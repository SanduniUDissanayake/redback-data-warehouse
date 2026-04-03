import streamlit as st, os, shutil
from auth import require_login

require_login()

st.title("💾 Local Storage")
st.markdown("---")

def human_bytes(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(n) < 1024:
            return f"{n:3.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

total, used, free = shutil.disk_usage("/")
pct = used / total * 100

st.write(f"**/** — {pct:.1f}% used ({human_bytes(used)} / {human_bytes(total)})")
st.progress(int(pct))

