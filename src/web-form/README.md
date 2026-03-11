# Web Support Form — Prototype Placeholder

The complete React/Next.js Web Support Form is built in:
`production/api/web-form/SupportForm.jsx`

During incubation, the web form is simulated via the prototype CLI.

## Quick Test (Incubation)

```bash
python src/agent/prototype.py \
  --channel web_form \
  --customer-id "test@example.com" \
  --customer-name "Test User" \
  --message "I need help with the GitHub integration"
```

## Production Form Location

`production/api/web-form/` contains the full Next.js component with:
- Form validation
- Category and priority selection
- Ticket submission to FastAPI
- Success state with ticket ID
- Error handling
