import streamlit as st

# CRITICAL: st.set_page_config() MUST be the first Streamlit command
st.set_page_config(
    page_title="Match Scorecard Generator",
    layout="centered",
    page_icon="🏏",
    initial_sidebar_state="collapsed"
)

import os
import time
import sys
import asyncio

# Fix for Windows event loop policy
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from script import get_match_data, generate_pdf

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding-top: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #ff4b4b;
        color: white;
        font-weight: bold;
        padding: 0.75rem;
        border-radius: 0.5rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏏 Match Scorecard Generator")
st.markdown("Generate a professional PDF scorecard from a CricHeroes match URL.")

# Add helpful instructions
with st.expander("ℹ️ How to use", expanded=False):
    st.markdown("""
    1. Copy the full match URL from CricHeroes
    2. Paste it in the input field below
    3. (Optional) Override the Man of the Match
    4. Click "Generate Scorecard"
    5. Wait 30-60 seconds for processing
    6. Download your PDF!

    **Example URL:**
    `https://cricheroes.in/match/12345678`
    """)

# Input Form
with st.form("scorecard_form"):
    match_url = st.text_input(
        "Match URL",
        placeholder="https://cricheroes.in/scorecard/...",
        help="Paste the full CricHeroes match URL"
    )

    # Optional Override for Man of the Match
    man_of_the_match = st.text_input(
        "Man of the Match (Optional)",
        placeholder="Leave blank to extract automatically",
        help="Override the Man of the Match name if needed"
    )

    submitted = st.form_submit_button("🎯 Generate Scorecard", type="primary")

if submitted:
    if not match_url:
        st.error("❌ Please enter a valid Match URL.")
    else:
        # Create columns for better layout
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            # Progress Bar
            progress_bar = st.progress(0, text="Initializing...")
            status_text = st.empty()

            try:
                # Step 1: Connect
                status_text.info("🔗 Connecting to CricHeroes...")
                progress_bar.progress(10, text="Connecting...")
                time.sleep(0.5)

                # Step 2: Scrape data
                status_text.info("🕷️ Scraping match data (this may take 30-60 seconds)...")
                progress_bar.progress(20, text="Scraping data...")

                # Create an expander to show logs
                with st.expander("🔍 View scraping progress (for debugging)", expanded=True):
                    log_placeholder = st.empty()

                # Capture stderr to show progress
                import io
                from contextlib import redirect_stderr

                stderr_capture = io.StringIO()

                try:
                    with redirect_stderr(stderr_capture):
                        data_packet = get_match_data(match_url)

                    # Show captured logs
                    logs = stderr_capture.getvalue()
                    if logs:
                        log_placeholder.code(logs, language="log")

                except Exception as scrape_error:
                    logs = stderr_capture.getvalue()
                    if logs:
                        log_placeholder.code(logs, language="log")
                    raise scrape_error

                progress_bar.progress(60, text="Data extracted!")
                status_text.success("✅ Data extracted successfully!")
                time.sleep(0.5)

                # Step 3: Override Data if needed
                if man_of_the_match:
                    status_text.info(f"✏️ Overriding Man of the Match with: {man_of_the_match}")
                    if 'meta' not in data_packet:
                        data_packet['meta'] = {}
                    data_packet['meta']['man_of_the_match'] = man_of_the_match
                    time.sleep(0.5)

                # Step 4: Generate PDF
                status_text.info("📄 Generating PDF Report...")
                progress_bar.progress(70, text="Generating PDF...")

                output_filename = "scorecard.pdf"

                try:
                    generate_pdf(data_packet, output_filename)

                    if not os.path.exists(output_filename):
                        raise FileNotFoundError(f"PDF file was not created: {output_filename}")

                    file_size = os.path.getsize(output_filename)
                    if file_size == 0:
                        raise ValueError("PDF file is empty (0 bytes)")

                    print(f"✓ PDF generated successfully: {file_size} bytes")

                except Exception as pdf_error:
                    st.error(f"❌ PDF Generation Failed: {str(pdf_error)}")
                    raise

                progress_bar.progress(100, text="Complete!")
                status_text.success("✅ Scorecard generated successfully!")

                time.sleep(1)
                progress_bar.empty()
                status_text.empty()

                st.success("🎉 Your scorecard is ready!")

                # Show match info
                meta = data_packet.get('meta', {})
                if meta:
                    st.markdown("### Match Information")
                    info_col1, info_col2 = st.columns(2)
                    with info_col1:
                        st.metric("Tournament", meta.get('tournament_name', 'N/A'))
                        st.metric("Match Overs", meta.get('match_overs', 'N/A'))
                    with info_col2:
                        st.metric("Result", meta.get('result', 'N/A'))
                        st.metric("Man of the Match", meta.get('man_of_the_match', 'N/A'))

                st.markdown("---")

                if not os.path.exists(output_filename):
                    st.error(f"❌ PDF file not found: {output_filename}")
                    st.stop()

                with open(output_filename, "rb") as pdf_file:
                    pdf_bytes = pdf_file.read()

                if len(pdf_bytes) == 0:
                    st.error("❌ PDF file is empty")
                    st.stop()

                st.success(f"📄 PDF Ready! ({len(pdf_bytes):,} bytes)")

                download_col1, download_col2, download_col3 = st.columns([1, 2, 1])
                with download_col2:
                    st.download_button(
                        label="📥 Download Scorecard PDF",
                        data=pdf_bytes,
                        file_name="match_scorecard.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )

                st.info("💡 Tip: You can generate another scorecard by entering a new URL above!")

            except Exception as e:
                progress_bar.empty()
                status_text.empty()

                st.error(f"❌ An error occurred: {str(e)}")

                with st.expander("🔍 Error Details"):
                    st.code(str(e))
                    if 'data_packet' in locals():
                        st.json(data_packet)

                st.markdown("### 💡 Troubleshooting Tips:")
                st.markdown("""
                - Make sure the URL is correct and the match is completed
                - Try again in a few seconds (sometimes sites have rate limits)
                - Check if the match page is accessible in your browser
                - If using a mobile link, try the desktop version
                """)

                if os.path.exists("debug_screenshot.png"):
                    with st.expander("📸 Debug Screenshot"):
                        st.image("debug_screenshot.png")

                if os.path.exists("debug_page.html"):
                    with st.expander("📄 Debug HTML"):
                        with open("debug_page.html", "r") as f:
                            st.code(f.read()[:1000], language="html")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 0.9em;'>
    Built with ❤️ for cricket fans | Powered by Streamlit & Playwright
    </div>
    """,
    unsafe_allow_html=True
)