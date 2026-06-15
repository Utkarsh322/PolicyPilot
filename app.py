try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import streamlit as st
import requests
import os
from pathlib import Path

# Page config
st.set_page_config(
    page_title="PolicyPilot — Enterprise Policy RAG Assistant",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Server URL
API_URL = "http://127.0.0.1:8000"

# Inject Premium CSS for styling
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Gradient Header */
    .main-title {
        background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 50%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem;
        font-weight: 700;
        margin-bottom: 5px;
        text-align: left;
    }
    
    .subtitle {
        color: #64748B;
        font-size: 1.1rem;
        margin-bottom: 25px;
    }
    
    /* Metrics panel */
    .metric-card {
        background: rgba(255, 255, 255, 0.7);
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
    }
    
    /* Source badges */
    .source-badge {
        display: inline-block;
        padding: 3px 8px;
        background-color: #EFF6FF;
        color: #1D4ED8;
        border: 1px solid #BFDBFE;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 500;
        margin-right: 5px;
        margin-bottom: 5px;
    }
    
    /* Confidence indicators */
    .confidence-badge-high {
        background-color: #DCFCE7;
        color: #15803D;
        border: 1px solid #BBF7D0;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .confidence-badge-low {
        background-color: #FEE2E2;
        color: #B91C1C;
        border: 1px solid #FCA5A5;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    /* Side-by-side search blocks */
    .mode-header {
        font-size: 1.2rem;
        font-weight: 600;
        padding: 8px 12px;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    .mode-semantic {
        background-color: #EEF2F6;
        color: #334155;
        border-left: 5px solid #64748B;
    }
    .mode-hybrid {
        background-color: #ECFDF5;
        color: #065F46;
        border-left: 5px solid #10B981;
    }
    
    /* Hide Streamlit Deploy Button */
    .stDeployButton, [data-testid="stAppDeployButton"] {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)


# Helper function to query backend
# Helper to lazy-load local pipeline in case backend is offline/unreachable
@st.cache_resource
def get_local_pipeline():
    try:
        from src.pipeline import RAGPipeline
        return RAGPipeline()
    except Exception as e:
        st.error(f"Failed to initialize local in-process pipeline: {e}")
        return None

# Helper to automatically generate default policy PDFs if the folder is empty
def check_and_generate_defaults():
    policies_dir = Path("data/policies")
    if not policies_dir.exists() or not any(policies_dir.glob("*.pdf")):
        try:
            from scripts.generate_pdfs import POLICIES, create_policy_pdf
            st.info("No policy documents found in library. Generating default corporate policies...")
            for filename, data in POLICIES.items():
                create_policy_pdf(filename, data["title"], data["content"])
            st.success("Default corporate policies generated successfully!")
            
            # Immediately trigger indexing locally
            pipeline = get_local_pipeline()
            if pipeline:
                with st.status("Indexing documents into local database...", expanded=True) as status:
                    success = pipeline.reindex()
                    if success:
                        status.update(label="Initial indexing completed successfully!", state="complete")
                    else:
                        status.update(label="Initial indexing failed.", state="error")
        except Exception as e:
            st.error(f"Error during initial policy setup: {e}")

# Run the check on application load
check_and_generate_defaults()


# Helper function to query backend (with local in-process fallback)
def query_backend(question, history, search_mode, threshold):
    try:
        payload = {
            "question": question,
            "history": history,
            "search_mode": search_mode,
            "threshold": threshold
        }
        response = requests.post(f"{API_URL}/query", json=payload, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return None
    except Exception:
        # Fallback to local execution
        pipeline = get_local_pipeline()
        if pipeline:
            try:
                return pipeline.answer_question(
                    query=question,
                    history=history,
                    search_mode=search_mode,
                    threshold=threshold
                )
            except Exception as e:
                st.error(f"Local query processing failed: {e}")
        return None

# Helper to fetch system status (with local in-process fallback)
def fetch_status():
    try:
        res = requests.get(f"{API_URL}/status", timeout=2)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
        
    # Local fallback status retrieval
    try:
        policies_dir = Path("data/policies")
        pdf_docs = [f.name for f in policies_dir.glob("*.pdf")] if policies_dir.exists() else []
        pipeline = get_local_pipeline()
        chunk_count = len(pipeline.retriever.all_documents) if (pipeline and pipeline.retriever) else 0
        from src import config
        return {
            "document_count": len(pdf_docs),
            "documents": pdf_docs,
            "chunk_count": chunk_count,
            "llm_provider": pipeline.generator.provider if (pipeline and pipeline.generator) else config.LLM_PROVIDER,
            "confidence_threshold": config.CONFIDENCE_THRESHOLD,
            "hybrid_weights": {
                "semantic_weight": config.HYBRID_SEMANTIC_WEIGHT,
                "keyword_weight": config.HYBRID_KEYWORD_WEIGHT
            },
            "is_local_fallback": True
        }
    except Exception:
        return None

# Helper to reindex (with local in-process fallback)
def trigger_reindex():
    try:
        res = requests.post(f"{API_URL}/reindex", timeout=120)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pipeline = get_local_pipeline()
        if pipeline:
            success = pipeline.reindex()
            return {"success": success, "message": "Local database re-indexed successfully."}
    return None

# Helper to delete document (with local in-process fallback)
def delete_document(filename):
    try:
        res = requests.delete(f"{API_URL}/document/{filename}", timeout=60)
        if res.status_code == 200:
            return res.json()
    except Exception:
        policies_dir = Path("data/policies")
        file_path = policies_dir / filename
        if file_path.exists():
            try:
                file_path.unlink()
                pipeline = get_local_pipeline()
                if pipeline:
                    success = pipeline.reindex()
                    return {"success": success, "message": f"Local document '{filename}' deleted and re-indexed."}
            except Exception as e:
                st.error(f"Failed to delete local document: {e}")
    return None

# Helper to upload document (with local in-process fallback)
def upload_document(file_bytes, filename):
    try:
        files = {"file": (filename, file_bytes, "application/pdf")}
        res = requests.post(f"{API_URL}/upload", files=files, timeout=120)
        if res.status_code == 200:
            return res.json()
    except Exception:
        policies_dir = Path("data/policies")
        policies_dir.mkdir(parents=True, exist_ok=True)
        file_path = policies_dir / filename
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(file_bytes)
            pipeline = get_local_pipeline()
            if pipeline:
                success = pipeline.reindex()
                return {"success": success, "message": f"Local document '{filename}' uploaded and indexed."}
        except Exception as e:
            st.error(f"Failed to upload local document: {e}")
    return None


# Sidebar
st.sidebar.markdown("### 🛠️ PolicyPilot Settings")

# 1. Choose Provider
provider_options = ["Mock/Local Only", "Ollama (Local LLM)", "OpenAI API", "Google Gemini API"]
provider_sel = st.sidebar.selectbox("LLM Model Provider", provider_options)

# Map UI selections to environment configuration setting names
provider_map = {
    "Mock/Local Only": "mock",
    "Ollama (Local LLM)": "ollama",
    "OpenAI API": "openai",
    "Google Gemini API": "gemini"
}
selected_provider = provider_map[provider_sel]

# Save API keys to environment dynamically if input
if selected_provider == "openai":
    openai_key = st.sidebar.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    if openai_key:
        os.environ["OPENAI_API_KEY"] = openai_key
elif selected_provider == "gemini":
    gemini_key = st.sidebar.text_input("Gemini API Key", type="password", value=os.getenv("GEMINI_API_KEY", ""))
    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key

# 2. Retrieval parameters
st.sidebar.markdown("### 🔍 Retrieval Configuration")
confidence_threshold = st.sidebar.slider(
    "Confidence Relevance Threshold",
    min_value=0.1, max_value=0.9, value=0.35, step=0.05,
    help="Responses below this score will use the fallback response."
)

comparison_mode = st.sidebar.checkbox(
    "🔄 Compare Semantic vs Hybrid",
    value=False,
    help="Submit query to both retrieval types and view results side-by-side."
)

# 3. Document Library status
st.sidebar.markdown("### 📂 Policy Document Library")
sys_status = fetch_status()

if sys_status:
    if sys_status.get("is_local_fallback"):
        st.sidebar.info("🤖 Self-Contained Local Mode (FastAPI Offline)")
    st.sidebar.write(f"**Indexed Documents:** {sys_status['document_count']}")
    st.sidebar.write(f"**Total Chunks:** {sys_status['chunk_count']}")
    
    # List indexed docs with delete buttons
    for doc in sys_status['documents']:
        col_doc, col_del = st.sidebar.columns([4, 1])
        col_doc.markdown(f"📄 `{doc}`")
        if col_del.button("🗑️", key=f"del_{doc}", help=f"Delete {doc} from vector library"):
            with st.sidebar.status(f"Deleting {doc}...", expanded=True) as status:
                res = delete_document(doc)
                if res and res.get("success"):
                    status.update(label=f"Deleted {doc} successfully!", state="complete")
                    st.rerun()
                else:
                    status.update(label=f"Failed to delete {doc}", state="error")
else:
    st.sidebar.warning("API server is offline. Run `python api.py` to start the backend.")

# Re-index Button
if st.sidebar.button("♻️ Re-Index Document Library", use_container_width=True):
    with st.sidebar.status("Re-indexing policy files...", expanded=True) as status:
        st.write("Extracting PDF texts...")
        result = trigger_reindex()
        if result and result.get("success"):
            status.update(label="Re-indexing completed!", state="complete")
            st.rerun()
        else:
            status.update(label="Indexing failed!", state="error")

# Upload new document widget
st.sidebar.markdown("---")
st.sidebar.markdown("### 📤 Upload New Policy")
uploaded_file = st.sidebar.file_uploader("Upload policy document (.pdf)", type=["pdf"])
if uploaded_file is not None:
    # Use session state to ensure we only upload this specific file once per upload interaction
    upload_key = f"uploaded_{uploaded_file.name}_{uploaded_file.size}"
    if upload_key not in st.session_state:
        with st.sidebar.status(f"Uploading and indexing {uploaded_file.name}...", expanded=True) as status:
            res = upload_document(uploaded_file.getvalue(), uploaded_file.name)
            if res and res.get("success"):
                status.update(label="File uploaded and indexed successfully!", state="complete")
                st.session_state[upload_key] = True
                st.rerun()
            else:
                status.update(label="Indexing failed!", state="error")
else:
    # Clean up upload keys if file is cleared
    for key in list(st.session_state.keys()):
        if key.startswith("uploaded_"):
            del st.session_state[key]




# Main Panel
st.markdown("<div class='main-title'>PolicyPilot</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>AI-Powered Enterprise Policy Assistant with Hybrid Retrieval</div>", unsafe_allow_html=True)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Clear Chat History Button
if st.button("🧹 Clear Chat History", help="Clears conversation memory"):
    st.session_state.messages = []
    st.rerun()

# Display Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sources" in msg and msg["sources"]:
            with st.expander("📚 Reference Sources"):
                for src in msg["sources"]:
                    st.markdown(f"**{src['title']}** — `{src['source']}` (Page {src['page']})")

# User Input
if prompt := st.chat_input("Ask about company HR or IT policies (e.g., 'What is the WFH internet allowance?')"):
    
    # Add User message to chat
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # Prepare history payload for RAG API
    history_payload = []
    # Only take previous user/assistant strings (skip metadata like sources)
    for m in st.session_state.messages[:-1]:
        history_payload.append({
            "role": m["role"],
            "content": m["content"]
        })

    # Execute backend call
    with st.chat_message("assistant"):
        if comparison_mode:
            # Side-by-side columns
            col_sem, col_hyb = st.columns(2)
            
            with col_sem:
                st.markdown("<div class='mode-header mode-semantic'>Semantic Only Search</div>", unsafe_allow_html=True)
                with st.spinner("Retrieving via semantic..."):
                    res_sem = query_backend(prompt, history_payload, "semantic", confidence_threshold)
                
                if res_sem:
                    badge = f"<span class='confidence-badge-high'>Score: {res_sem['confidence_score']:.3f}</span>" if res_sem['passed_threshold'] else f"<span class='confidence-badge-low'>Score: {res_sem['confidence_score']:.3f}</span>"
                    st.markdown(f"**Status:** {badge}", unsafe_allow_html=True)
                    st.markdown(res_sem["answer"])
                    
                    if res_sem["sources"]:
                        with st.expander("📚 Semantic Sources"):
                            for src in res_sem["sources"]:
                                st.markdown(f"**{src['title']}** — `{src['source']}` (Page {src['page']})")
                                
            with col_hyb:
                st.markdown("<div class='mode-header mode-hybrid'>Hybrid Search (Semantic + BM25)</div>", unsafe_allow_html=True)
                with st.spinner("Retrieving via hybrid..."):
                    res_hyb = query_backend(prompt, history_payload, "hybrid", confidence_threshold)
                    
                if res_hyb:
                    badge = f"<span class='confidence-badge-high'>Score: {res_hyb['confidence_score']:.3f}</span>" if res_hyb['passed_threshold'] else f"<span class='confidence-badge-low'>Score: {res_hyb['confidence_score']:.3f}</span>"
                    st.markdown(f"**Status:** {badge}", unsafe_allow_html=True)
                    st.markdown(res_hyb["answer"])
                    
                    if res_hyb["sources"]:
                        with st.expander("📚 Hybrid Sources"):
                            for src in res_hyb["sources"]:
                                st.markdown(f"**{src['title']}** — `{src['source']}` (Page {src['page']})")
            
            # For history, save the hybrid response as it's the default main retriever
            if res_hyb:
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"**(Comparison Mode Output)**\n\n*Hybrid Search:* {res_hyb['answer']}",
                    "sources": res_hyb["sources"]
                })
                
        else:
            # Normal output
            with st.spinner("Thinking..."):
                res = query_backend(prompt, history_payload, "hybrid", confidence_threshold)
                
            if res:
                # Add confidence score display
                conf_badge = f"<span class='confidence-badge-high'>Confidence: {res['confidence_score']:.3f}</span>" if res['passed_threshold'] else f"<span class='confidence-badge-low'>Confidence: {res['confidence_score']:.3f} (Out of Scope)</span>"
                st.markdown(f"Relevance: {conf_badge}", unsafe_allow_html=True)
                st.markdown(res["answer"])
                
                if res["sources"]:
                    with st.expander("📚 Reference Sources"):
                        for src in res["sources"]:
                            st.markdown(f"**{src['title']}** — `{src['source']}` (Page {src['page']})")
                
                # Append to session history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": res["answer"],
                    "sources": res["sources"]
                })
                
            else:
                st.error("Error generating response.")
