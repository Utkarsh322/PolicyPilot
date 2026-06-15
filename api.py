import os
import shutil
from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from pathlib import Path

# Import pipeline
try:
    from src.pipeline import RAGPipeline
    from src import config
except ImportError:
    from pipeline import RAGPipeline
    import config

app = FastAPI(
    title="PolicyPilot API Backend",
    description="FastAPI Backend for PolicyPilot enterprise knowledge RAG assistant.",
    version="1.0.0"
)

# Global pipeline instance
pipeline = None

def get_pipeline():
    global pipeline
    if pipeline is None:
        print("Initializing RAG Pipeline on backend...")
        pipeline = RAGPipeline()
    return pipeline


# Pydantic Schemas
class Message(BaseModel):
    role: str = Field(..., description="Role of the message author: 'user' or 'assistant'")
    content: str = Field(..., description="The text content of the message")

class QueryRequest(BaseModel):
    question: str = Field(..., description="The user question to query the policy corpus")
    history: Optional[List[Dict[str, str]]] = Field(default=[], description="The conversation history of previous turns")
    search_mode: Optional[str] = Field(default="hybrid", description="Retrieval mode: 'semantic', 'keyword', or 'hybrid'")
    threshold: Optional[float] = Field(default=None, description="Custom confidence threshold filter")

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    confidence_score: float
    passed_threshold: bool
    search_query: str

class ReindexResponse(BaseModel):
    success: bool
    message: str

class StatusResponse(BaseModel):
    document_count: int
    documents: List[str]
    chunk_count: int
    llm_provider: str
    confidence_threshold: float
    hybrid_weights: Dict[str, float]


@app.on_event("startup")
def startup_event():
    # Warm up the pipeline on start
    get_pipeline()


@app.get("/")
def read_root():
    return {"status": "online", "message": "Welcome to the PolicyPilot API Server. Use /docs for API documentation."}


@app.post("/query", response_model=QueryResponse)
def query_policies(request: QueryRequest):
    """
    Submit a user question to the RAG pipeline.
    """
    pipe = get_pipeline()
    try:
        # Resolve history format (convert back to list of dicts)
        history_dicts = request.history if request.history else []
        
        result = pipe.answer_question(
            query=request.question,
            history=history_dicts,
            search_mode=request.search_mode,
            threshold=request.threshold
        )
        return QueryResponse(**result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pipeline Query Error: {str(e)}")


@app.post("/reindex", response_model=ReindexResponse)
def reindex_policies():
    """
    Reparse policies folder and rebuild the ChromaDB and BM25 index.
    """
    pipe = get_pipeline()
    try:
        success = pipe.reindex()
        if success:
            return ReindexResponse(success=True, message="Document library indexed successfully.")
        else:
            return ReindexResponse(success=False, message="Indexing failed. Check logs.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reindexing Error: {str(e)}")


@app.get("/status", response_model=StatusResponse)
def get_system_status():
    """
    Returns statistics and configuration about the current index and LLM settings.
    """
    pipe = get_pipeline()
    
    # List actual PDF documents in policy folder
    policies_dir = Path(config.POLICIES_DIR)
    pdf_docs = [f.name for f in policies_dir.glob("*.pdf")] if policies_dir.exists() else []
    
    # Retrieve details from retriever
    chunk_count = len(pipe.retriever.all_documents)
    
    return StatusResponse(
        document_count=len(pdf_docs),
        documents=pdf_docs,
        chunk_count=chunk_count,
        llm_provider=pipe.generator.provider,
        confidence_threshold=config.CONFIDENCE_THRESHOLD,
        hybrid_weights={
            "semantic_weight": config.HYBRID_SEMANTIC_WEIGHT,
            "keyword_weight": config.HYBRID_KEYWORD_WEIGHT
        }
    )


@app.post("/upload", response_model=ReindexResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a new policy PDF and trigger database re-indexing.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    policies_dir = Path(config.POLICIES_DIR)
    file_path = policies_dir / file.filename
    
    try:
        # Save file to policies directory
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Trigger reindex
        pipe = get_pipeline()
        success = pipe.reindex()
        if success:
            return ReindexResponse(success=True, message=f"Document '{file.filename}' uploaded and indexed successfully.")
        else:
            return ReindexResponse(success=False, message=f"Document '{file.filename}' saved but indexing failed. Check backend logs.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")


@app.delete("/document/{filename}", response_model=ReindexResponse)
def delete_document(filename: str):
    """
    Deletes a policy PDF from the library and rebuilds the index.
    """
    policies_dir = Path(config.POLICIES_DIR)
    file_path = policies_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")
        
    try:
        # Delete file
        file_path.unlink()
        
        # Trigger reindex to remove chunks from ChromaDB and BM25 index
        pipe = get_pipeline()
        success = pipe.reindex()
        if success:
            return ReindexResponse(success=True, message=f"Document '{filename}' deleted and database re-indexed successfully.")
        else:
            return ReindexResponse(success=False, message=f"Document '{filename}' deleted from filesystem but database re-indexing failed.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
