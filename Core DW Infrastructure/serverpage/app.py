from pathlib import Path
from PIL import Image
import streamlit as st
from auth import require_login
from auth import require_login, logout_button

user = require_login()

st.sidebar.success(f"Logged in as: {user.get('name', 'user')}")
logout_button()

st.markdown("---")
st.header("🔗Important Links")
st.write("Rabbit MQ: http://10.137.0.149:15672/ ")
st.write("Streamlit: https://redback.it.deakin.edu.au/file-upload")
st.write("Airflow: http://10.137.0.149:8888/login/")
st.write("Kafka: https://redback.it.deakin.edu.au/kafka/")
st.write("Wazuh: https://redback.it.deakin.edu.au/wazuh")
st.write("Dremio: http://10.137.0.149:9047")
st.write("MinIO: https://redback.it.deakin.edu.au/minio")


st.markdown("---")
st.header("🛠️Maintenance")
st.write("Grafana: https://cyber.redback.it.deakin.edu.au:9443/monitor/login")
