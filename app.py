
import streamlit as st
import os
import time
import sys
import asyncio
import subprocess

# Function to install playwright browsers
@st.cache_resource
def install_dependencies():
    print("Checking and installing dependencies...")
    try:
        import playwright
        print("Playwright is already installed.")
    except ImportError:
        print("Playwright not found. Installing dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "beautifulsoup4", "python-dotenv"], capture_output=True)

    print("Installing Playwright browsers...")
    try:
        process = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True, text=True)
        if process.returncode != 0:
             print(f"Error installing browsers: {process.stderr}")
        else:
             print("Browsers installed successfully.")
    except Exception as e:
        print(f"Exception installing browsers: {e}")

# Run installation
install_dependencies()

# Fix for Windows event loop policy
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from script import get_match_data, generate_pdf

# Set page config
st.set_page_config(page_title="Match Scorecard Generator", layout="centered", page_icon="🏏")

st.title("🏏 Match Scorecard Generator")
st.markdown("Generate a professional PDF scorecard from a CricHeroes match URL.")

# Input Form
with st.form("scorecard_form"):
    match_url = st.text_input("Match URL", placeholder="https://cricheroes.in/scorecard/...")
    
    # Optional Override for Man of the Match
    col1, col2 = st.columns(2)
    with col1:
        man_of_the_match = st.text_input("Man of the Match (Optional)", placeholder="Leave blank to extract automatically")
    
    submitted = st.form_submit_button("Generate Scorecard")

if submitted:
    if not match_url:
        st.error("Please enter a valid Match URL.")
    else:
        # Progress Bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Step 1: Scrum
            status_text.text("Connecting to CricHeroes...")
            progress_bar.progress(10)
            
            # We call the scraping function
            # Note: This might take time, so we show a spinner
            with st.spinner("Scraping match data... (This may take a minute)"):
                data_packet = get_match_data(match_url)
                
            progress_bar.progress(50)
            status_text.text("Data extracted successfully!")
            
            # Step 2: Override Data if needed
            if man_of_the_match:
                st.info(f"Overriding Man of the Match with: {man_of_the_match}")
                # Ensure the meta dictionary exists
                if 'meta' not in data_packet:
                    data_packet['meta'] = {}
                data_packet['meta']['man_of_the_match'] = man_of_the_match
            
            # Step 3: Generate PDF
            status_text.text("Generating PDF Report...")
            progress_bar.progress(70)
            
            output_filename = "scorecard.pdf"
            # Ensure output directory exists or just write to current
            # script.py writes to current dir by default
            
            generate_pdf(data_packet, output_filename)
            
            progress_bar.progress(100)
            status_text.text("PDF Ready!")
            
            st.success("Scorecard generated successfully!")
            
            # PDF Display/Download
            with open(output_filename, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()
                
            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                st.download_button(
                    label="Download Scorecard PDF 📥",
                    data=pdf_bytes,
                    file_name="match_scorecard.pdf",
                    mime="application/pdf",
                    type="primary"
                )
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.code(data_packet if 'data_packet' in locals() else "No data extracted")
