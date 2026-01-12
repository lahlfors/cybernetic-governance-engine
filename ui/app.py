import uuid

import streamlit as st
import requests
import os
import google.auth.transport.requests
from google.oauth2 import id_token

# Configuration
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")

def get_auth_token():
    """Retrieves an OIDC ID token for calling the backend."""
    try:
        # Check if running locally (proxy) vs Cloud Run
        if "localhost" in BACKEND_URL or "127.0.0.1" in BACKEND_URL:
            return None # Local testing usually doesn't need auth or handles it differently
            
        auth_req = google.auth.transport.requests.Request()
        return id_token.fetch_id_token(auth_req, BACKEND_URL)
    except Exception as e:
        print(f"Warning: Could not get ID token: {e}")
        return None

# Initialize Session State
if "user_id" not in st.session_state:
    # Check URL parameters for persistent user ID
    # Use st.query_params (Streamlit 1.30+) or fallback for older versions
    try:
        query_params = st.query_params
    except AttributeError:
        query_params = st.experimental_get_query_params()
        
    # Get user_id from params (handle dict or Proxy object)
    uid_param = query_params.get("user_id") if hasattr(query_params, "get") else None
    
    if uid_param:
        # Handle list if older streamlit returns list
        st.session_state.user_id = uid_param[0] if isinstance(uid_param, list) else uid_param
    else:
        st.session_state.user_id = str(uuid.uuid4())

# ...

def query_agent(prompt: str) -> str:
    # ...
    try:
        response = requests.post(
            f"{BACKEND_URL}/agent/query",
            json={
                "prompt": prompt,
                "user_id": st.session_state.user_id 
            },
            headers=headers,
            timeout=300  # Match Cloud Run timeout for complex operations
        )
# ...
        
        # Handle specific status codes
        if response.status_code == 403:
            return "⚠️ Authentication failed. The UI cannot access the backend service. Please check service account permissions."
        
        response.raise_for_status()
        return response.json().get("response", "No response received.")
    except requests.exceptions.RequestException as e:
        return f"Error communicating with agent: {str(e)}"

# --- Streamlit UI ---
st.set_page_config(
    page_title="Governed Financial Advisor",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Governed Financial Advisor")
st.caption("AI-powered financial analysis with governance guardrails")

# Sidebar with info
with st.sidebar:
    st.header("About")
    
    # Display User ID
    st.info(f"**User ID:** `{st.session_state.user_id}`")
    st.markdown("Add `?user_id=your_name` to the URL to persist memory.")

    st.markdown("""
    This financial advisor can help you with:
    - 📊 **Market Analysis** - Analyze stock tickers
    - 📈 **Trading Strategies** - Get strategy recommendations
    - ⚖️ **Risk Assessment** - Evaluate portfolio risk
    - 🔒 **Governed Trading** - Execute trades with policy enforcement
    
    *Governed Trading is available but Google does not take any responsibility for results.*
    
    **All services are provided solely for educational purposes.**
    """)
    
    st.divider()
    st.markdown("**Backend Status**")
    
    # Health check with auth
    try:
        headers = {}
        token = get_auth_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        health = requests.get(f"{BACKEND_URL}/health", headers=headers, timeout=5)
        if health.status_code == 200:
            st.success("✅ Connected")
        else:
            st.error(f"⚠️ Status: {health.status_code}")
    except:
        st.warning("⚠️ Cannot reach backend")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask about market analysis, strategies, or trading..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get agent response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = query_agent(prompt)
        st.markdown(response)
    
    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": response})

# Footer
st.divider()
st.caption("⚠️ **Disclaimer:** This is for educational purposes only. Not financial advice.")
