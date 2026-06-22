"""Document loader for RAG."""

from pathlib import Path
from typing import Optional

from app.utils.logger import logger


class DocumentLoader:
    """Load documents from various sources.

    Supports:
    - Text files (.txt)
    - Markdown files (.md)
    - JSON files (.json)
    - FAQ data from knowledge base
    """

    @staticmethod
    def load_text_file(file_path: str, metadata: Optional[dict] = None) -> dict:
        """Load a text file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = path.read_text(encoding="utf-8")
        return {
            "content": content,
            "metadata": {
                "source": str(path),
                "filename": path.name,
                "file_type": path.suffix,
                **(metadata or {}),
            },
        }

    @staticmethod
    def load_markdown_file(file_path: str, metadata: Optional[dict] = None) -> dict:
        """Load a markdown file."""
        return DocumentLoader.load_text_file(file_path, metadata)

    @staticmethod
    def load_json_file(file_path: str, content_key: str = "content", metadata: Optional[dict] = None) -> dict:
        """Load a JSON file."""
        import json
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Extract content from JSON
        if isinstance(data, dict):
            content = data.get(content_key, json.dumps(data, ensure_ascii=False))
        elif isinstance(data, list):
            content = "\n".join(str(item) for item in data)
        else:
            content = str(data)

        return {
            "content": content,
            "metadata": {
                "source": str(path),
                "filename": path.name,
                "file_type": ".json",
                **(metadata or {}),
            },
        }

    @staticmethod
    def load_faq_data(faq_list: list[dict]) -> list[dict]:
        """Load FAQ data from knowledge base format.

        Args:
            faq_list: List of dicts with 'question' and 'answer' keys
        """
        documents = []
        for i, faq in enumerate(faq_list):
            question = faq.get("question", "")
            answer = faq.get("answer", "")
            content = f"问题：{question}\n答案：{answer}"

            documents.append({
                "content": content,
                "metadata": {
                    "source": "faq",
                    "faq_id": faq.get("id", i),
                    "question": question,
                    "category": faq.get("category", "general"),
                },
            })

        return documents

    @staticmethod
    def load_directory(directory: str, extensions: Optional[list[str]] = None) -> list[dict]:
        """Load all documents from a directory."""
        path = Path(directory)
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        extensions = extensions or [".txt", ".md", ".json"]
        documents = []

        for file_path in path.rglob("*"):
            if file_path.is_file() and file_path.suffix in extensions:
                try:
                    if file_path.suffix == ".json":
                        doc = DocumentLoader.load_json_file(str(file_path))
                    else:
                        doc = DocumentLoader.load_text_file(str(file_path))
                    documents.append(doc)
                except Exception as e:
                    logger.warning(f"Failed to load {file_path}: {e}")

        logger.info(f"Loaded {len(documents)} documents from {directory}")
        return documents
