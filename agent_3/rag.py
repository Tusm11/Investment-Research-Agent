import os

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "agent_1", ".env"))


# ======================
# CONFIG
# ======================

os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")
os.environ["HF_TOKEN"] = os.getenv("HF_TOKEN", "")

pdf_folder = os.path.dirname(os.path.abspath(__file__))
db_path = "chroma_db"

EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"


# ======================
# EMBEDDINGS
# ======================

_vector_store = None
_retriever = None
_llm = None
_prompt = None
_rag_chain = None


def _init_rag():
    """Initialize embeddings, FAISS vector store, retriever and chains lazily."""
    global _vector_store, _retriever, _llm, _prompt, _rag_chain

    if _rag_chain is not None:
        return

    try:
        from langchain_community.document_loaders import PyPDFLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_community.vectorstores import Chroma
        from langchain_groq import ChatGroq
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_classic.chains.combine_documents import create_stuff_documents_chain
        from langchain_classic.chains import create_retrieval_chain
    except Exception as exc:
        print(f"RAG dependencies unavailable: {exc}")
        _rag_chain = None
        return

    # embeddings (may download model on first use)
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    # load existing index or build from PDFs using Chroma (avoids FAISS build delays)
    if os.path.exists(db_path):
        print("Loading Chroma index...")
        _vector_store = Chroma(persist_directory=db_path, embedding_function=embeddings)
    else:
        print("Building Chroma from PDFs... (this may take time)")
        all_docs = []
        for file in os.listdir(pdf_folder):
            if file.endswith(".pdf"):
                loader = PyPDFLoader(os.path.join(pdf_folder, file))
                docs = loader.load()
                for d in docs:
                    d.metadata["source"] = file
                all_docs.extend(docs)

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = splitter.split_documents(all_docs)

        _vector_store = Chroma.from_documents(chunks, embeddings, persist_directory=db_path)
        try:
            _vector_store.persist()
        except Exception:
            # some Chroma integrations use save_local/persist naming; ignore if not available
            pass
        print("Chroma saved.")

    _retriever = _vector_store.as_retriever(search_kwargs={"k": 8})

    # LLM and prompt
    _llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.2)

    system_prompt = """
You are Agent 3: Indian Market Analysis Engine.

Rules:
- Use ONLY provided context.
- Do NOT use external knowledge.
- If missing, say "Not mentioned in documents".

Format:

Market Overview
Positive Factors
Risk Factors
Sector Impact
Important Metrics To Monitor
Conclusion

Context:
{context}
"""

    _prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{input}")])
    qa_chain = create_stuff_documents_chain(_llm, _prompt)
    _rag_chain = create_retrieval_chain(_retriever, qa_chain)


# ======================
# DEBUG VIEW
# ======================

def show_context(result):

    print("\n================ RETRIEVED CHUNKS ================\n")

    for i, doc in enumerate(result["context"]):

        print(f"Chunk {i+1} | Source: {doc.metadata.get('source')}")
        print(doc.page_content[:400])
        print("-" * 60)


# ======================
# RUN LOOP
# ======================

def query_rag(query_text):
    _init_rag()
    if _rag_chain is None:
        return "RAG analysis unavailable."
    try:
        result = _rag_chain.invoke({"input": query_text})
        return result.get("answer", "")
    except Exception as e:
        print(f"RAG failed: {e}")
        return "RAG analysis unavailable."
