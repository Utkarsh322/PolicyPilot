import os
import json
import sys
import time
import numpy as np
from typing import List, Dict, Any

try:
    from src import config
    from src.pipeline import RAGPipeline
except ImportError:
    import config
    from pipeline import RAGPipeline

# Helper function to compute cosine similarity
def cosine_similarity(v1, v2):
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return float(dot_product / (norm_v1 * norm_v2))


def calculate_token_f1(generated: str, expected: str) -> float:
    """
    Computes word-level F1 score of overlap between two texts.
    """
    import re
    def tokenize(text):
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        return text.split()

    gen_tokens = tokenize(generated)
    exp_tokens = tokenize(expected)
    
    if not gen_tokens or not exp_tokens:
        return 0.0
        
    gen_set = set(gen_tokens)
    exp_set = set(exp_tokens)
    
    shared = gen_set.intersection(exp_set)
    if not shared:
        return 0.0
        
    precision = len(shared) / len(gen_set)
    recall = len(shared) / len(exp_set)
    
    f1 = 2 * (precision * recall) / (precision + recall)
    return f1


def run_evaluation():
    print("Starting PolicyPilot Evaluation Pipeline...")
    
    # 1. Load pipeline
    pipeline = RAGPipeline()
    if not pipeline.retriever.all_documents:
        print("CRITICAL ERROR: Vector database is empty. Please run ingestion first using: python -m src.ingest")
        return False

    eval_qa_path = config.EVAL_QA_PATH
    if not eval_qa_path.exists():
        print(f"CRITICAL ERROR: Evaluation QA dataset not found at {eval_qa_path}")
        return False

    with open(eval_qa_path, 'r', encoding='utf-8') as f:
        qa_pairs = json.load(f)

    print(f"Loaded {len(qa_pairs)} evaluation QA pairs.")
    
    # Check if we can do embedding-based semantic similarity
    embed_model = pipeline.retriever.embeddings
    
    results = []
    total_questions = len(qa_pairs)
    retrieval_hits = 0
    total_f1 = 0.0
    total_similarity = 0.0
    
    print("\nEvaluating individual questions...")
    print("-" * 80)
    
    for item in qa_pairs:
        qid = item["id"]
        question = item["question"]
        expected_doc = item["document"]
        expected_page = item["page"]
        expected_ans = item["answer"]
        
        start_time = time.time()
        
        # 1. Retrieve chunks
        # We retrieve candidates using hybrid search (top 4)
        retrieved_docs, score, passed = pipeline.retriever.retrieve(
            query=question,
            k=4,
            search_mode="hybrid",
            threshold=0.0 # Force retrieve to evaluate retrieval quality even if low score
        )
        
        # Check if the expected document and page is in the retrieved chunks (Hit Rate)
        hit = False
        for doc in retrieved_docs:
            source = doc.metadata.get("source", "")
            page = doc.metadata.get("page", 0)
            if source.lower() == expected_doc.lower() and int(page) == int(expected_page):
                hit = True
                break
                
        if hit:
            retrieval_hits += 1
            
        # 2. Generate answer
        # Generate with pipeline (using history=None for evaluation)
        pipeline_output = pipeline.answer_question(
            query=question,
            search_mode="hybrid",
            threshold=0.0 # Don't trigger low-confidence fallback for metric checks
        )
        
        generated_ans = pipeline_output["answer"]
        latency = time.time() - start_time
        
        # 3. Compute Metrics
        token_f1 = calculate_token_f1(generated_ans, expected_ans)
        total_f1 += token_f1
        
        # Calculate semantic cosine similarity using sentence-transformer embeddings
        sem_sim = 0.0
        if embed_model:
            try:
                emb_gen = embed_model.embed_query(generated_ans)
                emb_exp = embed_model.embed_query(expected_ans)
                sem_sim = cosine_similarity(emb_gen, emb_exp)
                # Cap similarity to [0.0, 1.0] range
                sem_sim = max(0.0, min(1.0, sem_sim))
            except Exception as e:
                print(f"Error computing embedding similarity for Q{qid}: {e}")
        total_similarity += sem_sim
        
        results.append({
            "id": qid,
            "question": question,
            "expected_document": expected_doc,
            "expected_page": expected_page,
            "retrieval_hit": hit,
            "generated_answer": generated_ans,
            "expected_answer": expected_ans,
            "token_f1": round(token_f1, 4),
            "semantic_similarity": round(sem_sim, 4),
            "latency_sec": round(latency, 2)
        })
        
        status_symbol = "OK" if hit else "FAIL"
        print(f"Q{qid:02d}: {question[:45]}... | Retrieval: {status_symbol} | F1: {token_f1:.2f} | Sim: {sem_sim:.2f} | {latency:.2f}s")

    # Calculate overall metrics
    avg_hit_rate = (retrieval_hits / total_questions) * 100.0
    avg_f1 = (total_f1 / total_questions) * 100.0
    avg_sim = (total_similarity / total_questions) * 100.0
    
    print("-" * 80)
    print("Evaluation Summary:")
    print(f"Total Evaluated Questions : {total_questions}")
    print(f"Retrieval Hit Rate (Recall@4) : {avg_hit_rate:.2f}%")
    print(f"Average Token F1-score       : {avg_f1:.2f}%")
    print(f"Average Semantic Similarity  : {avg_sim:.2f}%")
    print("-" * 80)
    
    # Create final results structure
    summary = {
        "metrics": {
            "total_questions": total_questions,
            "retrieval_hit_rate_pct": round(avg_hit_rate, 2),
            "avg_token_f1_pct": round(avg_f1, 2),
            "avg_semantic_similarity_pct": round(avg_sim, 2)
        },
        "queries": results
    }
    
    # Save results to data/eval_results.json
    results_path = config.DATA_DIR / "eval_results.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
        
    print(f"Saved detailed evaluation results to {results_path}")
    
    # Write a quick markdown summary in the workspace
    md_report_path = config.ROOT_DIR / "evaluation_report.md"
    with open(md_report_path, 'w', encoding='utf-8') as f:
        f.write("# PolicyPilot System Evaluation Report\n\n")
        f.write("This report displays the performance evaluation of the PolicyPilot RAG pipeline.\n\n")
        f.write("## Overall Metrics\n\n")
        f.write("| Metric | Score |\n")
        f.write("| :--- | :--- |\n")
        f.write(f"| **Total Evaluation Cases** | {total_questions} |\n")
        f.write(f"| **Retrieval Recall@4 (Hit Rate)** | {avg_hit_rate:.2f}% |\n")
        f.write(f"| **Average Token-level F1** | {avg_f1:.2f}% |\n")
        f.write(f"| **Average Semantic Cosine Similarity** | {avg_sim:.2f}% |\n\n")
        
        f.write("## Query-by-Query Performance Detail\n\n")
        f.write("| ID | Question | Expected Doc/Page | Retrieval Hit? | Token F1 | Semantic Sim |\n")
        f.write("| :--- | :--- | :--- | :---: | :---: | :---: |\n")
        for res in results:
            hit_str = "✅" if res["retrieval_hit"] else "❌"
            f.write(f"| {res['id']} | {res['question']} | `{res['expected_document']}` (P.{res['expected_page']}) | {hit_str} | {res['token_f1']*100:.1f}% | {res['semantic_similarity']*100:.1f}% |\n")
            
    print(f"Generated markdown report at {md_report_path}")
    return True


if __name__ == "__main__":
    success = run_evaluation()
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
