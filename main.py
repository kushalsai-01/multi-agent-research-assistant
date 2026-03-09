import sys
import os
import time
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

import config
from orchestrator import run_pipeline


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          🔬 AI Multi-Agent Research Assistant                ║
║          ─────────────────────────────────────               ║
║          4 LangChain Agents · LangGraph Pipeline             ║
║          Researcher → Analyst → Writer → Reviewer            ║
╚══════════════════════════════════════════════════════════════╝
    """)


def main():
    print_banner()

    # Check API key
    if not config.GROQ_API_KEY or config.GROQ_API_KEY.startswith("gsk_your"):
        print("❌ ERROR: GROQ_API_KEY not set!")
        print("   → Copy .env.example to .env and add your key")
        print("   → Or set GROQ_API_KEY environment variable")
        print("   → Get a free key at: https://console.groq.com")
        sys.exit(1)
    
    # Get topic
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
    else:
        topic = input("\n📝 Enter your research topic: ").strip()
        if not topic:
            topic = "Latest trends in artificial intelligence 2025"
            print(f"   Using default: {topic}")
    
    print(f"\n🔍 Topic: {topic}")
    print(f"{'─'*60}")
    
    # Run pipeline
    start = time.time()
    state = run_pipeline(topic)
    elapsed = time.time() - start
    
    # Print results
    if state.get("error"):
        print(f"\n❌ Pipeline error: {state['error']}")
    else:
        print(f"\n{'═'*60}")
        print("📄 FINAL REPORT")
        print(f"{'═'*60}\n")
        print(state["final_report"])
    
    # Print log
    print(f"\n{'─'*60}")
    print("📋 Agent Pipeline Log:")
    for entry in state.get("log", []):
        print(f"   {entry}")
    print(f"\n⏱️  Total time: {elapsed:.1f}s")
    
    # Save report
    os.makedirs("output", exist_ok=True)
    fname = f"output/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(f"# Research Report: {topic}\n\n")
        f.write(f"*Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n---\n\n")
        f.write(state.get("final_report", state.get("report", "No report generated.")))
    print(f"💾 Report saved to: {fname}")


if __name__ == "__main__":
    main()
