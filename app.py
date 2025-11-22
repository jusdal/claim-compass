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

# --- SIDEBAR: Patient Details & Observability ---
with st.sidebar:
    st.header("👤 Patient Details")
    st.info("These details help the agents find the correct state laws and format the letter correctly.")
    
    patient_name = st.text_input("Patient Name", placeholder="e.g. Jane Doe")
    patient_zip = st.text_input("Zip Code", placeholder="e.g. 10001")
    additional_context = st.text_area(
        "Additional Context", 
        placeholder="e.g. This was an emergency visit while traveling...",
        help="Add any details you want the AI to know about this specific situation."
    )
    
    st.divider()
    
    # Observability Section
    st.header("📊 Observability")
    
    if st.button("View Performance Summary"):
        obs = get_observability_manager()
        summary = obs.get_summary()
        
        if "message" in summary:
            st.info(summary["message"])
        else:
            st.metric("Total Executions", summary.get("total_executions", 0))
            st.metric("Total Duration", f"{summary.get('total_duration_seconds', 0):.1f}s")
            st.metric("Success Rate", f"{summary.get('overall_success_rate', 0):.1f}%")
            
            if "phase_breakdown" in summary:
                st.subheader("Phase Breakdown")
                for phase, stats in summary["phase_breakdown"].items():
                    with st.expander(f"📍 {phase.replace('_', ' ').title()}"):
                        col1, col2 = st.columns(2)
                        col1.metric("Executions", stats["count"])
                        col1.metric("Avg Duration", f"{stats['avg_duration']}s")
                        col2.metric("Success Rate", f"{stats['success_rate']*100:.1f}%")
    
    # View Logs
    if st.button("📄 View Recent Logs"):
        log_dir = pathlib.Path("logs")
        if log_dir.exists():
            log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
            if log_files:
                with open(log_files[0], 'r') as f:
                    lines = f.readlines()
                    st.text_area("Recent Log Entries", "".join(lines[-50:]), height=300)
            else:
                st.info("No log files found yet")
        else:
            st.info("Logs directory not created yet")

st.title("🛡️ Claim Compass: Agent Orchestrator")
st.markdown("**Upload a bill. The AI Team (Vision → Researcher → Writer) will handle the rest.**")

# Create tabs for main functionality and metrics
tab1, tab2 = st.tabs(["📤 Process Claim", "📊 System Metrics"])

with tab1:
    # File Uploader
    uploaded_file = st.file_uploader("Upload Medical Bill", type=["jpg", "png", "jpeg"])

    if uploaded_file:
        # Display Image
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.image(uploaded_file, caption="Uploaded Bill", use_column_width=True)
        
        with col2:
            if st.button("🚀 Start Appeal Process", use_container_width=True):
                # 1. Save File
                temp_filename = f"temp_bill{pathlib.Path(uploaded_file.name).suffix}"
                with open(temp_filename, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                    
                # 2. VISION AGENT (The "Eyes")
                with st.status("👀 Vision Agent: Reading bill...", expanded=True) as status:
                    vision = VisionAgent(PROJECT_ID, Config.VISION_LOCATION)
                    bill_json_text = vision.analyze_bill(temp_filename)
                    st.caption("Extracted Data:")
                    st.code(bill_json_text, language="text")
                    status.update(label="✅ Vision Complete", state="complete", expanded=False)

                # 3. COORDINATOR TEAM (The "Brains")
                with st.status("🤖 Coordinator Agent: Orchestrating team...", expanded=True) as status:
                    st.write("🔍 Specialist 1: Analyzing Internal Policy...")
                    st.write("🌍 Specialist 2: Researching Laws & Precedents...")
                    st.write("✍️  Specialist 3: Drafting Appeal Letter...")
                    
                    team = CoordinatorTeam(PROJECT_ID, LOCATION, DATA_STORE_ID)
                    
                    final_letter = team.run(
                        bill_json_text, 
                        patient_name=patient_name, 
                        patient_zip=patient_zip, 
                        context=additional_context
                    )
                    
                    status.update(label="✅ Workflow Complete", state="complete", expanded=False)

                # 4. OUTPUT
                st.subheader("📄 Final Appeal Letter")
                st.text_area("Draft", value=final_letter, height=600)
                
                # Download button
                st.download_button(
                    label="📥 Download Letter",
                    data=final_letter,
                    file_name=f"appeal_letter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
                
                # Show recent metrics
                obs = get_observability_manager()
                latest_metrics = obs.metrics[-3:] if obs.metrics else []
                
                if latest_metrics:
                    st.divider()
                    st.subheader("⚡ Performance Metrics (This Run)")
                    
                    metrics_cols = st.columns(len(latest_metrics))
                    for i, metric in enumerate(latest_metrics):
                        with metrics_cols[i]:
                            st.metric(
                                label=metric.phase.replace('_', ' ').title(),
                                value=f"{metric.duration_seconds}s",
                                delta="Success" if metric.success else "Failed",
                                delta_color="normal" if metric.success else "inverse"
                            )

with tab2:
    st.header("📊 System Performance Metrics")
    
    # Load all evaluation results
    eval_dir = pathlib.Path("evaluation_results")
    if eval_dir.exists():
        eval_files = sorted(eval_dir.glob("evaluation_*.json"), key=os.path.getmtime, reverse=True)
        
        if eval_files:
            st.subheader("📈 Recent Evaluation Results")
            
            # Load and display most recent evaluation
            with open(eval_files[0], 'r') as f:
                latest_eval = json.load(f)
            
            st.caption(f"Last evaluated: {latest_eval.get('timestamp', 'Unknown')}")
            
            # Summary metrics
            results = latest_eval.get("results", [])
            if results:
                avg_overall = sum(r["overall_score"] for r in results) / len(results)
                avg_vision = sum(r["vision_score"] for r in results) / len(results)
                avg_research = sum(r["research_score"] for r in results) / len(results)
                avg_letter = sum(r["letter_score"] for r in results) / len(results)
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Overall", f"{avg_overall*100:.1f}%")
                col2.metric("Vision", f"{avg_vision*100:.1f}%")
                col3.metric("Research", f"{avg_research*100:.1f}%")
                col4.metric("Letter", f"{avg_letter*100:.1f}%")
                
                # Detailed results
                st.subheader("📋 Test Case Results")
                for result in results:
                    status_emoji = "✅" if result["success"] else "❌"
                    with st.expander(f"{status_emoji} {result['case_id']} - Overall: {result['overall_score']*100:.1f}%"):
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Vision", f"{result['vision_score']*100:.1f}%")
                        col2.metric("Research", f"{result['research_score']*100:.1f}%")
                        col3.metric("Letter", f"{result['letter_score']*100:.1f}%")
                        
                        if result.get("vision_errors"):
                            st.error("Vision Errors:")
                            for error in result["vision_errors"]:
                                st.write(f"- {error}")
                        
                        if result.get("research_errors"):
                            st.warning("Research Issues:")
                            for error in result["research_errors"]:
                                st.write(f"- {error}")
                        
                        if result.get("letter_errors"):
                            st.warning("Letter Issues:")
                            for error in result["letter_errors"]:
                                st.write(f"- {error}")
            
            # Historical trend (if multiple evaluations exist)
            if len(eval_files) > 1:
                st.subheader("📉 Historical Performance")
                
                historical_data = []
                for eval_file in eval_files[:10]:  # Last 10 evaluations
                    with open(eval_file, 'r') as f:
                        eval_data = json.load(f)
                    results = eval_data.get("results", [])
                    if results:
                        avg_score = sum(r["overall_score"] for r in results) / len(results)
                        historical_data.append({
                            "timestamp": eval_data.get("timestamp", "Unknown"),
                            "score": avg_score
                        })
                
                if historical_data:
                    st.line_chart([d["score"] for d in reversed(historical_data)])
        else:
            st.info("No evaluation results yet. Run `python run_evaluation.py` to generate evaluation data.")
    else:
        st.info("No evaluation results directory. Run `python run_evaluation.py` to create evaluations.")
    
    # System logs
    st.divider()
    st.subheader("📜 System Logs")
    
    log_dir = pathlib.Path("logs")
    if log_dir.exists():
        log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
        
        if log_files:
            selected_log = st.selectbox(
                "Select log file",
                options=log_files,
                format_func=lambda x: f"{x.name} ({datetime.fromtimestamp(x.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')})"
            )
            
            if selected_log:
                with open(selected_log, 'r') as f:
                    log_content = f.read()
                
                # Filter options
                col1, col2 = st.columns([3, 1])
                with col1:
                    filter_text = st.text_input("Filter logs (regex)", placeholder="e.g. ERROR|WARNING")
                with col2:
                    line_limit = st.number_input("Max lines", value=100, min_value=10, max_value=1000)
                
                # Display logs
                lines = log_content.split('\n')
                
                if filter_text:
                    import re
                    pattern = re.compile(filter_text)
                    lines = [line for line in lines if pattern.search(line)]
                
                st.code('\n'.join(lines[-line_limit:]), language="log")
        else:
            st.info("No log files found")
    else:
        st.info("Logs directory not created yet")

# Footer
st.divider()
st.caption("🛡️ Claim Compass v1.0 | Powered by Google Vertex AI & Gemini | Built for AI Agent Workshop")