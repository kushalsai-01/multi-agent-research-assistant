"""
LangSmith Evaluation — creates evaluation datasets and runs evals.

Features:
- Creates a LangSmith dataset of research topics with expected quality criteria
- Runs the agent pipeline against each example
- Uses LLM-as-judge to score output quality (relevance, depth, accuracy)
- Tracks scores over time in LangSmith dashboard

Requirements:
  LANGCHAIN_API_KEY in .env (get from smith.langchain.com)
  GROQ_API_KEY in .env
  LANGCHAIN_TRACING_V2=true in .env

Run:
  python langsmith_eval.py --create-dataset   # first time only
  python langsmith_eval.py --run              # run evaluation
  python langsmith_eval.py --both             # create + run
"""

import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import config  # noqa: loads .env


# ─── Evaluation Dataset ─────────────────────────────────────────────────────

EVAL_EXAMPLES = [
    {
        "input": "Latest breakthroughs in quantum computing 2025",
        "criteria": "Report should cover qubit improvements, error correction, major companies, real-world applications",
        "min_words": 500,
    },
    {
        "input": "How is AI transforming healthcare?",
        "criteria": "Report should mention diagnostics, drug discovery, clinical trials, FDA approval challenges",
        "min_words": 500,
    },
    {
        "input": "Future of electric vehicles and battery technology",
        "criteria": "Report should cover solid-state batteries, charging infrastructure, top manufacturers, range improvements",
        "min_words": 500,
    },
    {
        "input": "Cybersecurity threats and trends 2025",
        "criteria": "Report should address ransomware, AI-powered attacks, zero-trust models, recent major breaches",
        "min_words": 500,
    },
    {
        "input": "Impact of AI on global job markets",
        "criteria": "Report should discuss automation displacement, new job creation, reskilling programs, economic impact data",
        "min_words": 500,
    },
]

JUDGE_PROMPT = """You are an expert evaluator. Score the research report below on three dimensions.

Topic: {topic}
Expected criteria: {criteria}

Report to evaluate:
{report}

Score each dimension 1-10 and give a brief reason:
1. Relevance (does it directly address the topic and criteria?)
2. Depth (does it provide substantive analysis, not just surface-level facts?)
3. Accuracy (does it stick to verifiable facts, cite sources, avoid hallucinations?)

Respond ONLY in this format:
relevance: <score>
depth: <score>
accuracy: <score>
overall: <average>
reason: <one sentence>
"""


def create_dataset(client, dataset_name: str):
    """Create a LangSmith evaluation dataset."""
    try:
        # Check if dataset already exists
        datasets = list(client.list_datasets(dataset_name=dataset_name))
        if datasets:
            print(f"Dataset '{dataset_name}' already exists. Skipping creation.")
            return datasets[0]

        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description="AI Research Assistant — quality evaluation dataset",
        )
        for ex in EVAL_EXAMPLES:
            client.create_example(
                inputs={"query": ex["input"]},
                outputs={"criteria": ex["criteria"], "min_words": ex["min_words"]},
                dataset_id=dataset.id,
            )
        print(f"✅ Created dataset '{dataset_name}' with {len(EVAL_EXAMPLES)} examples")
        return dataset
    except Exception as e:
        print(f"❌ Failed to create dataset: {e}")
        return None


def evaluate_report(report: str, topic: str, criteria: str) -> dict:
    """Use LLM-as-judge to score a report."""
    from langchain_groq import ChatGroq
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    llm = ChatGroq(model=config.GROQ_MODEL, temperature=0.1, api_key=config.GROQ_API_KEY)
    prompt = ChatPromptTemplate.from_messages([
        ("human", JUDGE_PROMPT),
    ])
    chain = prompt | llm | StrOutputParser()

    result = chain.invoke({"topic": topic, "criteria": criteria, "report": report[:3000]})

    scores = {"relevance": 0, "depth": 0, "accuracy": 0, "overall": 0, "reason": ""}
    for line in result.strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip()
            if key in ("relevance", "depth", "accuracy", "overall"):
                try:
                    scores[key] = float(val)
                except ValueError:
                    pass
            elif key == "reason":
                scores["reason"] = val
    return scores


def run_evaluation(client, dataset_name: str, experiment_prefix: str = "v2-eval"):
    """Run the pipeline against the eval dataset and score results."""
    from agents.researcher import run_researcher
    from agents.analyst import run_analyst, analyst_to_str
    from agents.writer import run_writer, writer_to_markdown
    from agents.reviewer import run_reviewer

    datasets = list(client.list_datasets(dataset_name=dataset_name))
    if not datasets:
        print(f"❌ Dataset '{dataset_name}' not found. Run with --create-dataset first.")
        return

    examples = list(client.list_examples(dataset_id=datasets[0].id))
    print(f"\n🔬 Running evaluation against {len(examples)} examples...")
    print("=" * 60)

    all_scores = []
    for ex in examples:
        query = ex.inputs["query"]
        criteria = ex.outputs["criteria"]
        print(f"\n📋 Topic: {query}")

        try:
            # Run mini pipeline (skip reviewer to save rate limit budget)
            text, _ = run_researcher(query)
            analysis_obj = run_analyst(text, query)
            analysis_str = analyst_to_str(analysis_obj)
            writer_out = run_writer(analysis_str, query)
            report_md = writer_to_markdown(writer_out)

            # Score with LLM judge
            scores = evaluate_report(report_md, query, criteria)
            all_scores.append(scores["overall"])
            print(f"   Relevance: {scores['relevance']}/10 | Depth: {scores['depth']}/10 | Accuracy: {scores['accuracy']}/10")
            print(f"   Overall: {scores['overall']}/10 — {scores['reason']}")

            # Log to LangSmith
            try:
                run = client.create_run(
                    name=f"{experiment_prefix}/{query[:40]}",
                    run_type="chain",
                    inputs={"query": query},
                    outputs={
                        "report": report_md[:500],
                        "scores": scores,
                    },
                    tags=["eval", experiment_prefix],
                )
                client.update_run(run.id, end_time=True, outputs={"scores": scores})
            except Exception:
                pass  # LangSmith logging is optional

        except Exception as e:
            print(f"   ❌ Failed: {e}")

    if all_scores:
        avg = sum(all_scores) / len(all_scores)
        print(f"\n{'='*60}")
        print(f"📊 Average overall score: {avg:.1f}/10 across {len(all_scores)} reports")
        print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="LangSmith Evaluation for AI Research Assistant")
    parser.add_argument("--create-dataset", action="store_true", help="Create eval dataset in LangSmith")
    parser.add_argument("--run", action="store_true", help="Run evaluation against dataset")
    parser.add_argument("--both", action="store_true", help="Create dataset and run evaluation")
    args = parser.parse_args()

    if not config.LANGCHAIN_API_KEY:
        print("❌ LANGCHAIN_API_KEY not set in .env. Get yours at smith.langchain.com")
        sys.exit(1)

    try:
        from langsmith import Client
        client = Client(api_key=config.LANGCHAIN_API_KEY)
    except ImportError:
        print("❌ langsmith package not installed. Run: pip install langsmith")
        sys.exit(1)

    dataset_name = "research-assistant-eval-v2"

    if args.both or args.create_dataset:
        create_dataset(client, dataset_name)

    if args.both or args.run:
        run_evaluation(client, dataset_name)

    if not any([args.both, args.create_dataset, args.run]):
        parser.print_help()


if __name__ == "__main__":
    main()
