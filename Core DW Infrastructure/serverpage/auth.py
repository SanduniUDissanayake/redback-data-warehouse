import os
import streamlit as st
import msal
import jwt
from jwt import PyJWKClient

TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

SCOPES = ["User.Read"]


def _check_env():
    missing = []
    if not TENANT_ID:
        missing.append("AZURE_TENANT_ID")
    if not CLIENT_ID:
        missing.append("AZURE_CLIENT_ID")
    if not CLIENT_SECRET:
        missing.append("AZURE_CLIENT_SECRET")
    if not REDIRECT_URI:
        missing.append("REDIRECT_URI")

    if missing:
        st.error("Missing server environment variables:\n\n" + "\n".join(missing))
        st.stop()

def _msal_app():
    return msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        client_credential=CLIENT_SECRET,
        authority=AUTHORITY,
    )

def _auth_url():
    return _msal_app().get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        prompt="select_account",
    )

def _validate_id_token(id_token: str) -> dict:
    """Validate Entra ID token signature, expiry, and audience."""
    jwks_url = f"{AUTHORITY}/discovery/v2.0/keys"
    jwk_client = PyJWKClient(jwks_url)
    signing_key = jwk_client.get_signing_key_from_jwt(id_token)

    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=CLIENT_ID,
        options={"verify_exp": True},
    )
    return claims

def logout_button():
    if st.button("Logout"):
        st.session_state.pop("user", None)
        st.rerun()


def require_login():
    """
    Call this at the TOP of app.py:
        from auth import require_login
        user = require_login()
    """
    _check_env()

    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is not None:
        return st.session_state.user

    params = st.query_params
    code = params.get("code")
    error = params.get("error")
    error_description = params.get("error_description")

    if error:
        st.error("Login error returned by Microsoft:")
        st.write(error)
        if error_description:
            st.write(error_description)
        st.stop()

    st.title("Sign in required")

    if code:
        result = _msal_app().acquire_token_by_authorization_code(
            code=code,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )

        id_token = result.get("id_token")
        if not id_token:
            st.error("Authentication failed (no id_token returned).")
            st.write(result)
            st.stop()

        try:
            claims = _validate_id_token(id_token)
        except Exception as e:
            st.error("Token validation failed.")
            st.exception(e)
            st.stop()

        st.session_state.user = claims
        st.query_params.clear()
        st.rerun()

    st.link_button("Sign in with Microsoft", _auth_url())
    st.stop()
