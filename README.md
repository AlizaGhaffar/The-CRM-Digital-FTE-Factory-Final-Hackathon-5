# NimbusFlow Customer Success FTE

**Hackathon 5 — The CRM Digital FTE Factory**
*Build Your First 24/7 AI Employee: From Incubation to Production*

A production-grade AI Customer Success agent that works 24/7 across **three communication channels** — Gmail, WhatsApp, and Web Form — powered by **Groq (LLaMA 4)**, built with **OpenAI Agents SDK**, **FastAPI**, **PostgreSQL**, and **Apache Kafka**.

---

## What It Does

A customer sends a support message via any channel → the AI agent:
1. Creates a support ticket in PostgreSQL
2. Analyzes customer sentiment
3. Searches the knowledge base
4. Generates a channel-appropriate response via Groq AI
5. Sends the reply back through the **same channel** (Gmail reply, WhatsApp message, or email notification)
6. Escalates to human if needed

---

## Architecture

```
┌─────────────┐  ┌──────────────┐  ┌─────────────┐
│   Gmail     │  │  WhatsApp    │  │  Web Form   │
│  (Gmail API)│  │  (Twilio)    │  │  (React UI) │
└──────┬──────┘  └──────┬───────┘  └──────┬──────┘
       │                │                  │
       ▼                ▼                  ▼
┌─────────────────────────────────────────────────┐
│              FastAPI Backend (:8000)             │
│   /webhooks/gmail  /webhooks/whatsapp            │
│   /support/submit  /support/ticket/{id}          │
└──────────────────────┬──────────────────────────┘
                       │ Kafka
                       ▼
┌─────────────────────────────────────────────────┐
│           Message Processor Worker               │
│         (OpenAI Agents SDK + Groq AI)            │
│                                                  │
│  create_ticket → analyze_sentiment →             │
│  search_knowledge_base → escalate_to_human →     │
│  send_response (delivers back via channel)       │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
   PostgreSQL (NeonDB)         Groq API (LLaMA 4)
   customers, tickets,         api.groq.com/openai/v1
   conversations, messages
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Model | Groq Cloud — `meta-llama/llama-4-scout-17b-16e-instruct` |
| Agent Framework | OpenAI Agents SDK |
| Backend API | FastAPI + Python 3.12 |
| Message Queue | Apache Kafka (Confluent) |
| Database | PostgreSQL 16 + pgvector (NeonDB) |
| Email Channel | Gmail API (OAuth2) |
| WhatsApp Channel | Twilio WhatsApp API |
| Web Channel | React 18 + Vite + Tailwind CSS |
| Containerization | Docker + Docker Compose |
| Orchestration | Kubernetes (manifests included) |

---

## Agent Skills (Tools)

| Skill | Tool | Description |
|-------|------|-------------|
| Customer Identification | `create_ticket` | Find/create customer, open ticket |
| Customer History | `get_customer_history` | Fetch prior interactions |
| Sentiment Analysis | `analyze_sentiment` | Score mood (0.0–1.0), detect escalation triggers |
| Knowledge Retrieval | `search_knowledge_base` | Vector search over resolved tickets |
| Escalation Decision | `escalate_to_human` | Route to billing@, legal@, or oncall@ |
| Channel Adaptation | `send_response` | Format + deliver reply via Gmail/WhatsApp/Email |

---

## Channel Response Matrix

| Channel | Intake | AI Response Delivery |
|---------|--------|---------------------|
| Gmail | Gmail API Webhook → Kafka | Gmail API reply (same thread) |
| WhatsApp | Twilio Webhook → Kafka | Twilio WhatsApp message |
| Web Form | React Form → FastAPI → Kafka | Gmail email to customer |

---

## Project Structure

```
├── production/
│   ├── agent/
│   │   ├── customer_success_agent.py   # OpenAI Agents SDK agent
│   │   └── tools.py                    # 6 agent tools (skills)
│   ├── api/
│   │   └── main.py                     # FastAPI endpoints
│   ├── channels/
│   │   ├── gmail_handler.py            # Gmail OAuth2 + send/receive
│   │   ├── whatsapp_handler.py         # Twilio WhatsApp + send/receive
│   │   └── web_form_handler.py         # Web form parsing + routing
│   ├── database/
│   │   ├── queries.py                  # asyncpg DB queries
│   │   └── schema.sql                  # PostgreSQL schema + pgvector
│   ├── workers/
│   │   └── message_processor.py        # Kafka consumer + agent runner
│   ├── tests/                          # 176 tests (all passing)
│   └── k8s/                            # Kubernetes manifests
├── frontend/
│   ├── src/App.jsx                     # React Router: /, /ticket/:id, /admin
│   └── components/
│       ├── SupportForm.jsx             # Customer support form
│       ├── TicketStatus.jsx            # Ticket tracking + conversation view
│       ├── AdminDashboard.jsx          # Agent admin panel
│       ├── AnalyticsDashboard.jsx      # Metrics + charts
│       ├── EscalationsQueue.jsx        # Human escalation queue
│       ├── ChannelConfig.jsx           # Channel settings
│       └── KnowledgeBaseManager.jsx    # KB management
├── docker-compose.yml                  # Full local stack
├── Dockerfile
└── .env.example                        # Environment template
```

---

## Quick Start

### Prerequisites
- Docker Desktop
- Node.js 18+
- Python 3.12+

### 1. Clone & Configure

```bash
git clone https://github.com/AlizaGhaffar/The-CRM-Digital-FTE-Factory-Final-Hackathon-5.git
cd The-CRM-Digital-FTE-Factory-Final-Hackathon-5

cp .env.example .env
# Fill in your credentials in .env
```

### 2. Required Environment Variables

```env
# Groq AI (https://console.groq.com)
GROQ_API_KEY=gsk_...
GROQ_MODEL=meta-llama/llama-4-scout-17b-16e-instruct

# PostgreSQL (NeonDB or any Postgres)
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require

# Gmail OAuth2
GMAIL_USER_ID=your@gmail.com
GMAIL_CREDENTIALS_PATH=secrets/client_secret_....json
GMAIL_TOKEN_PATH=secrets/token.json

# Twilio WhatsApp
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

### 3. Start Docker Stack

```bash
docker-compose up -d
```

This starts: Zookeeper → Kafka → Kafka UI → FastAPI → Worker

### 4. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

### 5. Access

| Service | URL |
|---------|-----|
| Customer Form | http://localhost:5173 |
| Ticket Tracker | http://localhost:5173/ticket/:id |
| Admin Dashboard | http://localhost:5173/admin |
| API Health | http://localhost:8000/health |
| API Docs | http://localhost:8000/docs |
| Kafka UI | http://localhost:8080 |

---

## Channel Setup

### Gmail
1. Create a Google Cloud project
2. Enable Gmail API
3. Download OAuth2 credentials → `secrets/client_secret_....json`
4. Run OAuth flow to generate `secrets/token.json`
5. Webhook: `POST /webhooks/gmail` (Google Pub/Sub push)
6. Manual poll (demo): `GET /webhooks/gmail/poll`

### WhatsApp (Twilio Sandbox)
1. Sign up at [twilio.com](https://twilio.com)
2. Go to Messaging → Try it out → Send a WhatsApp message
3. Run ngrok: `ngrok http 8000`
4. Set sandbox webhook: `https://your-ngrok-url.ngrok-free.app/webhooks/whatsapp`
5. Join sandbox from your phone: send `join <keyword>` to `+1 415 523 8886`

### Web Form
Submit via the React UI or directly:
```bash
curl -X POST http://localhost:8000/support/submit \
  -H "Content-Type: application/json" \
  -d '{"name":"John","email":"john@example.com","subject":"Help needed","message":"My order has not arrived","category":"billing"}'
```

---

## Running Tests

```bash
# All 176 tests
cd production
python -m pytest tests/ -v

# Specific suites
python -m pytest tests/test_agent.py -v
python -m pytest tests/test_e2e.py -v
python -m pytest tests/test_multichannel_e2e.py -v
python -m pytest tests/test_transition.py -v
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/support/submit` | Web form submission |
| GET | `/support/ticket/{id}` | Ticket status |
| GET | `/support/ticket/{id}/messages` | Conversation history |
| POST | `/support/ticket/{id}/reply` | Add customer reply |
| POST | `/support/ticket/{id}/escalate` | Request human agent |
| GET | `/webhooks/gmail/poll` | Manual Gmail poll (demo) |
| POST | `/webhooks/gmail` | Gmail Pub/Sub webhook |
| POST | `/webhooks/whatsapp` | Twilio WhatsApp webhook |
| GET | `/customers/lookup` | Customer lookup by email/phone |
| GET | `/conversations/{id}` | Full conversation with messages |
| GET | `/metrics/channels` | Channel performance metrics |
| GET | `/health` | Service health check |

---

## Kubernetes Deployment

```bash
kubectl apply -f production/k8s/namespace.yaml
kubectl apply -f production/k8s/secrets.yaml
kubectl apply -f production/k8s/configmap.yaml
kubectl apply -f production/k8s/deployment-api.yaml
kubectl apply -f production/k8s/deployment-worker.yaml
kubectl apply -f production/k8s/service.yaml
kubectl apply -f production/k8s/ingress.yaml
kubectl apply -f production/k8s/hpa.yaml
```

---

## Hackathon Deliverables Status

| Requirement | Status |
|-------------|--------|
| Working AI agent (OpenAI Agents SDK) | ✅ |
| Gmail channel (webhook + send) | ✅ |
| WhatsApp channel (Twilio webhook + send) | ✅ |
| Web Support Form (React + Vite) | ✅ |
| Ticket tracking + status page | ✅ |
| PostgreSQL schema (customers, tickets, messages) | ✅ |
| Kafka event streaming | ✅ |
| Sentiment analysis | ✅ |
| Knowledge base search | ✅ |
| Escalation routing | ✅ |
| Admin dashboard | ✅ |
| 176 tests passing | ✅ |
| Kubernetes manifests | ✅ |
| Docker Compose local stack | ✅ |

---

## Built With

- **Student:** Aliza Ghaffar
- **Hackathon:** CRM Digital FTE Factory — Hackathon 5
- **AI Assistant:** Claude Code (Anthropic)
- **Model:** Groq Cloud — LLaMA 4 Scout
