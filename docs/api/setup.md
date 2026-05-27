# Headless Setup & API Keys

You can set up LibrisLog entirely via the API — no browser needed. This is useful for automation, CI/CD, or building your own frontend.

## 1. Check if Setup is Required

```bash
curl http://localhost:8000/api/auth/setup-required
```

Returns `{"required": true}` if no admin user exists yet.

## 2. Create the First Admin

```bash
curl -X POST http://localhost:8000/api/auth/setup \
  -H "Content-Type: application/json" \
  -c /tmp/librislog-cookies.txt \
  -d '{"firstname": "Admin", "lastname": "User", "email": "admin@example.com", "password": "your-secure-password"}'
```

This creates the first admin user and stores a session cookie in `/tmp/librislog-cookies.txt`. The `-c` flag saves the cookie for subsequent requests.

> This endpoint is only available when no admin exists. Once an admin is created, subsequent calls return `403 Forbidden`.

## 3. Create an API Key

```bash
curl -X POST http://localhost:8000/api/profile/api-keys \
  -H "Content-Type: application/json" \
  -b /tmp/librislog-cookies.txt \
  -d '{"description": "My API key"}'
```

Returns the raw key (shown only once):

```json
{
  "key": "lsk_abc123def456...",
  "api_key": { "id": 1, "key_prefix": "lsk_abc", "description": "My API key", ... }
}
```

**Save the `key` value — it cannot be retrieved again.**

## 4. Use the API Key

Include it in the `X-API-Key` header:

```bash
curl -H "X-API-Key: lsk_abc123def456..." http://localhost:8000/api/books
```

## Full Script (Linux/macOS)

```bash
# Create first admin and save session cookie
curl -X POST http://localhost:8000/api/auth/setup \
  -H "Content-Type: application/json" \
  -c /tmp/librislog-cookies.txt \
  -d '{"firstname": "Admin", "lastname": "User", "email": "admin@example.com", "password": "your-password"}'

# Create API key
response=$(curl -s -X POST http://localhost:8000/api/profile/api-keys \
  -H "Content-Type: application/json" \
  -b /tmp/librislog-cookies.txt \
  -d '{"description": "CLI key"}')

api_key=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])")
echo "API Key: $api_key"

# Test it
curl -H "X-API-Key: $api_key" http://localhost:8000/api/books
```

## Full Script (Windows PowerShell)

```powershell
# Create first admin
Invoke-RestMethod -Uri http://localhost:8000/api/auth/setup `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"firstname":"Admin","lastname":"User","email":"admin@example.com","password":"your-password"}' `
  -SessionVariable session

# Create API key
$response = Invoke-RestMethod -Uri http://localhost:8000/api/profile/api-keys `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"description":"CLI key"}' `
  -WebSession $session

Write-Host "API Key: $($response.key)"

# Test it
Invoke-RestMethod -Uri http://localhost:8000/api/books `
  -Headers @{"X-API-Key" = $response.key}
```
