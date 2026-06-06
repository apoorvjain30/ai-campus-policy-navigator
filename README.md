# 🏛️ AI Campus Policy Navigator

**Team DataDrift** | **AI for Impact 2.0 Hackathon**

## The Problem
University students and administrative staff waste hours digging through dense, outdated PDF policy documents (hostel rules, fee structures, academic guidelines) to find simple answers.

## The Solution
An AI-powered Retrieval-Augmented Generation (RAG) application that allows students to instantly query official campus documents and get cited, highly accurate answers with zero hallucination.

---

## 🧪 Quick Start for Judges (Testing Guide)

To evaluate this project, please follow this exact workflow to see the full Admin-to-Student pipeline.

### 1. Environment Setup
Before running the app, install the required Python dependencies locally. Open your terminal in the root folder and run:
```bash
pip install -r requirements.txt
2. Verify Credentials
Note: Per hackathon evaluation requirements, the .env file containing the live Groq API key and admin password is already included inside the backend folder. You do not need to create or configure any keys manually.

3. Start the Backend Server
Navigate to the backend directory and spin up the FastAPI server:

Bash
cd backend
uvicorn main:app --reload
(The server will start running at http://127.0.0.1:8000)

4. Test the Application Workflow
Open Frontend: Open frontend/index.html in any modern web browser or via live server.

Admin Login: Click the Admin section and enter the secure password acropolis2026.

Upload Context: Open the sample_documents folder provided in this repository. Drag and drop a test PDF into the upload zone. Wait for the success confirmation.

Test Retrieval: Switch to the Student view and ask a specific question about the document you just uploaded. The AI will extract the correct policy and cite the exact source document and page number.

⚙️ Tech Stack & Architecture
Backend: FastAPI (Python) optimized for rapid asynchronous API routing.

Frontend: HTML/CSS/JS (Vanilla, zero-dependency for minimal latency).

AI Engine: LLaMA 3.3 70B (via Groq API) for sub-second inference.

Parser: pdfplumber for high-fidelity text extraction and chunking.

🔒 Security & Governance
Role-Based Access Control (RBAC): Admins strictly control the knowledge base; students can only query it. This prevents "database poisoning" from malicious uploads.

Zero-Hallucination Prompting: The AI operates at a temperature of 0.1 and is system-prompted to answer only from the uploaded context. It refuses to guess.

Persistent State: Uploaded document chunks are serialized to disk (policy_store.json), ensuring the knowledge base survives server restarts.