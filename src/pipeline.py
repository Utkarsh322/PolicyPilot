from typing import List, Dict, Tuple, Any
from langchain_core.documents import Document

try:
    from src import config
    from src.retriever import HybridRetriever
    from src.generator import ResponseGenerator
except ImportError:
    import config
    from retriever import HybridRetriever
    from generator import ResponseGenerator


def reformulate_query_mock(query: str, history: List[Dict[str, str]]) -> str:
    """
    Rule-based pronoun resolution and query enrichment for the mock/local mode.
    If the current query has pronouns (it, they, that, this, the policy) and there is history,
    we extract keywords from the previous question and append them.
    """
    if not history:
        return query
        
    pronouns = {"it", "this", "they", "that", "them", "these", "he", "she", "its"}
    query_words = set(query.lower().split())
    
    # Check if query contains pronouns
    has_pronoun = any(p in query_words for p in pronouns)
    
    # Also check if it's a short question that implies continuity (e.g. "how to claim?", "what about laptops?")
    is_short_followup = len(query.split()) < 5
    
    if has_pronoun or is_short_followup:
        # Find the last user message
        last_user_q = ""
        for msg in reversed(history):
            if msg["role"] == "user":
                last_user_q = msg["content"]
                break
                
        if last_user_q:
            # Extract key nouns/terms from the last question
            # Simple heuristic: remove common stopwords
            stopwords = {
                "what", "how", "why", "who", "when", "where", "is", "are", "do", "does", "did", 
                "can", "could", "would", "should", "the", "a", "an", "for", "to", "in", "on", 
                "at", "of", "and", "or", "but", "if", "you", "i", "me", "my", "we", "us", "our",
                "it", "this", "that", "these", "those"
            }
            last_q_words = [w.lower() for w in last_user_q.split() if w.lower() not in stopwords]
            
            # Take top 3 keywords and append them to help retrieval focus
            enrichment_keywords = " ".join(last_q_words[:3])
            enriched_query = f"{query} {enrichment_keywords}"
            print(f"Reformulated query (Mock): '{query}' -> '{enriched_query}'")
            return enriched_query
            
    return query


class RAGPipeline:
    def __init__(self):
        self.retriever = HybridRetriever()
        self.generator = ResponseGenerator()

    def reindex(self) -> bool:
        """
        Triggers re-indexing of documents and re-initializes retriever.
        """
        try:
            from src.ingest import ingest_documents
            success = ingest_documents()
            if success:
                # Reload retriever to pick up new database content
                self.retriever.initialize_retriever()
                return True
            return False
        except Exception as e:
            print(f"Error during re-indexing: {e}")
            return False

    def reformulate_query(self, query: str, history: List[Dict[str, str]] = None) -> str:
        """
        Reformulates follow-up queries using LLM or rule-based heuristics to ensure
        context is preserved.
        """
        if not history:
            return query
            
        # Use rule-based for mock mode, or if no LLM config is active
        if self.generator.provider not in ["openai", "gemini", "ollama"]:
            return reformulate_query_mock(query, history)
            
        # LLM-based reformulation prompt
        history_str = ""
        for msg in history[-4:]:  # last 4 turns
            history_str += f"{msg['role'].upper()}: {msg['content']}\n"
            
        prompt = (
            "Given the following conversation history and a follow-up question, "
            "rewrite the follow-up question to be a standalone search query that contains all necessary context. "
            "Do NOT answer the question. Only output the rewritten question.\n\n"
            f"Conversation History:\n{history_str}\n"
            f"Follow-up Question: {query}\n"
            "Standalone Question:"
        )

        try:
            # We can use the generator to get a fast response
            # Let's bypass retriever and send directly to model
            temp_doc = Document(page_content="Use this text for query rewrite.", metadata={"source": "system", "page": 1})
            result = self.generator.generate_response(prompt, [temp_doc])
            rewritten = result["answer"].strip()
            # Clean up potential LLM prefixing
            if ":" in rewritten and len(rewritten.split(":")[0]) < 15:
                rewritten = rewritten.split(":", 1)[1].strip()
            # Remove quotes
            rewritten = rewritten.strip('"\'')
            print(f"Reformulated query (LLM): '{query}' -> '{rewritten}'")
            return rewritten
        except Exception as e:
            print(f"LLM query reformulation failed: {e}. Falling back to rule-based.")
            return reformulate_query_mock(query, history)

    def answer_question(self, query: str, history: List[Dict[str, str]] = None, 
                        search_mode: str = "hybrid", threshold: float = None) -> Dict[str, Any]:
        """
        Processes a user question:
        1. Reformulate question using history
        2. Retrieve context documents
        3. Check confidence score against threshold
        4. Generate answer with citations
        """
        # 1. Reformulate query
        search_query = self.reformulate_query(query, history)
        
        # 2. Retrieve documents
        context_docs, best_score, passed = self.retriever.retrieve(
            query=search_query,
            search_mode=search_mode,
            threshold=threshold
        )
        
        # 3. Check confidence threshold
        if not passed:
            return {
                "answer": "I couldn't find this in our policy documents. Please contact HR/IT support directly.",
                "sources": [],
                "confidence_score": best_score,
                "passed_threshold": False,
                "search_query": search_query
            }
            
        # 4. Generate answer
        result = self.generator.generate_response(
            query=query,
            context_docs=context_docs,
            conversation_history=history
        )
        
        result.update({
            "confidence_score": best_score,
            "passed_threshold": True,
            "search_query": search_query
        })
        
        return result


if __name__ == "__main__":
    # Test pipeline
    pipeline = RAGPipeline()
    if pipeline.retriever.all_documents:
        response = pipeline.answer_question("What is the WFH policy details?")
        print(response["answer"])
        print("Sources:", response["sources"])
    else:
        print("Run ingest.py first to initialize index.")
