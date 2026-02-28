"""
🌐 Streamlit UI for Multi-Agent Research Assistant
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run:  streamlit run app.py
"""

import os
import time
import streamlit as st
from datetime import datetime


st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""
<style>
    .stApp { max-width: 1200px; margin: 0 auto; }
    .agent-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 0.5rem;
    }
    .status-running { color: #fbbf24; font-weight: bold; }
    .status-done { color: #34d399; font-weight: bold; }
    .status-waiting { color: #9ca3af; }
</style>
""", unsafe_allow_html=True)



with st.sidebar:
    st.title("⚙️ Configuration")
    
    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        value=os.getenv("OPENAI_API_KEY", ""),
        help="Get your key at https://platform.openai.com/api-keys",
    )
    
    model = st.selectbox(
        "Model",
        ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        index=0,
        help="gpt-4o-mini is cheapest and fastest",
    )
    
    temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1)
    
    st.divider()
    
    st.markdown("### 🤖 Agent Pipeline")
    st.markdown("""
    1. 🔍 **Researcher** — Web search  
    2. 📊 **Analyst** — Extract insights  
    3. ✍️ **Writer** — Compose report  
    4. 🔎 **Reviewer** — Quality check  
    """)
    
    st.divider()
    st.caption("Built with LangChain + LangGraph + Streamlit")


if api_key:
    os.environ["OPENAI_API_KEY"] = api_key
    
    import config
    config.OPENAI_API_KEY = api_key
    config.OPENAI_MODEL = model
    config.LLM_TEMPERATURE = temperature
st.title("🔬 AI Multi-Agent Research Assistant")
st.markdown("Enter any topic and **4 AI agents** will research, analyze, write, and review a comprehensive report for you.")
col1, col2 = st.columns([4, 1])
with col1:
    query = st.text_area(
        "Research Topic",
        placeholder="e.g., Impact of artificial intelligence on healthcare in 2025",
        height=80,
    )
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    run_button = st.button("🚀 Run Research", type="primary", use_container_width=True)

with st.expander("💡 Example Topics"):
    examples = [
        "Latest breakthroughs in quantum computing 2025",
        "How is AI transforming education?",
        "Climate change impact on global food security",
        "The future of electric vehicles and battery technology",
        "Cybersecurity threats and trends in 2025",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}"):
            query = ex
            run_button = True

if run_button and query:
    if not api_key:
        st.error("⚠️ Please enter your OpenAI API key in the sidebar.")
        st.stop()
    
    # Import here so config is set first
    from orchestrator import run_pipeline
    from agents.researcher import run_researcher
    from agents.analyst import run_analyst
    from agents.writer import run_writer
    from agents.reviewer import run_reviewer
    
    # Progress tracking
    progress_bar = st.progress(0, text="Starting pipeline...")
    status_container = st.container()
    with status_container:
        with st.status("🔍 **Agent 1: Researcher** — Searching the web...", expanded=True) as s1:
            t0 = time.time()
            try:
                research_data = run_researcher(query)
                elapsed = time.time() - t0
                st.markdown(research_data[:2000] + ("..." if len(research_data) > 2000 else ""))
                s1.update(label=f"🔍 Researcher — Done ({elapsed:.1f}s)", state="complete")
            except Exception as e:
                st.error(f"Researcher failed: {e}")
                st.stop()
    progress_bar.progress(25, text="Research complete...")
    with status_container:
        with st.status("📊 **Agent 2: Analyst** — Extracting insights...", expanded=True) as s2:
            t0 = time.time()
            try:
                analysis = run_analyst(research_data, query)
                elapsed = time.time() - t0
                st.markdown(analysis[:2000] + ("..." if len(analysis) > 2000 else ""))
                s2.update(label=f"📊 Analyst — Done ({elapsed:.1f}s)", state="complete")
            except Exception as e:
                st.error(f"Analyst failed: {e}")
                st.stop()
    progress_bar.progress(50, text="Analysis complete...")
    with status_container:
        with st.status("✍️ **Agent 3: Writer** — Composing report...", expanded=True) as s3:
            t0 = time.time()
            try:
                report = run_writer(analysis, query)
                elapsed = time.time() - t0
                st.markdown(report[:2000] + ("..." if len(report) > 2000 else ""))
                s3.update(label=f"✍️ Writer — Done ({elapsed:.1f}s)", state="complete")
            except Exception as e:
                st.error(f"Writer failed: {e}")
                st.stop()
    progress_bar.progress(75, text="Report written...")
    with status_container:
        with st.status("🔎 **Agent 4: Reviewer** — Quality review...", expanded=True) as s4:
            t0 = time.time()
            try:
                review = run_reviewer(report, research_data, query)
                elapsed = time.time() - t0
                s4.update(label=f"🔎 Reviewer — Done ({elapsed:.1f}s)", state="complete")
            except Exception as e:
                st.error(f"Reviewer failed: {e}")
                st.stop()
    progress_bar.progress(100, text="✅ All agents complete!")
    st.divider()
    st.header("📄 Results")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📝 Final Report", "🔎 Review", "📊 Analysis", "🔍 Raw Research"
    ])
    
    with tab1:
        st.markdown(review)
        
        # Download button
        st.download_button(
            "⬇️ Download Report (Markdown)",
            data=review,
            file_name=f"research_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown",
        )
    
    with tab2:
        st.markdown(review)
    
    with tab3:
        st.markdown(analysis)
    
    with tab4:
        st.markdown(research_data)
    
    # Save to output/
    os.makedirs("output", exist_ok=True)
    fname = f"output/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(f"# Research Report: {query}\n\n")
        f.write(f"*Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n")
        f.write("---\n\n")
        f.write(review)
    st.success(f"Report saved to `{fname}`")

elif run_button and not query:
    st.warning("Please enter a research topic.")
