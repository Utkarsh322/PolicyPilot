import re
import numpy as np
from typing import List, Dict, Tuple, Any
from langchain_core.documents import Document

try:
    from src import config
except ImportError:
    import config

# Try to import Chroma and HuggingFaceEmbeddings
try:
    from langchain_chroma import Chroma
except ImportError:
    try:
        from langchain_community.vectorstores import Chroma
    except ImportError:
        Chroma = None

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
except ImportError:
    HuggingFaceEmbeddings = None

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None


def preprocess_text(text: str) -> List[str]:
    """
    Cleans and tokenizes text for BM25.
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = text.split()
    return tokens


class HybridRetriever:
    def __init__(self):
        self.db_dir = str(config.DB_DIR)
        self.vector_store = None
        self.bm25 = None
        self.all_documents: List[Document] = []
        self.embeddings = None
        self.initialize_retriever()

    def initialize_retriever(self):
        """
        Loads ChromaDB and initializes BM25 from the indexed chunks.
        """
        if Chroma is None or HuggingFaceEmbeddings is None:
            print("Required libraries for retrieval are not available.")
            return

        try:
            # 1. Load Embeddings
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'}
            )
            
            # 2. Load Vector DB
            self.vector_store = Chroma(
                persist_directory=self.db_dir,
                embedding_function=self.embeddings
            )
            
            # 3. Retrieve all documents to initialize BM25
            # We fetch all data from Chroma directly to keep them in sync
            db_data = self.vector_store.get()
            if db_data and db_data.get('documents'):
                self.all_documents = []
                for doc_text, metadata in zip(db_data['documents'], db_data['metadatas']):
                    self.all_documents.append(
                        Document(page_content=doc_text, metadata=metadata)
                    )
                
                # 4. Initialize BM25 with tokenized documents
                if BM25Okapi is not None and self.all_documents:
                    tokenized_corpus = [preprocess_text(doc.page_content) for doc in self.all_documents]
                    self.bm25 = BM25Okapi(tokenized_corpus)
                    print(f"Retriever initialized with {len(self.all_documents)} chunks.")
                else:
                    print("BM25Okapi could not be initialized (no documents or library missing).")
            else:
                print("Vector database is empty. Please run ingestion first.")
        except Exception as e:
            print(f"Error initializing retriever: {e}")

    def semantic_search(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        """
        Performs semantic search using ChromaDB.
        Returns a list of (Document, similarity_score) tuples.
        """
        if not self.vector_store:
            return []
            
        try:
            # similarity_search_with_score returns L2 distance (lower is closer)
            results = self.vector_store.similarity_search_with_score(query, k=k)
            
            processed_results = []
            for doc, distance in results:
                # Convert L2 distance to a similarity score between 0 and 1
                # L2 distance for normalized embeddings lies in [0, 2] (or [0, 4] for squared)
                # Let's map it safely. If distance is close to 0, similarity is near 1.0.
                similarity = 1.0 / (1.0 + distance)
                processed_results.append((doc, float(similarity)))
                
            return processed_results
        except Exception as e:
            print(f"Error during semantic search: {e}")
            return []

    def keyword_search(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        """
        Performs keyword search using BM25.
        Returns a list of (Document, score) tuples.
        """
        if not self.bm25 or not self.all_documents:
            return []
            
        try:
            query_tokens = preprocess_text(query)
            scores = self.bm25.get_scores(query_tokens)
            
            # Pair documents with their scores
            doc_scores = list(zip(self.all_documents, scores))
            
            # Sort by score descending
            doc_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Take top k
            top_k_results = doc_scores[:k]
            
            # Normalize BM25 scores to [0, 1] relative to the max score in this run
            max_score = max(scores) if len(scores) > 0 else 0
            
            normalized_results = []
            for doc, score in top_k_results:
                norm_score = (score / max_score) if max_score > 0 else 0.0
                normalized_results.append((doc, float(norm_score)))
                
            return normalized_results
        except Exception as e:
            print(f"Error during keyword search: {e}")
            return []

    def hybrid_search(self, query: str, k: int = 5, 
                      w_semantic: float = None, 
                      w_keyword: float = None) -> List[Tuple[Document, float]]:
        """
        Combines semantic and keyword search scores linearly.
        """
        if w_semantic is None:
            w_semantic = config.HYBRID_SEMANTIC_WEIGHT
        if w_keyword is None:
            w_keyword = config.HYBRID_KEYWORD_WEIGHT

        # If BM25 is not initialized, fallback to semantic search only
        if not self.bm25:
            return self.semantic_search(query, k=k)

        # Retrieve more than k candidates from each to allow proper merging
        candidate_count = max(k * 2, 10)
        
        semantic_results = self.semantic_search(query, k=candidate_count)
        keyword_results = self.keyword_search(query, k=candidate_count)
        
        # Merge scores by document text/content + source page identifier
        # We use a unique key for matching: (source_file, page_num, content_hash)
        merged_scores: Dict[str, Dict[str, Any]] = {}
        
        # Add semantic results
        for doc, score in semantic_results:
            key = f"{doc.metadata.get('source', '')}_{doc.metadata.get('page', 0)}_{hash(doc.page_content)}"
            merged_scores[key] = {
                "doc": doc,
                "semantic_score": score,
                "keyword_score": 0.0
            }
            
        # Add keyword results
        for doc, score in keyword_results:
            key = f"{doc.metadata.get('source', '')}_{doc.metadata.get('page', 0)}_{hash(doc.page_content)}"
            if key in merged_scores:
                merged_scores[key]["keyword_score"] = score
            else:
                merged_scores[key] = {
                    "doc": doc,
                    "semantic_score": 0.0,
                    "keyword_score": score
                }
                
        # Calculate hybrid score
        hybrid_results = []
        for key, info in merged_scores.items():
            h_score = (w_semantic * info["semantic_score"]) + (w_keyword * info["keyword_score"])
            hybrid_results.append((info["doc"], float(h_score)))
            
        # Sort and return top k
        hybrid_results.sort(key=lambda x: x[1], reverse=True)
        return hybrid_results[:k]

    def retrieve(self, query: str, k: int = 4, search_mode: str = "hybrid", 
                 threshold: float = None) -> Tuple[List[Document], float, bool]:
        """
        Performs retrieval, applies confidence threshold, and returns results.
        Returns:
            - List of retrieved documents
            - The confidence score of the best match
            - A boolean flag indicating if it passed the threshold
        """
        if threshold is None:
            threshold = config.CONFIDENCE_THRESHOLD

        if search_mode == "semantic":
            results = self.semantic_search(query, k=k)
        elif search_mode == "keyword":
            results = self.keyword_search(query, k=k)
        else:
            results = self.hybrid_search(query, k=k)
            
        if not results:
            return [], 0.0, False
            
        # The best match determines the confidence score of the query
        best_score = results[0][1]
        passed = best_score >= threshold
        
        retrieved_docs = [doc for doc, score in results]
        
        # Debug printing
        print(f"Retrieve query: '{query}' | Mode: {search_mode} | Best score: {best_score:.4f} | Passed: {passed}")
        
        return retrieved_docs, best_score, passed


if __name__ == "__main__":
    # Test execution
    retriever = HybridRetriever()
    if retriever.all_documents:
        docs, score, passed = retriever.retrieve("how many days off do I get?", search_mode="hybrid")
        print(f"Retrieved {len(docs)} docs, score={score}, passed={passed}")
    else:
        print("Vector store not initialized. Run ingest.py first.")
