from pathlib import Path

import faiss
import numpy as np
from groq import Groq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import CrossEncoder, SentenceTransformer

from config import GROQ_API_KEY


class RAGPipeline:
    def __init__(self):
        self.kb_dir = Path(__file__).resolve().parents[1] / "knowledge_base"
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.client = Groq(api_key=GROQ_API_KEY)

        self.categories = {
            "account_access.md": "Account Access",
            "password_reset.md": "Account Access",
            "network.md": "Network",
            "hardware.md": "Hardware",
            "software.md": "Software",
            "email.md": "Email",
            "security.md": "Security",
        }

        self.chunks = []
        self.index = None
        self.build_index()

    def build_index(self):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=700,
            chunk_overlap=100,
        )

        for file in self.kb_dir.glob("*.md"):
            text = file.read_text(encoding="utf-8")

            for chunk in splitter.split_text(text):
                self.chunks.append({
                    "text": chunk,
                    "source": file.name,
                })

        texts = [chunk["text"] for chunk in self.chunks]
        embeddings = self.embedder.encode(
            texts,
            normalize_embeddings=True,
        ).astype("float32")

        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)

    def retrieve(self, query):
        query_embedding = self.embedder.encode(
            [query],
            normalize_embeddings=True,
        ).astype("float32")

        k = min(5, len(self.chunks))
        scores, indices = self.index.search(query_embedding, k)

        results = []

        for score, index in zip(scores[0], indices[0]):
            results.append({
                **self.chunks[index],
                "similarity": float(score),
            })

        rerank_scores = self.reranker.predict([
            (query, result["text"]) for result in results
        ])

        for result, score in zip(results, rerank_scores):
            result["rerank_score"] = float(score)

        results.sort(
            key=lambda result: result["rerank_score"],
            reverse=True,
        )

        return results[:3]

    def answer(self, query):
        results = self.retrieve(query)

        if not results or max(r["similarity"] for r in results) < 0.2:
            return {
                "category": "Unknown",
                "resolution": "No useful information was found in the knowledge base.",
                "sources": [],
                "has_useful_information": False,
            }

        category = self.categories.get(results[0]["source"], "Other")
        sources = list(dict.fromkeys(r["source"] for r in results))

        context = "\n\n".join(
            f"Source: {r['source']}\n{r['text']}"
            for r in results
        )

        prompt = f"""Use only the support documentation below to resolve the user's issue.

User issue:
{query}

Support documentation:
{context}

Give a short resolution for the support ticket. Do not add information that is not supported by the documentation."""

        response = self.client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
        )

        return {
            "category": category,
            "resolution": response.choices[0].message.content.strip(),
            "sources": sources,
            "has_useful_information": True,
        }
