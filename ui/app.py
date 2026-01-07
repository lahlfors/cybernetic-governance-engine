"""
Streamlit Chat UI for Governed Financial Advisor
Connects to the deployed Cloud Run backend API.
"""
import os
import requests
import streamlit as st

# Configuration
BACKEND_URL = os.environ.get(
    "BACKEND_URL", 
    "https://governed-financial-advisor-104563134786.us-central1.run.app"
)

def get_auth_token():
    """Gets Google Cloud identity token for authenticated requests."""
    import sys
    
    # Try metadata server directly first (most reliable in Cloud Run)
    try:
        import urllib.request
        url = f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience={BACKEND_URL}"
        req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
        token = urllib.request.urlopen(req, timeout=5).read().decode()
        print(f"DEBUG: Got token from metadata server (length: {len(token)})", file=sys.stderr)
        return token
    except Exception as e:
        print(f"DEBUG: Metadata server failed: {e}", file=sys.stderr)
    
    # Fallback to google-auth library
    try:
        import google.auth
        from google.auth.transport.requests import Request
        import google.oauth2.id_token
        
        auth_req = Request()
        token = google.oauth2.id_token.fetch_id_token(auth_req, BACKEND_URL)
        print(f"DEBUG: Got token from google-auth (length: {len(token)})", file=sys.stderr)
        return token
    except Exception as e:
        print(f"DEBUG: google-auth failed: {e}", file=sys.stderr)
    
    print("DEBUG: No token obtained", file=sys.stderr)
    return None

def query_agent(prompt: str) -> str:
    """Sends a query to the financial advisor backend."""
    headers = {"Content-Type": "application/json"}
    
    # Add auth token if available (for Cloud Run to Cloud Run calls)
    token = get_auth_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/agent/query",
            json={"prompt": prompt},
            headers=headers,
            timeout=120  # Agent responses can take time
        )
        
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
    st.markdown("""
    This financial advisor can help you with:
    - 📊 **Market Analysis** - Analyze stock tickers
    - 📈 **Trading Strategies** - Get strategy recommendations
    - ⚖️ **Risk Assessment** - Evaluate portfolio risk
    - 🔒 **Governed Trading** - Execute trades with policy enforcement
    """)
    
    st.divider()
    st.markdown("**Backend Status**")
    
    # Health check
    try:
        health = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if health.status_code == 200:
            st.success("✅ Connected")
        else:
            st.error(f"⚠️ Status: {health.status_code}")
    except:
        st.warning("⚠️ Cannot reach backend (auth may be required)")

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
