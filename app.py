import streamlit as st
import time
import os
import pathlib
from agents.researcher import ResearcherAgent
from agents.vision import VisionAgent
from agents.writer import WriterAgent

from config import Config

# --- CONFIGURATION ---
PROJECT_ID = Config.PROJECT_ID
DATA_STORE_ID = Config.DATA_STORE_ID
LOCATION = Config.LOCATION

# Page Config
st.set_page_config(page_title="Claim Compass", page_icon="🛡️", layout="wide")

# --- HEADER ---
st.title("🛡️ Claim Compass")
st.markdown("""
**AI Agent Team for Patient Advocacy**
*Upload a medical bill, and our agents will analyze it, check your policy coverage, and draft an appeal letter.*
""")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Configuration")
    st.success("✅ Agents Online")
    st.info(f"Connected to Data Store:\n`{DATA_STORE_ID}`")
    
    # Hardcoded user context for the demo
    user_name = st.text_input("Patient Name", "")  # Remove default value
    user_zip = st.text_input("Zip Code", "")

# --- MAIN APP LOGIC ---

# 1. File Uploader
uploaded_file = st.file_uploader("Upload Medical Bill (Image)", type=["jpg", "png", "jpeg"])

if uploaded_file:
    # Display the bill
    col1, col2 = st.columns(2)
    with col1:
        st.image(uploaded_file, caption="Uploaded Bill", width="stretch")
    
    with col2:
        st.header("Agent Workflow")
        
        if st.button("🚀 Launch Appeal Agents", type="primary"):
            
            # SAVE FILE TEMPORARILY
            file_extension = pathlib.Path(uploaded_file.name).suffix
            temp_filename = f"temp_bill{file_extension}"
            with open(temp_filename, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # --- STEP 1: VISION AGENT ---
            with st.status("👀 Agent 1 (Visionary): Scanning bill...", expanded=True) as status:
                st.write("Initializing Gemini Vision...")
                vision = VisionAgent(PROJECT_ID, "us-central1") # Vision works best in us-central1
                bill_data = vision.analyze_bill(temp_filename)
                st.json({"extracted_data": bill_data})
                status.update(label="✅ Bill Extracted", state="complete", expanded=False)

			# --- STEP 2: RESEARCHER AGENT ---
            with st.status("🔎 Agent 2 (Researcher): Checking Policy & Laws...", expanded=True) as status:
                st.write("Connecting to Vertex AI Search...")
                researcher = ResearcherAgent(PROJECT_ID, LOCATION, DATA_STORE_ID)
                
                query = f"What are the coverage details, limits, and exclusions for these services: {bill_data}? Is there federal protection or specific policy limits?"
                
                evidence = researcher.search(query)
                st.markdown(f"**Evidence Found:**\n{evidence}")
                status.update(label="✅ Policy Analyzed", state="complete", expanded=False)

            # --- STEP 3: WRITER AGENT ---
            with st.status("✍️ Agent 3 (Advocate): Drafting Appeal...", expanded=True) as status:
                writer = WriterAgent(PROJECT_ID, "us-central1")
                appeal_letter = writer.draft_appeal(bill_data, evidence, user_name)
                status.update(label="✅ Letter Ready", state="complete", expanded=True)

            # --- RESULT ---
            st.subheader("📄 Final Appeal Letter")
            st.text_area("Copy your letter:", value=appeal_letter, height=400)
            
            st.download_button(
                label="📥 Download Letter as Text",
                data=appeal_letter,
                file_name=f"Appeal_Letter_{user_name}.txt",
                mime="text/plain"
            )