import os
import re
from pathlib import Path

import faiss
import numpy as np
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter


class RAGPipeline:
    def __init__(self):
        load_dotenv()

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is missing from the .env file.")

        self.client = Groq(api_key=api_key)
        self.knowledge_base = (
            Path(__file__).resolve().parent.parent / "knowledge_base"
        )

        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=700,
            chunk_overlap=100
        )

        self.chunks = []
        self.index = None

        self.category_map = {
            "account_access.md": "Account Access",
            "password_reset.md": "Account Access",
            "network.md": "Network",
            "hardware.md": "Hardware",
            "software.md": "Software",
            "email.md": "Email",
            "security.md": "Security"
        }

        self._build_index()

    def _build_index(self):
        for path in sorted(self.knowledge_base.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            pieces = self.splitter.split_text(text)

            for piece in pieces:
                self.chunks.append({
                    "text": piece,
                    "source": path.name
                })

        if not self.chunks:
            raise ValueError("No knowledge base documents were found.")

        texts = [chunk["text"] for chunk in self.chunks]

        embeddings = self.embedding_model.encode(
            texts,
            normalize_embeddings=True
        )

        embeddings = np.asarray(
            embeddings,
            dtype="float32"
        )

        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)

    def _keyword_score(self, query, text):
        query_words = set(
            re.findall(r"[a-z0-9]+", query.lower())
        )

        text_words = set(
            re.findall(r"[a-z0-9]+", text.lower())
        )

        if not query_words:
            return 0.0

        return len(query_words & text_words) / len(query_words)

    def retrieve(self, query, top_k=5):
        query_embedding = self.embedding_model.encode(
            [query],
            normalize_embeddings=True
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype="float32"
        )

        count = min(top_k, len(self.chunks))

        scores, indices = self.index.search(
            query_embedding,
            count
        )

        candidates = []

        for semantic_score, index in zip(
            scores[0],
            indices[0]
        ):
            chunk = self.chunks[index]

            keyword_score = self._keyword_score(
                query,
                chunk["text"]
            )

            rerank_score = (
                0.8 * float(semantic_score)
                + 0.2 * keyword_score
            )

            candidates.append({
                "text": chunk["text"],
                "source": chunk["source"],
                "semantic_score": float(semantic_score),
                "rerank_score": rerank_score
            })

        candidates.sort(
            key=lambda item: item["rerank_score"],
            reverse=True
        )

        return candidates[:3]

    def answer(self, query):
        results = self.retrieve(query)

        if not results:
            return {
                "category": "Unknown",
                "resolution": (
                    "No useful information was found "
                    "in the knowledge base."
                ),
                "sources": [],
                "has_useful_information": False
            }

        best = results[0]

        if best["semantic_score"] < 0.20:
            return {
                "category": "Unknown",
                "resolution": (
                    "No useful information was found "
                    "in the knowledge base."
                ),
                "sources": [],
                "has_useful_information": False
            }

        category = self.category_map.get(
            best["source"],
            "Other"
        )

        context_parts = []
        sources = []

        for result in results:
            context_parts.append(
                f"Source: {result['source']}\n"
                f"{result['text']}"
            )

            if result["source"] not in sources:
                sources.append(result["source"])

        context = "\n\n".join(context_parts)

        prompt = f"""
Use only the support documentation below to answer the user's issue.

User issue:
{query}

Support documentation:
{context}

Write a short resolution for a support ticket.
Do not add information that is not supported by the documentation.
Return only the resolution text.
"""

        response = self.client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=250
        )

        resolution = (
            response.choices[0]
            .message.content
            .strip()
        )

        return {
            "category": category,
            "resolution": resolution,
            "sources": sources,
            "has_useful_information": True
        }
