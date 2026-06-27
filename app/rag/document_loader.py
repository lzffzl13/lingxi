"""Document loader for RAG."""

from pathlib import Path
from typing import Optional

from app.utils.logger import logger


class DocumentLoader:
    """Load documents from various sources."""

    @staticmethod
    def load_text_file(file_path: str, metadata: Optional[dict] = None) -> dict:
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
        return DocumentLoader.load_text_file(file_path, metadata)

    @staticmethod
    def load_json_file(file_path: str, content_key: str = "content", metadata: Optional[dict] = None) -> dict:
        import json

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

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
        documents = []
        for index, faq in enumerate(faq_list):
            question = faq.get("question", "")
            answer = faq.get("answer", "")

            documents.append(
                {
                    "content": f"Question: {question}\nAnswer: {answer}",
                    "metadata": {
                        "source": "faq",
                        "faq_id": faq.get("id", index),
                        "question": question,
                        "answer": answer,
                        "category": faq.get("category", "general"),
                    },
                }
            )

        return documents

    @staticmethod
    def load_directory(directory: str, extensions: Optional[list[str]] = None) -> list[dict]:
        path = Path(directory)
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        extensions = extensions or [".txt", ".md", ".json"]
        documents = []

        for file_path in path.rglob("*"):
            if file_path.is_file() and file_path.suffix in extensions:
                try:
                    if file_path.suffix == ".json":
                        document = DocumentLoader.load_json_file(str(file_path))
                    else:
                        document = DocumentLoader.load_text_file(str(file_path))
                    documents.append(document)
                except Exception as exc:
                    logger.warning(f"Failed to load {file_path}: {exc}")

        logger.info(f"Loaded {len(documents)} documents from {directory}")
        return documents
