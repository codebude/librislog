# Telemetry

LibrisLog sends minimal, **anonymous** installation telemetry to help the project understand how many installations exist and on which platforms they run. This is an installation census, not user-behavior tracking.

## What is collected

Only the following fields are transmitted: once when LibrisLog starts, then every 24 hours.

| Field | Meaning | Example |
|-------|---------|---------|
| `message_version` | Telemetry schema version (always 1) | `1` |
| `installation_id` | Random UUIDv4 generated on first startup | `f47ac10b-58cc-4372-a567-0e02b2c3d479` |
| `version` | LibrisLog version | `v1.2.3` |
| `os` | Operating system seen by LibrisLog | `linux`, `windows`, `darwin` |
| `architecture` | CPU architecture | `amd64`, `arm64`, `unknown` |
| `runtime` | Container or directly on the host | `container`, `baremetal`, `unknown` |
| `client_ts` | Timestamp of the heartbeat | ISO 8601 UTC |

The runtime is reported as `container` when a container marker file (`/.dockerenv`, `/.containerenv`) is present or a container runtime is visible in the process cgroup paths (this covers Docker, Podman, containerd and Kubernetes), as `baremetal` when no container is detected, and as `unknown` only if the environment cannot be determined. The cgroup check derives a simple yes/no signal — no cgroup or container IDs are ever read, stored, or sent.

The `installation_id` is a cryptographically random UUIDv4 that is **not** derived from your MAC address, hostname, `/etc/machine-id`, or any other hardware identifier. It is stored in the LibrisLog database, so it stays stable across container restarts and updates — but is regenerated if you delete the database and reinstall.

## What is NEVER collected

LibrisLog deliberately does **not** collect:

- IP addresses or geographic information
- Hostnames
- Usernames or user IDs
- MAC addresses or `/etc/machine-id`
- Container IDs or Docker host information
- Book data, book counts, or user counts
- Reading activity, search queries, or feature usage
- Database contents or environment variables
- Filesystem paths
- User-Agent or other client-identifying details (telemetry requests send only a fixed, generic user-agent string, never browser or OS specifics)

The payload is built from a strict allow-list: only the fields listed above may ever be sent.

## When telemetry is sent

One heartbeat is sent when LibrisLog starts, then once every 24 hours. Telemetry is **best-effort**: if the telemetry server is unreachable, the request is dropped silently, no retries are attempted, and LibrisLog continues to work normally.

## Transparency & verification

Telemetry is fully verifiable by anyone:

- **The telemetry server is open source.** The complete code that ingests, stores, and serves telemetry data is public at [github.com/codebude/librislog-telemetry](https://github.com/codebude/librislog-telemetry). You can inspect it to confirm that nothing beyond the allow-listed fields above is ever stored or exposed.
- **The results are public.** The aggregated census is published for everyone to see at [metrics.librislog.app](https://metrics.librislog.app/) — total and active installations, versions in use, operating systems, architectures, and runtimes. There is no private dashboard: the exact same data shown to the project maintainers is visible to anyone.

## How to disable telemetry

Set the following in your `.env` file:

```bash
TELEMETRY_DISABLED=true
```

Restart LibrisLog after changing it. No telemetry is sent while `TELEMETRY_DISABLED=true` is set.