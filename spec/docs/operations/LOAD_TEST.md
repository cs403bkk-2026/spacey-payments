# Load / capacity test

Script: `scripts/load_test.py`. Hits `GET /spaces` repeatedly with a fixed number of requests, run at two different concurrency levels, and reports request volume, latency, and failure rate for each.

## Conditions

- App run with `gunicorn -w 2` (2 sync workers) - the same worker count
  used by the Dockerfile.
- Database: local Postgres via Docker Compose, seeded with one space.
- 200 requests per run, only `--concurrency` changed between runs.
- Run on a single developer laptop, not the class deployment target -
  absolute numbers will differ there, but the relative pattern (what
  breaks first as load increases) should hold.

## Results

| Concurrency | Requests | Failures | Median latency | p95 latency | Throughput |
|---|---|---|---|---|---|
| 5  | 200 | 0 (0.0%) | 2.2 ms  | 3.7 ms  | ~1932 req/s |
| 50 | 200 | 0 (0.0%) | 21.1 ms | 23.2 ms | ~2047 req/s |

## Conclusion

No requests failed at either level, so the app doesn't fall over under
this load. Throughput actually held up well, even ticking up slightly
from concurrency 5 to 50 (~1932 to ~2047 req/s). But median latency rose
about 9.6x over the same jump (2.2ms -> 21.1ms) - individual requests
took much longer to complete, even though the server kept up overall.

That pattern points to the **worker pool** as the first bottleneck, not
the database or the app logic: with only 2 sync gunicorn workers, extra
concurrent requests have to queue and wait for a free worker instead of
being handled in parallel. Aggregate throughput doesn't collapse, but
each individual request waits longer in that queue - which shows up
exactly as rising latency, not failures.

Next step if this needs to scale further: increase the gunicorn worker
count (or switch to a threaded/async worker class) before looking at the
database - the database wasn't the limiting factor at this load level.
