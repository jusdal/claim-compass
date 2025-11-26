import os
import streamlit as st
import pathlib
import logging
import json
from datetime import datetime
from config import Config
from agents.vision import VisionAgent
from agents.coordinator import CoordinatorTeam
from observability import get_observability_manager

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Config
PROJECT_ID = Config.PROJECT_ID
DATA_STORE_ID = Config.DATA_STORE_ID
LOCATION = Config.LOCATION

os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = LOCATION
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

st.set_page_config(page_title="Claim Compass", page_icon="🛡️", layout="wide")

# --- SESSION STATE INITIALIZATION ---
if "generated_letter" not in st.session_state:
    st.session_state.generated_letter = None
if "vision_output" not in st.session_state:
    st.session_state.vision_output = None
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

# ==========================================
# 🎛️ SIDEBAR: ADMIN & OBSERVABILITY
# ==========================================
with st.sidebar:
    st.title("⚙️ Admin Console")
    
    # --- SECTION 1: LIVE METRICS ---
    st.subheader("📡 System Health")
    obs = get_observability_manager()
    summary = obs.get_summary()
    
    col1, col2 = st.columns(2)
    col1.metric("Total Runs", summary.get("total_executions", 0))
    col2.metric("Success %", f"{summary.get('overall_success_rate', 0):.0f}%")
    
    # --- SECTION 2: EVALUATION SCORES ---
    st.divider()
    st.subheader("🧪 Quality Benchmarks")
    eval_dir = pathlib.Path("evaluation_results")
    if eval_dir.exists():
        eval_files = sorted(eval_dir.glob("evaluation_*.json"), key=os.path.getmtime, reverse=True)
        if eval_files:
            with open(eval_files[0], 'r') as f:
                latest_eval = json.load(f)
            
            # Calculate averages from the latest run
            results = latest_eval.get("results", [])
            if results:
                avg_score = sum(r["overall_score"] for r in results) / len(results)
                st.metric("Latest Eval Score", f"{avg_score*100:.1f}%", 
                         help=f"Based on {len(results)} test cases run at {latest_eval.get('timestamp')}")
                
                with st.expander("View Detailed Scores"):
                    for r in results:
                        icon = "✅" if r['success'] else "❌"
                        st.caption(f"{icon} **{r['case_id']}**: {r['overall_score']*100:.0f}%")
        else:
            st.caption("No evaluation data found.")
    
    # --- SECTION 3: LOGS ---
    st.divider()
    with st.expander("📜 System Logs", expanded=False):
        log_dir = pathlib.Path("logs")
        if log_dir.exists():
            log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
            if log_files:
                selected_log = st.selectbox("Log File", log_files, format_func=lambda x: x.name)
                if selected_log:
                    with open(selected_log, 'r') as f:
                        st.code(f.read()[-2000:], language="log") # Show last 2000 chars
            else:
                st.info("No logs yet.")

# ==========================================
# 🏠 MAIN PAGE: PATIENT ADVOCATE
# ==========================================

st.title("🛡️ Claim Compass")
st.markdown("### AI-Powered Insurance Appeal Generator")
st.markdown("Stop fighting insurance companies alone. Upload your denied bill, and our AI agents will research your policy, cite federal laws, and write a professional appeal letter for you.")

st.divider()

# --- STEP 1: PATIENT DETAILS ---
st.subheader("1. Patient Information")
with st.container(border=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        patient_name = st.text_input("Patient Name", placeholder="e.g. Jane Doe", key="p_name")
    with col2:
        insurance_provider = st.text_input("Insurance Provider", placeholder="e.g. Kaiser, Aetna", key="p_provider")
    with col3:
        patient_zip = st.text_input("Zip Code", placeholder="e.g. 10001", key="p_zip")
        
    additional_context = st.text_area(
        "Additional Context (Optional)", 
        placeholder="Tell us what happened... e.g., 'I was on vacation and this was the only ER available.'",
        key="p_context"
    )

# --- STEP 2: UPLOAD BILL ---
st.subheader("2. Upload Denied Bill")
uploaded_file = st.file_uploader("Upload a photo or PDF of your medical bill", type=["jpg", "png", "jpeg", "pdf"])

if uploaded_file:
    # --- STEP 3: PROCESSING ---
    if st.button("🚀 Generate Appeal Letter", type="primary", use_container_width=True) or st.session_state.is_processing:
        st.session_state.is_processing = True
        
        # Save File (if new)
        if not st.session_state.generated_letter:
            temp_filename = f"temp_bill{pathlib.Path(uploaded_file.name).suffix}"
            with open(temp_filename, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Display Preview
            col_img, col_status = st.columns([1, 2])
            with col_img:
                if uploaded_file.type in ["image/jpeg", "image/png", "image/jpg"]:
                    st.image(uploaded_file, use_container_width=True, caption="Your Bill")
                else:
                    st.info(f"📄 PDF: {uploaded_file.name}")

            with col_status:
                # AGENT 1: VISION
                with st.status("👀 Reading Bill...", expanded=True) as status:
                    if not st.session_state.vision_output:
                        vision = VisionAgent(PROJECT_ID, Config.VISION_LOCATION)
                        bill_json_text = vision.analyze_bill(temp_filename)
                        st.session_state.vision_output = bill_json_text
                        st.write("✅ Extracted bill details")
                    
                    # AGENT 2: RESEARCH & WRITING
                    status.update(label="🤖 AI Agents Working...", state="running")
                    st.write(f"🔍 Searching **{insurance_provider or 'General'}** policy documents...")
                    st.write("⚖️  Checking Federal protections (No Surprises Act)...")
                    st.write("✍️  Drafting professional appeal...")
                    
                    if not st.session_state.generated_letter:
                        team = CoordinatorTeam(PROJECT_ID, LOCATION, DATA_STORE_ID)
                        final_letter = team.run(
                            st.session_state.vision_output, 
                            patient_name=patient_name, 
                            patient_zip=patient_zip, 
                            insurance_provider=insurance_provider,
                            context=additional_context
                        )
                        st.session_state.generated_letter = final_letter
                    
                    status.update(label="✅ Appeal Generated!", state="complete", expanded=False)
            
            st.session_state.is_processing = False
            st.rerun()

    # --- STEP 4: RESULTS ---
    if st.session_state.generated_letter:
        st.divider()
        st.subheader("3. Your Appeal Letter")
        
        st.success("Your letter is ready! Review it below.")
        
        col_text, col_actions = st.columns([3, 1])
        
        with col_text:
            st.text_area("Appeal Letter Draft", value=st.session_state.generated_letter, height=600)
        
        with col_actions:
            st.download_button(
                label="📥 Download Text",
                data=st.session_state.generated_letter,
                file_name=f"Appeal_{datetime.now().strftime('%Y-%m-%d')}.txt",
                mime="text/plain",
                type="primary",
                use_container_width=True
            )
            
            if st.button("🔄 Start Over", use_container_width=True):
                st.session_state.generated_letter = None
                st.session_state.vision_output = None
                st.session_state.is_processing = False
                st.rerun()