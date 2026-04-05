# Deploying Alpha Scout to Google Cloud

## Prerequisites

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed: https://cloud.google.com/sdk/docs/install
3. **API Keys** ready:
   - `GEMINI_API_KEY` from https://aistudio.google.com/apikey
   - `TAVILY_API_KEY` from https://tavily.com

---

## Quick Deploy (5 minutes)

### 1. Authenticate
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 2. Enable APIs
```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### 3. Set API Keys as Secrets
```bash
# Create secrets
echo -n "your_gemini_key" | gcloud secrets create GEMINI_API_KEY --data-file=-
echo -n "your_tavily_key" | gcloud secrets create TAVILY_API_KEY --data-file=-

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding TAVILY_API_KEY \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 4. Deploy
```bash
cd alpha_scout

# Build and deploy
gcloud builds submit --config cloudbuild.yaml
```

### 5. Set Environment Variables
```bash
gcloud run services update alpha-scout \
  --region europe-west1 \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest,TAVILY_API_KEY=TAVILY_API_KEY:latest"
```

---

## Manual Deploy (Alternative)

```bash
# Build locally
docker build -t alpha-scout .

# Tag for GCR
docker tag alpha-scout gcr.io/YOUR_PROJECT_ID/alpha-scout

# Push
docker push gcr.io/YOUR_PROJECT_ID/alpha-scout

# Deploy
gcloud run deploy alpha-scout \
  --image gcr.io/YOUR_PROJECT_ID/alpha-scout \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --set-env-vars "GEMINI_API_KEY=xxx,TAVILY_API_KEY=xxx"
```

---

## After Deployment

Your app will be available at:
```
https://alpha-scout-XXXXX-ew.a.run.app
```

### Useful Commands
```bash
# View logs
gcloud run services logs read alpha-scout --region europe-west1

# Get URL
gcloud run services describe alpha-scout --region europe-west1 --format="value(status.url)"

# Update with new code
gcloud builds submit --config cloudbuild.yaml
```

---

## Cost Estimate

Cloud Run charges only when the app is running:
- **CPU**: ~$0.00002400/vCPU-second
- **Memory**: ~$0.00000250/GiB-second
- **Requests**: First 2M free, then $0.40/million

**Typical usage**: $5-20/month for demo purposes.

---

## Troubleshooting

### "Permission denied" on secrets
```bash
# Get project number
gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)"

# Grant access (replace PROJECT_NUMBER)
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### App crashes on startup
Check logs:
```bash
gcloud run services logs read alpha-scout --region europe-west1 --limit 50
```

### Database not persisting
Cloud Run is stateless. For persistent storage, use:
- Cloud SQL (PostgreSQL)
- Cloud Storage (for SQLite file)
- Firestore
