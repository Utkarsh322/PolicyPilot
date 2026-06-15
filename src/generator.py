import os
import requests
import json
import re
from typing import List, Dict, Any
from langchain_core.documents import Document

try:
    from src import config
except ImportError:
    import config

class ResponseGenerator:
    def __init__(self):
        self.provider = config.LLM_PROVIDER
        print(f"ResponseGenerator initialized with provider: {self.provider}")

    def generate_response(self, query: str, context_docs: List[Document], conversation_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Generates a RAG response citing sources, based on the active provider.
        """
        if not context_docs:
            return {
                "answer": "I couldn't find this in our policy documents. Please contact HR/IT support directly.",
                "sources": []
            }

        # Build clean source list for references
        sources = []
        for doc in context_docs:
            sources.append({
                "source": doc.metadata.get("source", "Unknown Document"),
                "page": doc.metadata.get("page", 0),
                "title": doc.metadata.get("title", "Policy Document")
            })

        # Remove duplicate sources
        unique_sources = []
        seen = set()
        for src in sources:
            key = (src["source"], src["page"])
            if key not in seen:
                seen.add(key)
                unique_sources.append(src)

        # Call appropriate model provider
        if self.provider == "openai":
            answer = self._generate_openai(query, context_docs, conversation_history)
        elif self.provider == "gemini":
            answer = self._generate_gemini(query, context_docs, conversation_history)
        elif self.provider == "ollama":
            answer = self._generate_ollama(query, context_docs, conversation_history)
        else:
            answer = self._generate_mock(query, context_docs)

        return {
            "answer": answer,
            "sources": unique_sources
        }

    def _build_system_prompt(self, context_docs: List[Document]) -> str:
        """
        Builds the system instructions containing the context.
        """
        context_str = ""
        for i, doc in enumerate(context_docs):
            src_name = doc.metadata.get("source", "Unknown Document")
            page_num = doc.metadata.get("page", 0)
            context_str += f"[{i+1}] Source: {src_name} (Page {page_num})\nContent: {doc.page_content}\n\n"

        prompt = (
            "You are PolicyPilot, an AI-powered Enterprise Knowledge Assistant. "
            "Your job is to answer the user's question accurately using ONLY the provided policy context below.\n"
            "If the provided context does not contain enough information to answer the question, respond exactly with: "
            "\"I couldn't find this in our policy documents. Please contact HR/IT support directly.\"\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Base your answer strictly on the context. Do not make assumptions or extrapolate.\n"
            "2. For EVERY claim or fact you state, you MUST cite the source document and page number in parentheses, "
            "for example: '(leave_policy.pdf, Page 1)' or 'According to the IT Support & Asset Policy (it_policy.pdf, Page 2)...'\n"
            "3. If multiple sources support a claim, cite all of them.\n"
            "4. Keep your answer professional, clear, and concise.\n\n"
            "Provided Policy Context:\n"
            "======================\n"
            f"{context_str}"
            "======================\n"
        )
        return prompt

    def _generate_openai(self, query: str, context_docs: List[Document], conversation_history: List[Dict[str, str]]) -> str:
        """
        Generates response using OpenAI API.
        """
        api_key = config.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "[Error: OpenAI API Key is missing. Fallback to local mock response.]\n\n" + self._generate_mock(query, context_docs)

        system_prompt = self._build_system_prompt(context_docs)
        
        # Build messages including history
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            for msg in conversation_history[-5:]: # Include last 5 messages for context
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": query})

        try:
            url = "https://api.openai.com/v1/chat/completypes" # wait, standard url is chat/completions
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            payload = {
                "model": config.OPENAI_MODEL,
                "messages": messages,
                "temperature": 0.0
            }
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                return f"[OpenAI API Error {response.status_code}: {response.text}]\n\nFallback Answer:\n" + self._generate_mock(query, context_docs)
        except Exception as e:
            return f"[OpenAI connection failed: {e}]\n\nFallback Answer:\n" + self._generate_mock(query, context_docs)

    def _generate_gemini(self, query: str, context_docs: List[Document], conversation_history: List[Dict[str, str]]) -> str:
        """
        Generates response using Google Gemini API.
        """
        api_key = config.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "[Error: Gemini API Key is missing. Fallback to local mock response.]\n\n" + self._generate_mock(query, context_docs)

        system_prompt = self._build_system_prompt(context_docs)
        
        # Construct Gemini API payload
        # Standard endpoint: v1beta/models/gemini-1.5-flash:generateContent
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            
            # Simple content structure for Gemini (combining system instructions and history)
            contents = []
            
            # We can pass system instruction in the config parameter for Gemini
            contents.append({
                "role": "user",
                "parts": [{"text": system_prompt + f"\n\nUser Question: {query}"}]
            })
            
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.0
                }
            }
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                # Parse text from candidate
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                return text
            else:
                return f"[Gemini API Error {response.status_code}: {response.text}]\n\nFallback Answer:\n" + self._generate_mock(query, context_docs)
        except Exception as e:
            return f"[Gemini connection failed: {e}]\n\nFallback Answer:\n" + self._generate_mock(query, context_docs)

    def _generate_ollama(self, query: str, context_docs: List[Document], conversation_history: List[Dict[str, str]]) -> str:
        """
        Generates response using local Ollama model.
        """
        system_prompt = self._build_system_prompt(context_docs)
        
        # Build prompt string or message structure
        prompt_str = f"{system_prompt}\n\n"
        if conversation_history:
            for msg in conversation_history[-3:]:
                prompt_str += f"{msg['role'].upper()}: {msg['content']}\n"
        prompt_str += f"USER: {query}\nASSISTANT:"

        try:
            url = f"{config.OLLAMA_HOST}/api/generate"
            payload = {
                "model": config.OLLAMA_MODEL,
                "prompt": prompt_str,
                "stream": False,
                "options": {
                    "temperature": 0.0
                }
            }
            response = requests.post(url, json=payload, timeout=45)
            if response.status_code == 200:
                result = response.json()
                return result["response"]
            else:
                return f"[Ollama Service Error {response.status_code}. Make sure Ollama is running.]\n\nFallback Answer:\n" + self._generate_mock(query, context_docs)
        except Exception as e:
            return f"[Could not connect to Ollama at {config.OLLAMA_HOST}. Is it running?]\n\nFallback Answer:\n" + self._generate_mock(query, context_docs)

    def _generate_mock(self, query: str, context_docs: List[Document]) -> str:
        """
        A local keyword-extractive answer generator that acts as an LLM fallback.
        It searches retrieved chunks, extracts relevant sentences, and structures an answer.
        """
        if not context_docs:
            return "I couldn't find this in our policy documents. Please contact HR/IT support directly."

        # Find best chunk (usually the first retrieved one)
        top_doc = context_docs[0]
        text = top_doc.page_content
        doc_name = top_doc.metadata.get("source", "policy_document.pdf")
        page_num = top_doc.metadata.get("page", 1)
        doc_title = top_doc.metadata.get("title", "Policy Document")

        # Let's write a dynamic answer based on sentences matching keywords in the query
        query_words = [w.lower() for w in query.split() if len(w) > 3]
        
        # Split block into sentences
        # Simple sentence splitter: split on periods followed by whitespace
        sentences = re.split(r'\.\s+', text)
        matching_sentences = []
        
        for idx, sentence in enumerate(sentences):
            sentence_clean = sentence.strip()
            if not sentence_clean:
                continue
            # Score sentence based on word overlap
            overlap = sum(1 for w in query_words if w in sentence_clean.lower())
            if overlap > 0:
                matching_sentences.append((sentence_clean, overlap, idx))

        # Sort matching sentences by word overlap, preserving order of appearance if possible
        matching_sentences.sort(key=lambda x: (-x[1], x[2]))
        
        # Select best 2-3 sentences to formulate the answer
        if matching_sentences:
            selected_sentences = [item[0] for item in matching_sentences[:3]]
            # Add periods if missing
            answer_body = " ".join([s if s.endswith('.') else s + '.' for s in selected_sentences])
        else:
            # Fallback to the first paragraph of the best chunk
            answer_body = text.split("\n\n")[0].strip()
            if not answer_body.endswith('.'):
                answer_body += '.'

        # Format and append citations inline
        answer = (
            f"Based on the corporate document **{doc_title}**:\n\n"
            f"{answer_body} ({doc_name}, Page {page_num})\n\n"
            f"> *Note: This response was processed locally using PolicyPilot's deterministic semantic parsing engine.*"
        )
        
        return answer
