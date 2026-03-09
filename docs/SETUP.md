# VisionQA — Setup Guide

## Prerequisites

- Python 3.11+
- Google API Key (Gemini 2.5 Flash access)
- Google Chrome (for Selenium Navigator mode)
- Docker (optional, for container deployment)
- `gcloud` CLI (optional, for Cloud Run deployment)

---

## 1. Local Setup

```bash
# Clone and enter the project
git clone https://github.com/YOUR_USERNAME/visionqa
cd visionqa

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

Edit `.env`:

```
GOOGLE_API_KEY=your_gemini_api_key_here
CONFIDENCE_THRESHOLD=0.85
```

---

## 2. Running Locally

### Screenshot Analysis Mode
```bash
python main.py --image path/to/screenshot.png --prompt "Verify the login button is visible"
```

### Navigation + QA Mode
```bash
python main.py --url https://example.com --prompt "Check the page title is correct"
```

### API Server Mode
```bash
python main.py --serve
# Swagger UI available at: http://localhost:8080/docs
```

---

## 3. Running Tests

```bash
python -m pytest tests/ -v
```

Test results and Markdown reports are saved to `reports/`.

---

## 4. Docker Build (Local)

```bash
docker build -t visionqa .
docker run -p 8080:8080 -e GOOGLE_API_KEY=your_key_here visionqa
```

---

## 5. Deploy to Google Cloud Run

### One-time setup
```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com

# Create Artifact Registry repository
gcloud artifacts repositories create visionqa \
  --repository-format=docker \
  --location=us-central1

# Store API key in Secret Manager
echo -n "your_gemini_api_key" | gcloud secrets create GOOGLE_API_KEY --data-file=-
```

### Deploy
```bash
# Build and push image
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_GOOGLE_API_KEY=your_key_here

# Or manually:
IMAGE="us-central1-docker.pkg.dev/YOUR_PROJECT/visionqa/visionqa-api"
docker build -t "$IMAGE:latest" .
docker push "$IMAGE:latest"

gcloud run deploy visionqa-api \
  --image="$IMAGE:latest" \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-secrets=GOOGLE_API_KEY=GOOGLE_API_KEY:latest
```

---

## 6. GitHub Actions CI/CD

Set the following secrets in your GitHub repository (`Settings → Secrets`):

| Secret | Value |
|---|---|
| `GOOGLE_API_KEY` | Your Gemini API key |
| `GCP_PROJECT_ID` | Your Google Cloud project ID |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Workload Identity Federation provider |
| `GCP_SERVICE_ACCOUNT` | Service account email |

Every push to `main` will automatically: run tests → build → push to Artifact Registry → deploy to Cloud Run → health check.

---

## 7. Optional: Slack & Jira Integration

Add to `.env`:

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
JIRA_WEBHOOK_URL=https://your-domain.atlassian.net/rest/api/2/issue
GITHUB_TOKEN=ghp_your_token
GITHUB_REPO=your-org/your-repo
```

VisionQA will automatically post to Slack and create Jira/GitHub tickets whenever a visual bug is detected.
