from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import json
import re
import pdfplumber
import shutil
from pathlib import Path
from typing import Optional
from groq import Groq
from dotenv import load_dotenv

# ── Load environment variables from .env file ──────────────────────────────────
load_dotenv()

# ── App Setup ──────────────────────────────────────────────────────────────────
app = FastAPI(title="AI Campus Policy Navigator", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ─────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
UPLOAD_DIR = Path("uploaded_policies")
UPLOAD_DIR.mkdir(exist_ok=True)
STORE_FILE = Path("policy_store.json")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "acropolis2026")

if not GROQ_API_KEY:
    print("⚠️  WARNING: GROQ_API_KEY not set. Please add it to your .env file.")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ── In-memory policy store ─────────────────────────────────────────────────────
policy_store: dict[str, list[dict]] = {}


# ── Persist policy store to disk ───────────────────────────────────────────────
def save_store():
    """Save policy store to JSON file so data survives server restarts."""
    with open(STORE_FILE, "w") as f:
        json.dump(policy_store, f)


def load_store():
    """Load policy store from disk on startup."""
    global policy_store
    if STORE_FILE.exists():
        try:
            with open(STORE_FILE, "r") as f:
                policy_store.update(json.load(f))
            print(f"✅ Loaded {len(policy_store)} documents from saved store.")
        except Exception as e:
            print(f"⚠️  Could not load saved store: {e}")


# Load saved data when server starts
load_store()


# ── Schemas ────────────────────────────────────────────────────────────────────
class QuestionRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5


class LoginRequest(BaseModel):
    password: str


# ── Helpers ────────────────────────────────────────────────────────────────────
def extract_pdf_chunks(filepath: str, filename: str) -> list[dict]:
    """
    Opens a PDF and extracts text page by page.
    Each page becomes one 'chunk' stored with its source filename and page number.
    """
    chunks = []
    with pdfplumber.open(filepath) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                chunks.append({
                    "source": filename,
                    "page": i,
                    "text": text.strip()
                })
    return chunks


def improved_keyword_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Improved search that:
    1. Removes common stop words (the, is, a, etc.)
    2. Checks for exact phrase matches (highest priority)
    3. Checks for individual word matches
    4. Checks for partial word matches
    This gives much better results than basic keyword search.
    """
    query_lower = query.lower()
    query_words = set(re.sub(r"[^\w\s]", "", query_lower).split())

    # Remove stop words so common words don't dominate scoring
    stop_words = {
        "what", "is", "the", "a", "an", "are", "how", "when",
        "where", "who", "can", "do", "does", "for", "of", "in",
        "to", "and", "or", "if", "my", "me", "i", "we", "our",
        "will", "be", "has", "have", "was", "were", "it", "this"
    }
    query_words = query_words - stop_words

    scored = []
    for filename, chunks in policy_store.items():
        for chunk in chunks:
            chunk_text_lower = chunk["text"].lower()

            # Exact phrase match gives highest score (5 points)
            phrase_score = 5 if query_lower in chunk_text_lower else 0

            # Each matching word gives 1 point
            word_score = sum(1 for w in query_words if w in chunk_text_lower)

            # Partial word match gives 0.5 points
            # e.g. query word "fee" matches "fees", "feeble", etc.
            partial_score = sum(
                0.5 for w in query_words
                if any(w in word for word in chunk_text_lower.split())
                and w not in chunk_text_lower  # avoid double counting
            )

            total_score = phrase_score + word_score + partial_score
            if total_score > 0:
                scored.append({"score": total_score, **chunk})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def build_prompt(question: str, context_chunks: list[dict]) -> str:
    """
    Builds the prompt sent to the AI model.
    We give it the question + relevant PDF pages as context.
    The AI must answer ONLY from this context — no hallucination.
    """
    context_text = ""
    for chunk in context_chunks:
        context_text += (
            f"\n--- Source: {chunk['source']} | Page {chunk['page']} ---\n"
            f"{chunk['text']}\n"
        )

    return f"""You are an AI Campus Policy Navigator for Acropolis Institute of Technology and Research, Indore.
Your job is to help students find answers from official campus policy documents.

STRICT RULES:
- Answer ONLY from the policy documents provided below.
- If the answer is not found, say exactly: "This information is not available in the uploaded policy documents."
- Always cite the source document name and page number.
- Be clear, helpful, and student-friendly in your tone.
- Respond ONLY with valid JSON. No extra text, no markdown, no explanation outside JSON.

STUDENT QUESTION: {question}

POLICY CONTEXT (extracted from official documents):
{context_text}

Respond with this EXACT JSON format:
{{
  "answer": "your detailed answer here",
  "source": "filename.pdf",
  "page": 1,
  "confidence": "high"
}}

Confidence levels: "high" = clearly stated in document, "medium" = inferred, "low" = not clearly found."""


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "message": "AI Campus Policy Navigator v2.0 is running!",
        "status": "ok",
        "documents_loaded": len(policy_store)
    }


@app.post("/login")
def login(req: LoginRequest):
    """
    Simple admin login.
    Returns a token if password is correct.
    This token is used by frontend to allow upload/delete.
    """
    if req.password == ADMIN_PASSWORD:
        return {"success": True, "token": "admin-token-aitr-2026"}
    raise HTTPException(status_code=401, detail="Incorrect password.")


@app.get("/policies")
def list_policies():
    """Returns list of all uploaded policy documents with page counts."""
    total_pages = sum(len(chunks) for chunks in policy_store.values())
    return {
        "policies": [
            {"filename": name, "pages": len(chunks)}
            for name, chunks in policy_store.items()
        ],
        "total_documents": len(policy_store),
        "total_pages": total_pages
    }


@app.post("/upload")
async def upload_policy(file: UploadFile = File(...)):
    """
    Accepts a PDF file, extracts all text page by page,
    stores it in memory AND saves to disk so it persists after restart.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    save_path = UPLOAD_DIR / file.filename
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    chunks = extract_pdf_chunks(str(save_path), file.filename)

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="Could not extract text from this PDF. Make sure it's not a scanned image."
        )

    policy_store[file.filename] = chunks
    save_store()  # ← Save to disk so data persists after restart

    return {
        "message": f"Successfully uploaded '{file.filename}'",
        "pages_extracted": len(chunks),
        "filename": file.filename,
        "total_documents": len(policy_store)
    }


@app.delete("/policies/{filename}")
def delete_policy(filename: str):
    """Removes a policy document from memory and disk."""
    if filename not in policy_store:
        raise HTTPException(status_code=404, detail="Policy not found.")

    del policy_store[filename]
    save_store()  # ← Update disk after deletion

    # Also delete the actual PDF file
    pdf_path = UPLOAD_DIR / filename
    if pdf_path.exists():
        pdf_path.unlink()

    return {"message": f"'{filename}' removed successfully.", "total_documents": len(policy_store)}


@app.post("/ask")
async def ask_question(req: QuestionRequest):
    """
    Main AI endpoint:
    1. Searches uploaded PDFs for relevant sections
    2. Sends question + context to Groq AI (LLaMA 3.3 70B)
    3. Returns structured answer with source citation
    """
    if not client:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY not configured. Please add it to your .env file."
        )

    if not policy_store:
        raise HTTPException(
            status_code=400,
            detail="No policy documents uploaded yet. Please upload at least one PDF first."
        )

    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Step 1 — Find relevant PDF sections
    relevant_chunks = improved_keyword_search(req.question, top_k=req.top_k)

    if not relevant_chunks:
        return JSONResponse({
            "answer": "No relevant policy sections found for your question. Try rephrasing or uploading more documents.",
            "source": None,
            "page": None,
            "confidence": "low",
            "related_sections": []
        })

    # Step 2 — Send to Groq AI
    prompt = build_prompt(req.question, relevant_chunks)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,   # Low temperature = more factual, less creative
            max_tokens=600
        )

        raw_text = response.choices[0].message.content.strip()

        # Clean up any markdown code fences the model might add
        raw_text = re.sub(r"^```json\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        result = json.loads(raw_text)

    except json.JSONDecodeError:
        # If AI doesn't return proper JSON, handle gracefully
        result = {
            "answer": response.choices[0].message.content.strip(),
            "source": relevant_chunks[0]["source"],
            "page": relevant_chunks[0]["page"],
            "confidence": "medium"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI model error: {str(e)}")

    # Step 3 — Add related sections (other relevant pages found)
    result["related_sections"] = [
        {
            "source": c["source"],
            "page": c["page"],
            "preview": c["text"][:200] + "..."
        }
        for c in relevant_chunks[1:]
    ]

    return result


@app.get("/health")
def health():
    """Health check endpoint — useful for checking if server is running."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "documents_loaded": len(policy_store),
        "total_chunks": sum(len(v) for v in policy_store.values()),
        "groq_configured": bool(GROQ_API_KEY)
    }
