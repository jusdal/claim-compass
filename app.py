import os
import streamlit as st
import pathlib
import logging
from config import Config
from agents.vision import VisionAgent
from agents.coordinator import CoordinatorTeam

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

# --- SIDEBAR: Patient Details ---
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

st.title("🛡️ Claim Compass: Agent Orchestrator")
st.markdown("**Upload a bill. The AI Team (Vision -> Researcher -> Writer) will handle the rest.**")

# File Uploader
uploaded_file = st.file_uploader("Upload Medical Bill", type=["jpg", "png", "jpeg"])

if uploaded_file:
    # Display Image
    st.image(uploaded_file, caption="Uploaded Bill", width=400)
    
    if st.button("🚀 Start Appeal Process"):
        # 1. Save File
        temp_filename = f"temp_bill{pathlib.Path(uploaded_file.name).suffix}"
        with open(temp_filename, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        # 2. VISION AGENT (The "Eyes")
        with st.status("👀 Vision Agent: Reading bill...", expanded=True) as status:
            vision = VisionAgent(PROJECT_ID, Config.VISION_LOCATION)
            bill_json_text = vision.analyze_bill(temp_filename)
            st.caption("Extracted Data:")
            st.code(bill_json_text, language="json")
            status.update(label="✅ Vision Complete", state="complete", expanded=False)

        # 3. COORDINATOR TEAM (The "Brains")
        with st.status("🤖 Coordinator Agent: Orchestrating team...", expanded=True) as status:
            st.write("🔍 Specialist 1: Analyzing Internal Policy...")
            st.write("🌍 Specialist 2: Researching Laws & Precedents...")
            st.write("✍️  Specialist 3: Drafting Appeal Letter...")
            
            team = CoordinatorTeam(PROJECT_ID, LOCATION, DATA_STORE_ID)
            
            # UPDATED: Pass the sidebar inputs to the coordinator
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