"""Formats RAG provenance for writer/reviewer prompts and the UI."""
def build_citation_context(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    refs = []
    for chunk in chunks:
        filename = chunk.get("metadata", {}).get("filename", "Document")
        refs.append(f"- [{filename} p.{chunk.get('page_number', '?')}]")
    return "## Available PDF citations\n" + "\n".join(dict.fromkeys(refs))
