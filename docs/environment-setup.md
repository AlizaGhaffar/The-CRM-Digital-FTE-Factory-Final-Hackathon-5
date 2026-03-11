# NimbusFlow Customer Success FTE — Environment Setup Guide

**Purpose:** Step-by-step instructions for obtaining every API key, credential,
and service configuration required to run the FTE in production.

**Time required:** 60–90 minutes (first time)
**Prerequisites:** Google account, Twilio account (free), Python 3.12+

---

## What You Need

| Credential | Service | Cost | Required? |
|-----------|---------|------|-----------|
| Gemini API key | Google AI Studio | Free (15 RPM) | ✅ Yes |
| OpenAI API key | OpenAI | Pay-per-use (tiny) | ✅ Yes (embeddings) |
| Twilio Account SID + Auth Token | Twilio | Free sandbox | ✅ Yes |
| Gmail OAuth2 credentials | Google Cloud | Free | ✅ Yes |
| Gmail OAuth2 token | Google OAuth flow | Free | ✅ Yes |
| GCP Project + Pub/Sub topic | Google Cloud | Free tier | ✅ Yes |
| PostgreSQL password | Self-managed | Free | ✅ Yes (you set it) |

---

## Section 1: Gemini API Key

The primary LLM used for agent inference (`gemini-2.0-flash` model).

### Steps

1. Open [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

2. Sign in with your Google account

3. Click **"Create API key"**

4. Select an existing Google Cloud project or click **"Create new project"**
   - Project name: `nimbusflow-fte` (or anything you prefer)

5. Copy the key immediately — it starts with `AIza`

6. Save it:
   ```bash
   # Add to .env:
   echo "GEMINI_API_KEY=AIzaSy..." >> .env

   # Encode for Kubernetes secrets:
   echo -n "AIzaSy..." | base64
   ```

### Verify it works

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=YOUR_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"parts":[{"text":"Say hello"}]}]}'
# Expected: JSON response with "Hello" in candidates[0].content
```

### Free tier limits
- 15 requests per minute
- 1 million tokens per day
- Sufficient for the 24-hour test at expected volume

---

## Section 2: OpenAI API Key

Used for `text-embedding-ada-002` (knowledge base semantic search). Minimal
cost — embedding calls are extremely cheap ($0.0001 per 1K tokens).

### Steps

1. Open [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)

2. Sign in (create a free account if needed)

3. Click **"Create new secret key"**
   - Name: `nimbusflow-fte-embeddings`
   - Permissions: **Restricted → Models (read)**

4. Copy the key immediately — starts with `sk-` — it is **shown only once**

5. Save it:
   ```bash
   echo "OPENAI_API_KEY=sk-proj-..." >> .env
   echo -n "sk-proj-..." | base64
   ```

### Add billing (required for API access)
1. Go to [https://platform.openai.com/account/billing](https://platform.openai.com/account/billing)
2. Add a payment method
3. Set a **usage limit** of $5/month to avoid surprises
4. Add $5 credit — enough for months of embedding calls

### Verify it works
```bash
curl https://api.openai.com/v1/embeddings \
  -H "Authorization: Bearer sk-proj-..." \
  -H "Content-Type: application/json" \
  -d '{"model":"text-embedding-ada-002","input":"test query"}' | \
  jq '.data[0].embedding | length'
# Expected: 1536
```

---

## Section 3: Twilio WhatsApp Sandbox

Twilio provides a free WhatsApp Sandbox — no WhatsApp Business account needed.

### Step 3a: Create Twilio account

1. Go to [https://www.twilio.com/try-twilio](https://www.twilio.com/try-twilio)

2. Sign up with email + phone verification

3. From the **Console Dashboard**, note:
   - **Account SID** — top left, starts with `AC`, 34 characters
   - **Auth Token** — click the eye icon to reveal, 32 hex characters

4. Save them:
   ```bash
   echo "TWILIO_ACCOUNT_SID=ACxxxxxxxx..." >> .env
   echo "TWILIO_AUTH_TOKEN=your32hextoken..." >> .env
   ```

### Step 3b: Set up WhatsApp Sandbox

1. In Twilio Console: **Messaging → Try it out → Send a WhatsApp message**

2. Follow the instructions to join the sandbox:
   - Send a WhatsApp message to `+1 415 523 8886`
   - Body: `join <sandbox-word>` (e.g., `join bright-eagle`)

3. After joining, note the **Sandbox number**: `whatsapp:+14155238886`

4. Save it:
   ```bash
   echo "TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886" >> .env
   ```

### Step 3c: Configure the webhook URL

After deploying to Kubernetes (you'll have a domain `api.nimbusflow.io`):

1. Twilio Console → **Messaging → Settings → WhatsApp Sandbox Settings**

2. Set **"When a message comes in"** to:
   ```
   https://api.nimbusflow.io/webhooks/whatsapp
   ```
   Method: **HTTP POST**

3. Set **"Status callback URL"** to:
   ```
   https://api.nimbusflow.io/webhooks/whatsapp/status
   ```

4. Click **Save**

### Verify

```bash
# Check Auth Token is correct by listing messages:
curl -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN \
  "https://api.twilio.com/2010-04-01/Accounts/$TWILIO_ACCOUNT_SID/Messages.json?PageSize=1"
# Expected: JSON with "messages" array (may be empty)
```

---

## Section 4: Gmail API + OAuth2 Credentials

Allows the FTE to read customer emails and send replies from a Gmail inbox.

### Step 4a: Enable Gmail API in Google Cloud Console

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)

2. Select the project you created in Section 1 (or create a new one)

3. Navigate to: **APIs & Services → Library**

4. Search for **"Gmail API"** → Click it → Click **"Enable"**

5. Also enable: **"Google Cloud Pub/Sub API"** (needed for push notifications)

### Step 4b: Create OAuth2 credentials

1. Go to: **APIs & Services → Credentials**

2. Click **"+ Create Credentials" → "OAuth 2.0 Client ID"**

3. If prompted: configure the **OAuth consent screen** first:
   - App name: `NimbusFlow FTE`
   - Support email: your email
   - Scopes: Add `https://www.googleapis.com/auth/gmail.modify`
   - Test users: Add your Gmail address
   - Save

4. Back in Credentials → Create OAuth 2.0 Client ID:
   - Application type: **Desktop app**
   - Name: `nimbusflow-fte`
   - Click **Create**

5. Click **"Download JSON"** → Save as `gmail_credentials.json`

6. Store it in a safe place (NOT in the repo):
   ```bash
   mkdir -p secrets
   mv ~/Downloads/client_secret_*.json secrets/gmail_credentials.json
   ```

### Step 4c: Run the OAuth2 flow to get gmail_token.json

This opens a browser for you to authorize the app — run this **once** locally:

```bash
# Install google-auth if not already installed:
pip install google-auth-oauthlib

# Run the token generation script:
python -c "
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
]

flow = InstalledAppFlow.from_client_secrets_file(
    'secrets/gmail_credentials.json',
    SCOPES,
)
creds = flow.run_local_server(port=0, open_browser=True)

import json
with open('secrets/gmail_token.json', 'w') as f:
    f.write(creds.to_json())

print('✅ Token saved to secrets/gmail_token.json')
print('   Expiry:', creds.expiry)
print('   Scopes:', creds.scopes)
"
```

**What happens:**
- A browser opens to Google's login page
- Log in with the Gmail account that will **receive customer support emails**
- Grant access to the app
- The browser shows "The authentication flow has completed"
- `secrets/gmail_token.json` is created with refresh token (does not expire)

### Step 4d: Verify Gmail access

```bash
python -c "
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json

creds = Credentials.from_authorized_user_file('secrets/gmail_token.json')
service = build('gmail', 'v1', credentials=creds)
profile = service.users().getProfile(userId='me').execute()
print('✅ Gmail access OK')
print('   Email:', profile['emailAddress'])
print('   Total messages:', profile['messagesTotal'])
"
```

---

## Section 5: Google Cloud Pub/Sub (Gmail Push Notifications)

Instead of polling Gmail every N seconds, we use Pub/Sub push notifications —
Google sends an HTTP POST to our webhook whenever new mail arrives.

### Step 5a: Create a Pub/Sub topic

```bash
# Install gcloud CLI: https://cloud.google.com/sdk/docs/install
gcloud auth login
gcloud config set project YOUR_GCP_PROJECT_ID

# Create the topic:
gcloud pubsub topics create nimbusflow-gmail-push

# Grant Gmail permission to publish to the topic:
gcloud pubsub topics add-iam-policy-binding nimbusflow-gmail-push \
  --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```

### Step 5b: Create a push subscription

```bash
# Create subscription pointing to your API webhook:
gcloud pubsub subscriptions create nimbusflow-gmail-sub \
  --topic=nimbusflow-gmail-push \
  --push-endpoint="https://api.nimbusflow.io/webhooks/gmail" \
  --ack-deadline=30 \
  --message-retention-duration=7d

# Verify:
gcloud pubsub subscriptions describe nimbusflow-gmail-sub
```

### Step 5c: Register Gmail watch

After deploying the API, register the Gmail push watch (re-runs every 7 days):

```bash
curl -X POST https://api.nimbusflow.io/webhooks/gmail/register \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "projects/YOUR_GCP_PROJECT_ID/topics/nimbusflow-gmail-push",
    "label_ids": ["INBOX"]
  }'
```

Or trigger via code:
```python
from production.channels.gmail_handler import GmailHandler
import asyncio

async def setup():
    handler = GmailHandler()
    result = await handler.setup_push_notifications(
        "projects/YOUR_GCP_PROJECT_ID/topics/nimbusflow-gmail-push"
    )
    print("Watch expiry:", result.get("expiration"))

asyncio.run(setup())
```

### Save to config

```bash
# Update configmap.yaml with your values:
sed -i "s/your-gcp-project-id/YOUR_ACTUAL_PROJECT_ID/" production/k8s/configmap.yaml
sed -i "s/nimbusflow-gmail-push/nimbusflow-gmail-push/" production/k8s/configmap.yaml
```

---

## Section 6: PostgreSQL

When deploying with Kubernetes (via Helm bitnami/postgresql):

```bash
# Choose a strong password:
export POSTGRES_PASSWORD="$(openssl rand -base64 24 | tr -d '=+/')"
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"   # Save this!

# Install PostgreSQL:
helm install postgres bitnami/postgresql \
  --namespace customer-success-fte \
  --set auth.database=fte_db \
  --set auth.username=fte_user \
  --set "auth.password=$POSTGRES_PASSWORD"

echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" >> .env
```

For local development with `docker-compose`, the password in `.env` is used
automatically. Change it from the default `changeme`:

```bash
# Generate a local dev password:
sed -i "s/changeme/localdevpass123/" .env
sed -i "s/changeme/localdevpass123/" docker-compose.yml
```

---

## Section 7: Final .env File

After completing all sections above, your `.env` should look like this:

```bash
# Copy the example:
cp .env.example .env

# Then edit .env and fill in real values for all REPLACE/placeholder fields.
# Minimum required values to start the system:

GEMINI_API_KEY=AIzaSy...                         # Section 1
OPENAI_API_KEY=sk-proj-...                        # Section 2
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxx     # Section 3
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx # Section 3
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886      # Section 3b
POSTGRES_PASSWORD=your-strong-password            # Section 6
GOOGLE_CLOUD_PROJECT=your-gcp-project-id          # Section 5

# These can keep their defaults for local dev:
POSTGRES_HOST=localhost
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
GEMINI_MODEL=gemini-2.0-flash
```

### Validate your .env

```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

required = [
    'GEMINI_API_KEY', 'OPENAI_API_KEY',
    'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN',
    'POSTGRES_PASSWORD',
]
missing = [k for k in required if not os.getenv(k) or 'REPLACE' in os.getenv(k,'')]
if missing:
    print('❌ Missing or unfilled:', missing)
else:
    print('✅ All required env vars are set')
"
```

---

## Section 8: Populate Kubernetes Secrets

After filling in all credentials, apply them to Kubernetes:

```bash
# Use the automated script (recommended):
./scripts/deploy.sh --secrets-only

# Or manually:
kubectl create secret generic fte-secrets \
  --namespace customer-success-fte \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=GEMINI_API_KEY="$GEMINI_API_KEY" \
  --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY" \
  --from-literal=TWILIO_ACCOUNT_SID="$TWILIO_ACCOUNT_SID" \
  --from-literal=TWILIO_AUTH_TOKEN="$TWILIO_AUTH_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic fte-gmail-secrets \
  --namespace customer-success-fte \
  --from-file=gmail_credentials.json=secrets/gmail_credentials.json \
  --from-file=gmail_token.json=secrets/gmail_token.json \
  --dry-run=client -o yaml | kubectl apply -f -
```

---

## Quick Checklist

```
□ 1. Gemini API key created at aistudio.google.com
□ 2. OpenAI API key created + billing added ($5 credit)
□ 3. Twilio account created + WhatsApp sandbox joined
□ 4. Twilio webhook URLs configured (after deploy)
□ 5. Gmail API enabled in Google Cloud Console
□ 6. OAuth2 credentials downloaded → secrets/gmail_credentials.json
□ 7. OAuth2 token generated → secrets/gmail_token.json
□ 8. Pub/Sub topic created + Gmail watch registered
□ 9. PostgreSQL password chosen + saved
□ 10. .env filled and validated (no REPLACE_ placeholders)
□ 11. kubectl create secret applied for fte-secrets + fte-gmail-secrets
□ 12. Run: ./scripts/test-deployment.sh to verify all connections
```
