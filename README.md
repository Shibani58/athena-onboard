# Athena Onboard

**AI-generated, HR-reviewed onboarding plans on a serverless AWS stack.**

HR enters a new joiner's employee ID → Athena fetches their profile → picks the most relevant training with embeddings and cosine similarity → drafts a 3-week plan with an LLM → HR reviews and approves → the plan is emailed to the new joiner, with every step in an audit trail.

> This is a public **demo rebuild** of a hackathon project I worked on. The original ran on Amazon Bedrock (Titan Text + Titan Embeddings); this version uses the **Google Gemini API free tier** so the demo costs nothing. All employees and training content are **synthetic**.

## Architecture

```
Static UI (GitHub Pages)
   │
   ▼
API Gateway (HTTP API, throttled)
   ├── GET  /employees/{id}      → get-employee-details  (mock HR system)
   ├── POST /plans               → generate-plan         (cosine similarity + LLM → DynamoDB)
   ├── GET  /plans/{id}          → review-plan
   ├── PUT  /plans/{id}          → review-plan           (HR approve / reject, versioning, audit)
   └── POST /plans/{id}/send     → send-email            (SES, or an email preview in demo mode)
```

| Piece | Choice |
|---|---|
| Compute | AWS Lambda (Python 3.12, arm64) |
| API | API Gateway HTTP API with throttling |
| Storage | DynamoDB (plans, versions, audit trail) |
| Email | Amazon SES (optional; preview mode when not configured) |
| LLM | Gemini (`gemini-2.5-flash`) for plan generation, `gemini-embedding-001` for content selection |
| Fallback | Template planner + bag-of-words cosine when no API key is set or the free quota is used up |
| UI | Plain HTML/CSS/JS single page; runs fully in the browser in demo mode |
| IaC | AWS SAM (`backend/template.yaml`) |

**Guarding against hallucinations:** the LLM only sees the top training modules picked by cosine similarity and must reference them by ID; anything else is dropped before the plan is saved.

## Run the UI locally (demo mode)

Demo mode needs no backend: `config.js` has an empty API URL, so `mock-api.js` stands in for the Lambdas.

```bash
mkdir -p site/data && cp -r frontend/* site/ && cp backend/src/data/*.json site/data/
python -m http.server 8000 --directory site
```

Open http://localhost:8000 and try `EMP1001`.

## Deploy the backend

Prerequisites: an AWS account, the AWS CLI (`aws configure`) and the AWS SAM CLI. Optional: a free Gemini API key from Google AI Studio.

```bash
cd backend
sam build
sam deploy --guided   # stack name: athena-onboard; paste the Gemini key when asked (or leave empty)
```

Then put the `ApiUrl` output into `frontend/config.js` and push; GitHub Actions republishes the UI.

Cost: Lambda and DynamoDB stay within the AWS free tier at demo traffic; the API is throttled and plan generation is limited to 2 concurrent runs. Set an AWS budget alert anyway.

## Project layout

```
backend/
  template.yaml              SAM template (API, Lambdas, DynamoDB)
  src/
    get_employee_details.py  GET /employees/{id}
    generate_plan.py         POST /plans
    review_plan.py           GET / PUT /plans/{id}
    send_email.py            POST /plans/{id}/send
    llm.py                   Gemini text + embeddings, cosine similarity, offline fallback
    common.py                responses, data loading, DynamoDB + audit helpers
    data/                    synthetic employees and training catalogue
frontend/                    single-page UI (index.html, app.js, mock-api.js, styles.css, config.js)
```
