# 🏛️ AI Campus Policy Navigator

## The Problem
University students waste hours digging through dense, outdated PDF policy documents (hostel rules, fee structures, academic guidelines) to find simple answers.

## The Solution
An AI-powered Retrieval-Augmented Generation (RAG) application that allows students to instantly query official campus documents and get cited, highly accurate answers. 

## 🧪 Quick Start for Judges (Testing Guide)

Before running the app, you must install the Python dependencies and set the API key locally.

### Environment Setup
1. **Install Dependencies:** Open your terminal in the root folder and run:
   ```bash
   pip install -r requirements.txt
   ```
2. **Set API Key:** Create a file named `.env` in the root folder and add the following:
   ```text
   GROQ_API_KEY=your_provided_api_key
   ADMIN_PASSWORD=acropolis2026
   ```
   *(Note: The actual Groq API key is provided privately in our hackathon submission form).*

### Running the App
1. **Start the Backend:** ```bash
   cd backend
   uvicorn main:app --reload
   ```
2. **Open the Frontend:** Open `frontend/index.html` in any modern web browser.
3. **Admin Login:** Enter the secure password `acropolis2026` to unlock the admin dashboard.
4. **Upload Context:** Open the `sample_documents` folder provided in this repository. Drag and drop the test PDFs into the upload zone.
5. **Test the Retrieval:** Switch to the student view and ask a specific question about the document you just uploaded. The AI will extract the correct policy and cite the exact source document and page number.

## Tech Stack
* **Backend:** FastAPI (Python)
* **Frontend:** HTML/CSS/JS (Vanilla, zero-dependency)
* **AI Model:** LLaMA 3.3 70B (via Groq API)
* **Document Parsing:** pdfplumber

## Core Architecture & Security
* **Role-Based Access Control (RBAC):** Admins strictly control the knowledge base; students can only query it. This structural decision prevents "database poisoning" from malicious user uploads.
* **Zero-Hallucination Prompting:** The AI is strictly bound by temperature controls (0.1) and system prompts to answer *only* from the uploaded context. If the answer isn't in the PDFs, it explicitly refuses to guess.
* **Granular Source Citation:** Every answer returns the exact PDF filename and page number so students can verify the policy themselves.
* **Persistent State:** Uploaded chunks are serialized to disk (`policy_store.json`), ensuring the knowledge base survives server restarts.