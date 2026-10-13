# Deploying Payments

Deployment is enabled. A successful `/health` check proves that this revision
can start, apply its migrations and reach its database; the release also checks
that a payment endpoint rejects a call without the service token. Neither proves
the booking flow: Purchase is not yet calling this service, and no cutover runs
here.

## Service address and deployed revision

| | |
|---|---|
| Address | `https://payments.cs403bkk26.space` |
| Health | `GET /health` → `{"status": "ok", "revision": "<git sha>"}` |
| Deployed revision | `decf946e932c87dba7d57b53c734ef5cba1c9637` (skeleton, `/health` only), [run 38202461249](https://github.com/cs403bkk-2026/spacey-payments/actions/runs/38202461249), 2026-10-12 04:06 UTC |

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

The same variable holds `service_token`, the shared secret Purchase sends as
`X-Service-Token`. The job refuses to start without that key, so add it before
releasing a revision that reads it, keeping the existing key:

```bash
nomad var put -namespace=payments nomad/jobs/payments \
  database_url="$(nomad var get -namespace=payments -item=database_url nomad/jobs/payments)" \
  service_token="$(openssl rand -hex 32)"
```

Purchase needs the same value as its `SERVICE_TOKEN`, passed out of band.
Changing the variable restarts the task.

The service applies `migrations/*.sql` at startup, so the first deployment
creates the `payments` table and its types in that database.

Before release, the platform owner checks:

- The namespace, scoped deployment token and job-owned variable exist.
- Traefik watches the namespace and its discovery policy permits reading it.
- DNS and TLS reach the course ingress for the approved hostname.
- Nomad clients can pull the image from GHCR, using public package visibility
  or separately provisioned registry authentication.
- The application node can reach the database and has capacity for the job.
- GitHub's `production` environment does not require a separate release approval.

Set `DEPLOY_ENABLED=true` as a repository variable only after setup and review.
In the protected `production` environment set variables `NOMAD_NAMESPACE`,
`APP_HOSTNAME` and `RUNTIME_VARIABLE` to the approved identifiers, and secrets
`NOMAD_ADDR` and a fresh namespace-scoped `NOMAD_TOKEN`. An expired or
default-only token is unsuitable.

## Release and verification

Every push to `main` starts the `release` workflow. The release owner can also
retry it manually from `main`. With `DEPLOY_ENABLED=true`, deployment proceeds
automatically after the build checks pass, without a separate production approval.
The workflow runs the full test suite, builds an image, exercises that image
against disposable Postgres, and publishes that same image. Deployment uses its
registry digest, waits for Nomad's rollout, then requires `/health` to report both
`status: ok` and the exact source revision, and `GET /payments` without a token to
answer `401`. A superseded main revision is rejected.

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
