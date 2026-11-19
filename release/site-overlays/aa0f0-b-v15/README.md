# AA0F0-B V1.5 · opt-in performance candidate

V1.5 preserves V1.4 physical grasp, TCP, speed, collision, verification, and
230 mm lift parameters. It changes only preparation:

1. Pre-initialize the persistent planner using the construction profile from
   the successful tool-3 V1.4 run `e2ede7bef25a42faa2a24c81abb50cd6`.
   This request has `initialize_only=true` and performs no solve or motion.
   The formal solve still uses the **new** observation and SceneSnapshot.
2. Read both controllers concurrently in each before/after read-only FK audit.
3. Write `v15-runtime-binding.json` and `v15-planner-performance.json` in the
   new run directory. A runtime-key mismatch fails before motion.

The site source files contain later demo extensions absent from the GitHub
development branch. This overlay was built against the exact site file hashes;
`install.py` refuses any changed baseline and backs up each replaced file.
It does not restart the backend or start a robot task. V1.4 stays the default;
select `function-AA0F0-B-v1.5` explicitly for a supervised comparison.

Read-only site verification before packaging: the prewarm request's runtime
construction key matched all twelve most recent saved formal requests, and
setting `initialize_only=true` preserved the source key. These are key checks,
not a measured V1.5 latency result.

Expected comparison: V1.4 versus V1.5 on the same station, object and tool 3;
record observation, planner initialization, pure solve, total planning, total
preparation, first-motion latency, runtime cache hit, and terminal result.
The previous frozen replay suggests a possible 23 s → 4 s planner-request
change when cache reuse succeeds; it is not an online V1.5 measurement.
