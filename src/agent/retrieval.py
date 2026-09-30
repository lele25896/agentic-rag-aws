"""PDFs -> chunks -> FAISS. Ported from ../LangChains/ingest.py (Chroma swapped for a file index)."""
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .llm import DATA_DIR, INDEX_DIR, get_embeddings


def build_index(chunk_size: int = 512, chunk_overlap: int = 64) -> int:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = []
    for pdf in sorted(DATA_DIR.glob("*.pdf")):
        for c in splitter.split_documents(PyMuPDFLoader(str(pdf)).load()):
            c.metadata = {"source": pdf.stem, "page": int(c.metadata.get("page", -1))}
            chunks.append(c)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    FAISS.from_documents(chunks, get_embeddings()).save_local(str(INDEX_DIR))
    return len(chunks)


_store = None


def get_store():
    global _store
    if _store is None:
        # pickle load is safe here: we wrote the index ourselves
        _store = FAISS.load_local(
            str(INDEX_DIR), get_embeddings(), allow_dangerous_deserialization=True
        )
    return _store


if __name__ == "__main__":
    print(f"indexed {build_index()} chunks -> {INDEX_DIR}")
