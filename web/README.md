# API Migration Agent web application

This pnpm-managed Next.js application provides the human review surface for the
API Migration Agent. It starts the trusted AtlasPay workflow, presents only
evidence-backed migration actions, collects explicit approval, and renders the
content-safe validation report.

The current MVP deliberately operates only on the bundled trusted AtlasPay
example repository. It does not accept a user path, upload, Git URL, or
arbitrary validation command. General repository intake is a future security and
product-design expansion, not an undocumented capability of this interface.

The selection contract is already implemented: the web app loads the backend's
content-safe target catalog and starts runs with a stable target ID. AtlasPay is
currently the only registered target; private filesystem paths never enter the
browser or an API request.

## Local development

Run the FastAPI backend on `http://localhost:8000`, then start the frontend:

```powershell
pnpm install
pnpm run dev
```

Open `http://localhost:3000`. The optional non-sensitive
`NEXT_PUBLIC_API_BASE_URL` build-time variable may select another HTTP(S)
backend origin. URLs containing credentials are rejected. In accordance with
the repository security policy, no environment file is included or documented.

## Quality checks

```powershell
pnpm run lint
pnpm run typecheck
pnpm run test
pnpm run build
```

The browser never applies patches or makes security decisions. It delegates the
workflow to the backend and displays content-safe records; the backend remains
authoritative for evidence, approval enforcement, filesystem confinement, and
validation.

Component tests cover start, approval, required-answer handling, rejection, and
final reporting. API-client tests additionally verify URL safety, run-ID
encoding, malformed-response rejection, and sanitized error behavior.
