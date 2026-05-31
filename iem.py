import os
import json
import streamlit as st
from google import genai
from google.genai import types

# Initialize the Gemini Client
# Assumes GEMINI_API_KEY is set in your environment variables
try:
    client = genai.Client()
except Exception:
    client = None

# Configure the page layout
st.set_page_config(page_title="Work Study Analyst", page_icon="⏱️", layout="centered")

# --- SESSION STATE INITIALIZATION ---
if "step" not in st.session_state:
    st.session_state.step = 1
if "task_name" not in st.session_state:
    st.session_state.task_name = ""
if "elements" not in st.session_state:
    st.session_state.elements = []

# --- STEP 1: INPUT TASK & AI GENERATION ---
if st.session_state.step == 1:
    st.title("⏱️ Work Study Time Estimator")
    st.write("Enter a task or work process. AI will break it down into micro-work elements and estimate observed times.")

    task_input = st.text_input("What task are you analyzing?", placeholder="e.g., Preparing instant noodles")

    if st.button("Generate Work Elements →", type="primary"):
        if not task_input.strip():
            st.error("Please enter a valid task name.")
        elif not client:
            st.error("Gemini API key not found. Please set the GEMINI_API_KEY environment variable.")
        else:
            with st.spinner("Analyzing process and generating time data..."):
                try:
                    # Construct a strict prompt for Industrial Engineering breakdown
                    prompt = f"""
                    You are an expert Industrial Engineering assistant. 
                    The user wants to perform a time study on the task: "{task_input}".
                    Break this down into 5 to 7 logical sequential micro-work elements with realistic observed times in seconds.
                    Return the response strictly adhering to the requested JSON structure.
                    """

                    # Force the model to output structured JSON matching our schema
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "element": types.Schema(type=types.Type.STRING),
                                        "time_sec": types.Schema(type=types.Type.INTEGER),
                                    },
                                    required=["element", "time_sec"],
                                ),
                            ),
                        ),
                    )
                    
                    # Parse and save to session state
                    st.session_state.elements = json.loads(response.text)
                    st.session_state.task_name = task_input
                    st.session_state.step = 2
                    st.rerun()

                except Exception as e:
                    st.error(f"An error occurred while calling the AI engine: {e}")

# --- STEP 2: REVIEW & EDIT ELEMENTS ---
elif st.session_state.step == 2:
    st.title("📋 Step 1: Review Work Elements")
    st.subheader(f"Task: {st.session_state.task_name}")
    st.write("Review and adjust the AI-generated observed times below if needed.")

    updated_elements = []
    total_observed_time = 0

    # Dynamically display editable inputs for each element
    for i, item in enumerate(st.session_state.elements):
        col1, col2 = st.columns([3, 1])
        with col1:
            # Display text cleanly
            st.markdown(f"**Element {i+1}:** {item['element']}")
        with col2:
            # Let the user fine-tune the time values
            new_time = st.number_input(
                "Time (sec)", 
                min_value=1, 
                value=int(item['time_sec']), 
                key=f"time_{i}",
                label_visibility="collapsed"
            )
            total_observed_time += new_time
        updated_elements.append({"element": item['element'], "time_sec": new_time})

    st.markdown("---")
    st.metric(label="Total Observed Time", value=f"{total_observed_time} seconds")

    # Navigation buttons
    col_back, col_next = st.columns([1, 1])
    with col_back:
        if st.button("← Back / Start Over"):
            st.session_state.step = 1
            st.rerun()
    with col_next:
        if st.button("Calculate Standard Time →", type="primary"):
            # Update session state with any modified times
            st.session_state.elements = updated_elements
            st.session_state.step = 3
            st.rerun()

# --- STEP 3: CALCULATIONS & SUMMARY ---
elif st.session_state.step == 3:
    st.title("🧮 Step 2: Allowances & Calculations")
    st.subheader(f"Analysis for: {st.session_state.task_name}")

    # Compute base observed time
    total_observed_time = sum(item['time_sec'] for item in st.session_state.elements)
    
    # 1. Normal Time (Assuming 100% rating factor as per your assignment framework)
    rating_factor = 1.0  
    normal_time = total_observed_time * rating_factor

    # 2. User input for Allowance
    st.markdown("### 1. Apply Allowances")
    allowance_pct = st.slider(
        "Select Allowance Percentage (for personal needs, fatigue, and delays):", 
        min_value=0, 
        max_value=50, 
        value=15, 
        step=1
    )

    # 3. Standard Time Calculation
    # Formula: Standard Time = Normal Time * (1 + Allowance/100)
    standard_time = normal_time * (1 + (allowance_pct / 100))

    st.markdown("---")
    st.markdown("### 2. Time Study Summary Calculations")

    # Display clean comparison layout
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(label="Total Observed Time", value=f"{total_observed_time} s")
    with c2:
        st.metric(label="Normal Time (100% Rating)", value=f"{normal_time:.1f} s")
    with c3:
        st.metric(label="Final Standard Time", value=f"{standard_time:.1f} s")

    # Display intuitive human-readable conclusion
    minutes = int(standard_time // 60)
    seconds = int(standard_time % 60)
    st.success(f"**Conclusion:** The standard time required to complete this task is **{standard_time:.1f} seconds** (~{minutes} mins, {seconds} secs).")

    # Navigation back to editing
    st.markdown("---")
    if st.button("← Back to Elements"):
        st.session_state.step = 2
        st.rerun()