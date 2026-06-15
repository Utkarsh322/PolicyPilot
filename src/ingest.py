import sys
import shutil
from pathlib import Path
import fitz  # PyMuPDF
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Import configuration
try:
    from src import config
except ImportError:
    import config

# Try to import Chroma from langchain_chroma, fallback to langchain_community
try:
    from langchain_chroma import Chroma
except ImportError:
    try:
        from langchain_community.vectorstores import Chroma
    except ImportError:
        Chroma = None

# Try to import HuggingFaceEmbeddings
try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
except ImportError:
    HuggingFaceEmbeddings = None


def extract_pages_from_pdf(pdf_path: Path):
    """
    Extracts text page-by-page from a PDF document using PyMuPDF.
    Returns a list of Document objects with text and metadata.
    """
    doc_name = pdf_path.name
    category = pdf_path.stem.split("_")[0]  # e.g., 'leave', 'it', 'expense'
    
    documents = []
    
    try:
        pdf_reader = fitz.open(pdf_path)
        for page_num in range(len(pdf_reader)):
            page = pdf_reader[page_num]
            text = page.get_text()
            
            # Create LangChain Document
            doc = Document(
                page_content=text,
                metadata={
                    "source": doc_name,
                    "page": page_num + 1,  # 1-indexed for reader convenience
                    "category": category,
                    "title": pdf_path.stem.replace("_", " ").title()
                }
            )
            documents.append(doc)
        pdf_reader.close()
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        
    return documents


def load_all_policies(policies_dir: Path):
    """
    Finds and processes all PDFs in the policies directory.
    """
    all_documents = []
    pdf_files = list(policies_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {policies_dir}.")
        return all_documents
        
    print(f"Found {len(pdf_files)} PDF files to process.")
    for pdf_path in pdf_files:
        print(f"Parsing {pdf_path.name}...")
        docs = extract_pages_from_pdf(pdf_path)
        all_documents.extend(docs)
        print(f"Extracted {len(docs)} pages.")
        
    return all_documents


def ingest_documents():
    """
    Main function to clear DB, parse PDFs, chunk text, embed and store in ChromaDB.
    """
    policies_dir = Path(config.POLICIES_DIR)
    db_dir = Path(config.DB_DIR)
    
    # 1. Extract text from PDFs
    documents = load_all_policies(policies_dir)
    if not documents:
        print("No documents were loaded. Ingestion halted.")
        return False
        
    print(f"Total pages extracted: {len(documents)}")
    
    # 2. Chunk documents
    print(f"Splitting documents with chunk size {config.CHUNK_SIZE} and overlap {config.CHUNK_OVERLAP}...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        length_function=len,
        add_start_index=True
    )
    
    chunks = splitter.split_documents(documents)
    print(f"Created {len(chunks)} chunks from {len(documents)} pages.")
    
    # 3. Initialize embedding model
    print("Loading HuggingFace Embeddings model (sentence-transformers/all-MiniLM-L6-v2)...")
    if HuggingFaceEmbeddings is None:
        print("CRITICAL ERROR: HuggingFaceEmbeddings is not installed. Run pip install langchain-community sentence-transformers.")
        return False
        
    try:
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
    except Exception as e:
        print(f"Error loading embedding model: {e}")
        return False
        
    # 4. Initialize and populate Chroma DB
    if Chroma is None:
        print("CRITICAL ERROR: Chroma is not installed. Run pip install langchain-chroma or chromadb.")
        return False
        
    print(f"Indexing {len(chunks)} chunks into ChromaDB at {db_dir}...")
    try:
        # Check if database folder already exists and has files
        if db_dir.exists() and any(db_dir.iterdir()):
            print("ChromaDB directory exists and is not empty. Clearing existing collection contents...")
            vector_store = Chroma(
                persist_directory=str(db_dir),
                embedding_function=embeddings
            )
            # Fetch and delete all existing IDs
            db_data = vector_store.get()
            if db_data and db_data.get('ids'):
                print(f"Deleting {len(db_data['ids'])} existing chunks...")
                vector_store.delete(ids=db_data['ids'])
                print("All old chunks successfully deleted.")
            
            # Add new chunks to the same store
            if chunks:
                vector_store.add_documents(chunks)
        else:
            # Create a brand new persistent store
            db_dir.mkdir(parents=True, exist_ok=True)
            vector_store = Chroma.from_documents(
                documents=chunks,
                embedding=embeddings,
                persist_directory=str(db_dir)
            )
            
        # Persist if supported
        if hasattr(vector_store, 'persist'):
            vector_store.persist()
            
        print("Indexing completed successfully!")
        return True
    except Exception as e:
        print(f"Error during indexing in ChromaDB: {e}")
        return False



if __name__ == "__main__":
    success = ingest_documents()
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
