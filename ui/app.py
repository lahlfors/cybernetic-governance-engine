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

if "project_id" not in st.session_state:
    st.session_state.project_id = "unknown"

# ...

def query_agent(prompt: str):
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
            return "⚠️ Authentication failed. The UI cannot access the backend service. Please check service account permissions.", None
        
        response.raise_for_status()
        data = response.json()
        return data.get("response", "No response received."), data.get("trace_id")
    except requests.exceptions.RequestException as e:
        return f"Error communicating with agent: {str(e)}", None

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
            data = health.json()
            if "project_id" in data:
                st.session_state.project_id = data["project_id"]
        else:
            st.error(f"⚠️ Status: {health.status_code}")
    except:
        st.warning("⚠️ Cannot reach backend")

    # --- DEMO CONTROL PANEL ---
    st.divider()
    st.header("🛠️ Demo Control Panel")

    # 1. Scenario Selector
    st.subheader("Scenario Injection")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Normal Operation"):
            try:
                requests.post(f"{BACKEND_URL}/demo/reset", headers=headers)
                st.toast("System Reset to Normal")
            except: st.error("Failed to reset")

    with col2:
        if st.button("🐢 High Latency (>200ms)"):
            try:
                requests.post(f"{BACKEND_URL}/demo/context", json={"latency": 250.0, "risk_profile": "Balanced"}, headers=headers)
                st.toast("Injecting 250ms Latency")
            except: st.error("Failed to set latency")

    # 2. Green Stack Pipeline Trigger
    st.subheader("Green Stack Governance")

    st.caption("Runs a fully governed Risk Discovery & Policy Transpilation loop on Vertex AI.")
    if st.button("☁️ Run Green Stack on Vertex AI"):
        try:
            requests.post(f"{BACKEND_URL}/demo/pipeline", json={"strategy": "High Frequency Momentum"}, headers=headers)
            st.toast("Vertex Submission Initiated")
        except: st.error("Failed to submit to Vertex")

    # 3. Live Demo Status
    try:
        status_res = requests.get(f"{BACKEND_URL}/demo/status", headers=headers, timeout=2)
        if status_res.status_code == 200:
            status = status_res.json()

            # Latency Status
            lat = status.get("latency", 0)
            if lat > 0:
                st.warning(f"⚠️ Simulated Latency: {lat}ms")
            else:
                st.info("⚡ Latency: Normal")

            # Pipeline Status
            p_status = status.get("pipeline", {})
            st.caption(f"Pipeline ({p_status.get('mode', 'idle')}): {p_status.get('status')} - {p_status.get('message')}")

            # Dashboard Link (Vertex)
            dashboard_url = p_status.get("dashboard_url")
            if dashboard_url:
                st.markdown(f"☁️ [View Vertex Pipeline]({dashboard_url})")

            # Generated Rules (Fetched if available)
            rules = status.get("rules")
            if rules:
                with st.expander("📜 View Generated Rules"):
                    st.code(rules, language="python")
    except:
        st.caption("Status: Offline")


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
            response, trace_id = query_agent(prompt)
        st.markdown(response)

        # Show Trace Link
        if trace_id and st.session_state.project_id != "unknown":
            url = f"https://console.cloud.google.com/traces/list?project={st.session_state.project_id}&tid={trace_id}"
            st.caption(f"🔍 [View Trace]({url})")

    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": response, "trace_id": trace_id})

# Footer
st.divider()
st.caption("⚠️ **Disclaimer:** This is for educational purposes only. Not financial advice.")
