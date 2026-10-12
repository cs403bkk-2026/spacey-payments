# Deploying the Payments skeleton

Deployment is not yet enabled. A successful `/health` check proves that this
revision can start, apply its migrations and reach its database; it does not
prove that the payments ledger works. No booking-flow cutover runs here.

## Service address and deployed revision

| | |
|---|---|
| Address | `https://payments.cs403bkk26.space` (proposed, not yet live) |
| Health | `GET /health` → `{"status": "ok", "revision": "<git sha>"}` |
| Deployed revision | none yet |

Update this table after each verified release: source SHA, image digest,
workflow run URL and the time `/health` reported that SHA.

## Platform setup

The platform owner must confirm the namespace, hostname and runtime variable path
before creating them. Proposed values are `payments`, `payments.cs403bkk26.space`
and `nomad/jobs/payments`. The job ID is `payments`; keep the variable under its
job-owned path so its workload identity can read it without broader variable
permissions.

The runtime database is `payments`, with login `payments_user`, membership role
`team_payments`, and ownership limited to that database's `public` schema.
`payments_user` has no password until the platform owner sets one. The platform
owner stores the connection URL in the runtime variable's `database_url` key. It
must never be passed as a job argument, committed, or copied into GitHub.

The service applies `migrations/*.sql` at startup, so the first deployment
creates the `payments` table and its types in that database.

Before release, the platform owner checks:

- The namespace, scoped deployment token and job-owned variable exist.
- Traefik watches the namespace and its discovery policy permits reading it.
- DNS and TLS reach the course ingress for the approved hostname.
- Nomad clients can pull the image from GHCR, using public package visibility
  or separately provisioned registry authentication.
- The application node can reach the database and has capacity for the job.
- GitHub's `production` environment requires the designated release review.

Set `DEPLOY_ENABLED=true` as a repository variable only after setup and review.
In the protected `production` environment set variables `NOMAD_NAMESPACE`,
`APP_HOSTNAME` and `RUNTIME_VARIABLE` to the approved identifiers, and secrets
`NOMAD_ADDR` and a fresh namespace-scoped `NOMAD_TOKEN`. An expired or
default-only token is unsuitable.

## Release and verification

After review and merge, the release owner manually runs the `release` workflow
from `main`. It runs the full test suite, builds an image, exercises that image
against disposable Postgres, and publishes that same image. Deployment uses its
registry digest, waits for Nomad's rollout, then requires `/health` to report both
`status: ok` and the exact source revision. A superseded main revision is rejected.

For an approved manual release, export the platform-provided `NOMAD_ADDR`,
`NOMAD_TOKEN`, `NOMAD_NAMESPACE`, `APP_HOSTNAME`, `RUNTIME_VARIABLE`, plus the
reviewed `REVISION` and immutable `IMAGE` reference, then run:

```bash
nomad job run -var="image=${IMAGE}" -var="revision=${REVISION}" \
  -var="namespace=${NOMAD_NAMESPACE}" -var="hostname=${APP_HOSTNAME}" \
  -var="runtime_variable=${RUNTIME_VARIABLE}" deploy/payments.nomad.hcl
curl --fail --silent --show-error "https://${APP_HOSTNAME}/health" |
  jq -e --arg revision "${REVISION}" '.status == "ok" and .revision == $revision'
```

Nomad can revert an unhealthy update to a previous stable job; the initial
deployment has no previous stable version. Public routing failure can occur even
after a healthy allocation. In either case the release owner inspects the failed
deployment and either stops the initial job or redeploys the recorded previous
digest/revision, then verifies health again. This single-instance job does not
promise uninterrupted updates. Migrations are not rolled back by redeploying an
older image.

## SRE check

The team SRE checks the deployment with their own access:

```bash
nomad job status -namespace=payments payments
curl --fail --silent --show-error https://payments.cs403bkk26.space/health
```

The revision in the response must match the deployed revision above. Record the
actual result or blocker in issue #1; platform verification alone does not
establish the SRE's access.
