from langchain_core.tools import tool
from datetime import datetime
import os


@tool
def word_count(text: str) -> str:
    """Count the number of words in a text."""
    return f"Word count: {len(text.split())}"


@tool
def save_to_file(content: str, filename: str) -> str:
    """Save text content to a file in the output/ directory."""
    os.makedirs("output", exist_ok=True)
    filepath = os.path.join("output", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Saved to {filepath}"


@tool
def get_current_date() -> str:
    """Get the current date and time."""
    return datetime.now().strftime("%B %d, %Y at %I:%M %p")
