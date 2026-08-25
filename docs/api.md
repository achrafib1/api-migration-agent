# Backend API contract

The MVP API operates only on the bundled trusted AtlasPay example. Clients
cannot supply filesystem paths, commands, repositories, model names, or provider
credentials.

## List approved migration targets

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/migrations/targets"
```

The response contains stable IDs, names, and descriptions only. Server paths are
never part of this contract. The initial catalog contains `atlaspay`; later
operator-registered trusted projects use the same target contract.

## Start a migration

```powershell
$run = Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/migrations" `
  -ContentType "application/json" `
  -Body '{"target_id":"atlaspay"}'
$run.run_id
```

The response initially has `status=awaiting_review`, preserves the selected
`target_id`, and includes typed action summaries and questions. The same target
identifier remains present in review, finalization, and polling responses.

Unknown target IDs are rejected. Requests cannot supply repository or
specification paths.

## Submit the human decision

```powershell
$body = @{ decision = "approve"; answers = @{} } | ConvertTo-Json
$completed = Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/v1/migrations/$($run.run_id)/review" `
  -ContentType "application/json" `
  -Body $body
```

Use `decision=reject` to terminate without workspace creation or patching.

## Retrieve the latest snapshot

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "http://localhost:8000/api/v1/migrations/$($run.run_id)"
```

Snapshots are process-local and disappear after backend restart. They contain
review metadata, patch-operation metadata, validation metadata, and the final
report. They exclude source code, patch text, model output, test output,
workspace paths, settings, and credentials.

## Errors

Domain failures use a constant response shape:

```json
{
  "error_code": "STABLE_ERROR_CODE",
  "message": "A sanitized public message."
}
```

Unknown or expired run IDs return `404`. Invalid review decisions return `400`.
