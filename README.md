# 🧭 Survival Guidance Assistant  
*A Retrieval-Augmented Generation System for Evidence-Based Survival Advice*

---


## 🟠 Problem Description : The Challenge of Unlocking Structured Knowledge from Unstructured Media

### The Information Accessibility Problem
In today's digital landscape, valuable expert knowledge remains trapped in unstructured formats—particularly in video and audio content. While platforms like YouTube host incredible domain expertise, this knowledge is:

- 🔒 **Temporally locked** in hour-long videos  
- 🔗 **Structurally fragmented** across multiple content pieces  
- 🔍 **Difficult to search** beyond basic metadata  
- 🔄 **Lacking cross-references** between related concepts

---

## 🚀 The Solution: A Survival Knowledge Intelligence Platform
This project demonstrates how to transform unstructured survival content into an **intelligent, queryable knowledge base** using the *"How to Survive"* YouTube channel as a domain case study.

### The Transformation Pipeline
We've engineered an end-to-end system that revolutionizes how we interact with media content:

| Traditional Media | ➡️ | Our Intelligent System |
|---:|:---:|:---|
| 📺 Passive video consumption | → | 🔍 Active knowledge retrieval |
| 🎯 Manual content searching | → | 🤖 Semantic understanding of queries |
| 📝 Note-taking & bookmarking | → | 💾 Automated knowledge extraction |
| ❓ Isolated information | → | 🔗 Cross-referenced insights |

---

## ⚡ Real-World Impact
For survival scenarios where seconds count, our system delivers:

- ⚡ **Rapid access** to precise survival procedures  
- 📚 **Evidence-backed guidance** sourced from trusted content  
- 🎯 **Context-aware responses** tailored to specific emergencies  
- 🔄 **Continuous improvement** through user feedback loops

---

## 🌟 Beyond Survival: A Blueprint for Domain Intelligence
Although implemented for survival knowledge, this architecture is a reusable template for building intelligent knowledge bases in any domain:

- 🏥 Medical education from expert lectures  
- 💻 Technical training from tutorial content  
- 🏢 Corporate knowledge from internal presentations  
- 🎓 Academic research from conference recordings

---

> 💡 **This isn't just another RAG system** — it's a production-grade framework for transforming any media repository into an interactive knowledge companion. Features include ingestion, RAG retrieval, LLM reasoning, monitoring, user feedback, and cloud-native deployment.  
>
> **The result:** a transparent, reliable assistant that makes expert knowledge instantly accessible — backed by the original sources that generated it.

---



## 📘 Solution Overview  
**Survival Guidance Assistant** is a modular end-to-end RAG pipeline that transforms raw video transcripts into a **searchable, explainable and survival knowledge base**.  

Users can query the system via a [**Streamlit interface**](https://survivor-savant.streamlit.app/), get **evidence-backed answers** structured by OpenAI but strictly based on a knowledge base of transripts from playlist of the popular YouTube channel *How to survive*, and submit usage feedback through the interface.

> 💡 Built as a capstone project for the DataTalks.Club LLM Zoomcamp, this project demonstrates full-stack RAG application development engineered with MLOps practices — ingestion, RAG retrieval, LLM reasoning, monitoring, and containerization with Docker & Docker Compose — culminating in a multi-cloud deployment where diverse services orchestrate seamlessly to deliver a consolidated, intelligent, and production-ready retrieval experience.

---


## 🔍 Solution Summary  

| **Stage** | **Description** |
|:-----------|:----------------|
| **Ingestion & Chunking** | Extract and chunk transcripts into semantically meaningful segments with metadata (title, chapter, timestamp). |
| **Embedding & Storage** | Convert chunks to vector embeddings with **FastEmbed** and store them in **Qdrant Cloud** for semantic retrieval. |
| **Orchestration** | **Prefect** as the orchestrator for deploying cron-scheduled workflows of the Ingestion and the Chunk-Embed-Upsert pipelines. |
| **Retrieval-Augmented Generation** | **FastAPI** service retrieves top-matching chunks and crafts context-aware prompts for **OpenAI API**. |
| **User Interface** | **Streamlit** app for the user interface. |
| **Feedback Loop** | User feedback (sentiment, clarity, satisfaction) logged to **PostgreSQL** and visualized via **Grafana Cloud**. |
| **Deployment** | Two lightweight containers — `rag_api` (FastAPI) and `streamlit_app` (UI) — orchestrated via **Docker Compose**. |

---

## 🧩 Architecture Overview  

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                            SURVIVAL GUIDANCE ASSISTANCE SYSTEM                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

                                      ┌─────────────────┐
                                      │   INPUT SOURCE  │
                                      │ YouTube Playlist│
                                      │      URLs       │
                                      └─────────┬───────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                  PREFECT ORCHESTRATED INGESTION PIPELINE - PART 1                               │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────────────────────────────────┐
                        │            Content Catalog Creator              │
                        │  - Processes YouTube playlist URLs              │
                        │  - Creates video metadata catalog               │
                        │  - Identifies videos with/without transcripts   │
                        └───────────────┬─────────────────────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────────────────────┐
                        │           Transcript Downloader                 │
                        │  - Downloads available transcripts (JSON)       │
                        │  - Filters successful/failed downloads          │
                        └───────────────┬─────────────────────────────────┘
                                        │
                                        ▼
                        ┌───────────────┴───────────┐
                        │          SPLIT PATH       │
                        └───────────────┬───────────┘
                                        │
                ┌───────────────────────┼───────────────────────┐
                │                       │                       │
                ▼                       ▼                       ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│  Successful Transcripts │  │  Failed Transcripts     │  │   No Transcripts        │
│       (JSON files)      │  │    (Video List)         │  │     (Video List)        │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
                │                       │                       │
                └───────────────────────┼───────────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────────────────────┐
                        │           Audio Processing Pipeline             │
                        │  - Downloads audio clips for failed videos      │
                        │  - ASR Transcription using Faster Whisper       │
                        │  - Output: JSON transcripts                     │
                        └───────────────┬─────────────────────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────────────────────┐
                        │          All Transcripts (JSON)                 │
                        │  - Original + ASR generated transcripts         │
                        └───────────────┬─────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                      PREFECT ORCHESTRATED INGESTION PIPELINE - PART 2                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────────────────────────────────┐
                        │           Chapter-based Chunker                 │
                        │  - Segments transcripts by video chapters       │
                        │  - Creates semantic chunks                      │
                        └───────────────┬─────────────────────────────────┘
                                        │
                                        ▼
                        ┌────────────────────────────────────────────────────────────────┐
                        │             Embedding Generator                                │
                        │  - Model: "BAAI/bge-base-en-v1.5"                              │
                        │  - Converts chunks to vector embeddings with FastEmbed         │
                        └───────────────┬────────────────────────────────────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────────────────────┐
                        │              Vector Store Client                │
                        │  - Upserts embeddings to Qdrant Cloud           │
                        │  - Manages vector collections                   │
                        └───────────────┬─────────────────────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────────────────────┐
                        │        QDRANT CLOUD <---> RAG Pipeline          │
                        │  - Vector similarity search                     │
                        │  - Metadata storage                             │
                        │  - Collection management                        │
                        └─────────────────────────────────────────────────┘

                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                        RAG PIPELINE (FASTAPI SERVICE)                                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────────────────────────────────┐
                        │            FastAPI Application                  │
                        │  - REST API endpoints                           │
                        │  - User Query embedding                         │
                        │  - Vector search execution                      |
                        |  - Serves User a strucutured answer from LLM    │
                        └───────────────┬─────────────────────────────────┘
                                        │
                        ┌───────────────┴─────────────────────────────────┐
                        │          COMPONENTS                             │
                        └───────────────┬─────────────────────────────────┘
                                        │
                ┌───────────────────────┼───────────────────────┐
                ▼                       ▼                       ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│     Query Processor     │  │    Vector Retriever     │  │    Response Generator   │
│- User query vector embed│  │  - Cosine similarity    │  │  - OpenAI integration   │
│- Conditional Query      |  |  - Top-k retrieval      |  |  - Prompt engineering   |  
|  re-writing with LLM    │  │                         │  |                         │     
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
                │                       │                       │
                └───────────────────────┼───────────────────────┘
                                        │
                                        ▼
                        ┌─────────────────────────────────────────────────┐
                        │                  OPENAI API                     │
                        │  - LLM for response generation                  |
                        |  - LLM for Qyery Re-writing                     │
                        │  - Context-aware answers                        │
                        └─────────────────────────────────────────────────┘

                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           STREAMLIT CHATBOT INTERFACE                                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────────────────────────────────┐
                        │            Streamlit Application                │
                        │  - User interface                               │
                        │  - User Query Response                          │
                        │  -Chat history management /Query rewrite        |
                        |  - User experience feedback collection          │
                        └───────────────┬─────────────────────────────────┘
                                        │
                        ┌───────────────┴─────────────────────────────────┐
                        │                   COMPONENTS                    │
                        └───────────────┬─────────────────────────────────┘
                                        │
                ┌───────────────────────┼───────────────────────┐
                ▼                       ▼                       ▼
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│     UI Controller       │  │    API Client           │  │    Feedback Collector   │
│  - Chat interface       │  │  - FastAPI calls        │  │  - User rating system   │
│  - Session management   │  │  - Error handling       │  │  - Feedback storage     │
└─────────────────────────┘  └─────────────────────────┘  └─────────────┬───────────┘
                                                                        │
                                                                        ▼
                                                        ┌─────────────────────────────────┐
                                                        │   FEEDBACK DATABASE             │
                                                        │   AWS RDS PostgreSQL            │
                                                        │  - Upvote (+) Downvote (-)      | 
                                                        |  - Qunatitative User            |        
                                                        |    Satisfaction Level           │
                                                        │  - Categorised Usage            |
                                                        |    Sentiment on Response Quality│
                                                        └─────────────┬───────────────────┘
                                                                      │
                                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              MONITORING & ANALYTICS                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

                        ┌──────────────────────────────┐
                        │            Grafana Cloud     |
                        │  - Performance dashboards    │
                        │  - User feedback analytics   │
                        │  - System metrics            │
                        └─────────────── ──────────────┘
                                        ▲
                                        │             
                                        |
                                        |                      
                          ┌────────────────────────────┐
                          │     AWS RDS PostgreSQL     │
                          │    (Feedback Data)         |
                          └────────────────────────────┘

```


---

## 🧠 Key Features  

- ⚙️ Semantic retrieval pipeline built on **Qdrant + embeddings**  
- 🧾 Source-cited answers with **references and timestamps**  
- 🗣️ Context-aware LLM integration using **OpenAI API**  
- 📊 Real-time user feedback stored in **AWS RDS** and visualized in [**Grafana Cloud**](https://sapientsapiens.grafana.net/public-dashboards/87d99596e7654e7aaef8d5c4535de037)  
- 🧰 Lightweight and portable architecture via **Docker Compose**  
- ☁️ Cloud-managed services for Qdrant, Postgres, and Grafana  

---

## 🧱 Tech Stack  

| **Layer** | **Technology** |
|:-----------|:---------------|
| LLM & RAG | OpenAI API  |
| Embedding Genration | FastEmbed |
| Vector DB | Qdrant Cloud |
| API Framework | FastAPI |
| Frontend | Streamlit |
| Feedback Storage | AWS RDS (PostgreSQL) |
| Monitoring | Grafana Cloud |
| Containerization | Docker & Docker Compose |


## 🚀 Quick Start  - Reproducibility

```bash
# 1️⃣ Clone the repo
  git clone https://github.com/SapientSapiens/capstoneproject-2025-llmz.git
  cd capstoneproject-2025-llmz

# 2️⃣ Create a .env file with your credentials at the project root
  touch .env

# 3️⃣ Build & start both services
  docker compose up --build # if running for the first time
  docker compose up

# 4️⃣ Access the interfaces
  FastAPI (RAG API):   http://localhost:8010 -->> will show status "status": "ready"
  Streamlit App:       http://localhost:8501
```

📊 Results ---->>

✅ Fact-grounded survival advice with verified references

📈 Grafana dashboards visualize user sentiment & satisfaction trends

💬 Real feedback loop supports RAG evaluation for continuous improvement


📈 Next Steps ---->>

🔍 Retrieval evaluation & LLM evaluation
 
 🧬 Hybrid search with both dense and sparse vectors

 📑 Document Re-ranking


## 📊 Project Evaluation Rubric Compliance

| 🌟 **Criteria** | ✨ **Compliance Evidence** |
|:----------------|:---------------------------|
| 🧩 **Problem Description** | Problem definition of availability of rich subject/domain data from video/audio transcripts and how this solution addresses it. |
| 🔍 **Retrieval Flow** | **Qdrant** vector database (knowledge base) + **OpenAI LLM** in a fully integrated retrieval pipeline. |
| 💻 **Interface** | **Streamlit UI** + **FastAPI** backend with full user interaction and seamless responses. |
| ⚙️ **Ingestion Pipeline** | Automated **Prefect**-orchestrated pipeline for scalable content ingestion and processing. |
| 📈 **Monitoring** | Real-time **User Feedback Collection** in **AWS RDS PostgreSQL** + **Grafana Cloud** dashboard with 5 analytical charts. |
| 🐳 **Containerization** | Complete **Docker Compose** setup orchestrating all microservices with isolated environments. |
| ♻️ **Reproducibility** | Clear instructions, accessible data, and **fully versioned, reproducible** environment setup |
| 🧠 **Best Practices** | **↳ Query Rewriting:** Implemented intelligent query rewriting for context-aware retrieval and better conversation flow. |
| ☁️ **Bonus Points** | **↳ Cloud Deployment:** Fully containerized **multicloud architecture** deployed to **AWS EC2**, **Streamlit Cloud**, **Qdrant Cloud**, **AWS RDS PostgreSQL**, and **Grafana Cloud**. |


## 📊 Operating the Cloud Deployed Survival Guidance RAG  

 ![alt text](images/cloud-active.gif)


### Please also check my component-wise project developement and execution [images](images/)

### Thank You