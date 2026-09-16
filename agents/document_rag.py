from rag import format_rag_context, retrieve_chunks

def run_document_rag(query: str, owner_id: str) -> tuple[str, list[dict]]:
    chunks = retrieve_chunks(query, owner_id)
    return format_rag_context(chunks), chunks
