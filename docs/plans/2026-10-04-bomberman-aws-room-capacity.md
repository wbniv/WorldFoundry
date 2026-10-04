# Bomberman: simultaneous-room capacity on AWS and Cloudflare

Status: planned for review. No hosting resources have been created and no capacity measurements have been run. The filename is retained to preserve existing links.

## Objective

Measure how many simultaneous Internet matches the phase-one server can sustain while keeping movement, bomb timing and room joining responsive. Produce a tested room limit, a cost estimate and an upgrade trigger. Connection count alone is not a capacity result.

Companion to the [online multiplayer plan](2026-10-04-bomberman-online-multiplayer.md). Each room has two-to-four active players. Phase one has one existing Chromecast display in total; it joins one room as a display client and does not consume a player slot. Multiple local TVs belong to phase two.

## Execution order and decision gates

- [ ] Finish reviewing the multiplayer scope, protocol and acceptance budgets. Implementation remains pending review.
- [ ] Implement the shared authoritative simulation and room protocol for two-to-four players, including sequenced input, snapshots, room isolation, scoring and reconnect. Pass functional checks before treating throughput as capacity.
- [ ] Build and validate the JMeter one-room baseline on an isolated development server: exercise two, three and four players plus the single display, acknowledge the correct input sequences, consume snapshots and maintain intended input pacing. Save evidence that the generator reproduces the real protocol reliably.
- [ ] Qualify AWS and Cloudflare using the same workload and timing budgets. Start with one generator; add engines when measured generator saturation prevents the intended workload. Keep peak concurrency and monthly room-hours as separate comparison dimensions.
- [ ] Review the measured provider comparison, choose hosting and set a tested admission limit with headroom. Record upgrade triggers and operating costs before regular-play deployment. Writing this plan does not provision infrastructure.

Local protocol and JMeter work can proceed independently of a permanent hosting choice once implementation resumes. Provider-specific prototypes are comparison targets; neither is the selected production deployment until the results are reviewed.

## AWS baseline and alternatives

Use an isolated Linux Amazon Lightsail instance as the first measurement target. The current public-IPv4 bundle is listed at $7/month with 1 GB RAM, two vCPUs, 40 GB SSD and 2 TB transfer; confirm bundle availability, region-specific transfer allowance and current billing before provisioning. Pricing checked 2026-10-04 from [AWS Lightsail pricing](https://aws.amazon.com/lightsail/pricing/). Do not include promotional credits in the ongoing cost estimate.

The two vCPUs are burstable. AWS documents a 10% performance baseline per vCPU for the $7 Linux bundle, so a short run on accumulated burst capacity cannot establish sustainable room capacity. Record credit/burst metrics throughout qualification. See [AWS baseline documentation](https://docs.aws.amazon.com/lightsail/latest/userguide/baseline-cpu-performance.html) and [Lightsail metrics](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-resource-health-metrics.html).

Run Node.js, the actual HTTPS reverse proxy, supervisor and bounded logging on the target, matching the proposed deployment. Pin runtime/dependencies, build revision, simulation and snapshot rates, compression, proxy settings and operating-system limits. A single Node.js event loop does not automatically parallelize simulation over two cores.

EC2 remains an alternative if existing AWS infrastructure can be reused or tests require more predictable compute. Record its exact instance/architecture/region and include compute, storage, transfer, public addresses and any CPU-credit charges. EC2 public IPv4 is separately priced at $0.005/address-hour before applicable credits; Lightsail's selected IPv4 bundle already includes its public address. See [AWS public IPv4 pricing](https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/). Do not add an EC2 IPv4 charge to the Lightsail bundle.

If Lightsail cannot meet the target sustainably, test the next suitable AWS size or a fixed-performance EC2 option. Requalify on that exact target rather than extrapolating from advertised vCPU count. AWS and Cloudflare are candidates; DigitalOcean is not the deployment baseline.

## Cloudflare comparison

Compare hosting the game on Cloudflare with hosting it on AWS. Cloudflare DNS/proxy in front of an AWS server is a separate hybrid option; it does not move the authoritative simulation to Cloudflare.

| Candidate | Cost model | Implementation and operation | Capacity question |
|---|---|---|---|
| AWS Lightsail | $7/month baseline bundle, plus applicable extras | Reuse the Node server; maintain Linux, TLS, service updates and monitoring | How many rooms fit within sustainable CPU, memory and transfer? |
| AWS EC2 | Instance, disk, transfer, address and possible CPU-credit charges | Reuse Node; greater sizing/network flexibility and more billing configuration | Does the exact instance justify its cost over Lightsail? |
| Cloudflare Workers + Durable Objects | $5/month paid-plan minimum plus metered overages | Shared rules remain reusable; adapt HTTP, WebSockets, timers and lifecycle; one authoritative object per room | Does each room meet timing budgets, and do many rooms remain reliable within account limits? |
| Cloudflare Containers | Paid-plan minimum plus metered CPU, provisioned memory/disk and egress | Containerize Node; validate routing, lifecycle and deployment adapters | Does lower porting effort justify metered container costs? |

These effort comparisons are architectural estimates, not completed compatibility tests. AWS is the simplest initial implementation candidate because the current server already uses Node. Cloudflare Durable Objects are a managed alternative that distributes room ownership without maintaining a Linux VM. Benchmark before choosing; advertised automatic scaling is not measured room capacity.

Cloudflare prices checked 2026-10-04: [Workers](https://developers.cloudflare.com/workers/platform/pricing/), [Durable Objects](https://developers.cloudflare.com/durable-objects/platform/pricing/) and [Containers](https://developers.cloudflare.com/containers/platform/pricing/). Workers have no additional egress charge; Containers have separate egress billing. The $5 minimum is per account, with shared allowances, not per room.

For Durable Objects, duration includes 400,000 GB-s/month, then $12.50 per million GB-s, rounding excess up to the next million. Each awake room is billed at 0.128 GB regardless of actual memory. One awake room-hour consumes 460.8 GB-s: roughly 868 room-hours fit the duration allowance. Examples, assuming unused account allowances:

| Monthly awake room-hours | Base plan + duration only |
|---|---|
| 60 | $5 |
| 600 | $5 |
| 1,000 | $17.50 |

These exclude request/storage/other usage and taxes. Incoming WebSocket messages count at 20:1; outgoing messages are uncharged. Measure actual input traffic. Free-plan limits cause operations to fail when exceeded, so free service is not the regular-play capacity assumption.

A running simulation timer prevents hibernation; an active match costs awake duration even between inputs. Stop timers in eligible idle states, use hibernatable WebSockets and checkpoint enough state to reconstruct the room after eviction. Validate pause/reconnect semantics without writing every simulation tick to storage. See [object lifecycle](https://developers.cloudflare.com/durable-objects/concepts/durable-object-lifecycle/).

One room still has one authoritative location. Default placement is near its first request; location hints are best effort and objects do not currently relocate automatically. Compare measured RTT from participants' locations, including host/remote room creation, rather than assuming edge hosting removes distance. See [data location](https://developers.cloudflare.com/durable-objects/reference/data-location/).

## Comparable Cloudflare qualification

- [ ] Prototype a Durable Object room adapter with the same rules, protocol, simulation/snapshot rates and client prediction as AWS. Record porting effort and incompatibilities. Do not change gameplay to make a provider pass.
- [ ] Run the same baseline, room-count sweep, legal bursts, churn, network, soak and overload workloads against deployed objects, using a separate load generator. Capture per-room timing so separate objects cannot hide a starved match in pooled results.
- [ ] Replace VM-specific credit/host-memory gates with applicable runtime memory, CPU/event limits and account limits. Record the exact limits at test time; retain the shared correctness, input, cadence, cleanup and headroom requirements.
- [ ] Exercise first activation, eviction/hibernation, rehydration, reconnect and deployment/restart recovery. Measure room placement and mixed-geography RTT; verify live ticks continue reliably under the deployed runtime.
- [ ] Measure actual awake duration, requests, storage operations, Worker usage and bytes. Account for idle rooms, post-match timers and reconnect grace periods, not just time marked playing. Compare predicted bills with provider usage metrics and apply billing-unit rounding.
- [ ] Establish separate per-room resource limits and an application-level room/admission budget; managed distribution does not imply unlimited affordable room creation. Repeat the 25% excess-demand test with rejection and reconnection behavior.
- [ ] If Containers are a serious candidate after pricing the intended configuration, run the same Node workload there and capture CPU, provisioned memory/disk, egress, idle shutdown and recovery costs separately from Durable Objects.

The final comparison must include qualified simultaneous rooms, p95/p99 timing, geographic RTT, monthly costs at the same room-hours, implementation effort and ongoing maintenance. Compare 60, 600 and 1,000 monthly room-hours as cost scenarios independently of peak concurrency. A room-hour is one room awake for one hour, not one player-hour. State whether each figure is measured or estimated. No provider is selected by this plan alone.

## Preconditions and test isolation

- [ ] Complete the shared rules, input sequencing, room roles, reconnect and snapshot protocol before qualifying capacity. The current incomplete two-player draft may be profiled for development, but its results do not qualify the final four-player implementation.
- [ ] Confirm region and relevant billing/resource settings. Use a dedicated test target and a separate load generator; do not stress unrelated AWS services or existing live matches.
- [ ] Run deterministic rules and room-isolation tests first. A fast server with incorrect scoring, timing or isolation fails qualification.
- [ ] Record instance ID/bundle, architecture, region, source revision, dependency lockfile hashes, runtime, TLS/proxy path, tick rate, snapshot rate and starting burst capacity.
- [ ] Use one common set of performance knobs for all room counts. Document any change and restart comparisons when a knob changes.

This plan has no new visible product surface, so no UI mockup is needed. The deliverable is measured evidence and a capacity report.

## Load generator

Use Apache JMeter as the load generator, following Will's preference. Commit a parameterized `.jmx` plan, properties, external Groovy scripts and seeded workload data. Use the real room/create/join/ready/input protocol. Each simulated client opens a separate authenticated session, consumes snapshots and records monotonic timing. It must not write server positions, invent score updates or bypass normal action limits.

Use [WebSocket Samplers by Peter Doornbosch](https://github.com/Luminis-Arnhem/jmeter-websocket-samplers/blob/master/README.md) for WSS and explicit open/read/write/close operations. It allows one active connection per JMeter thread: model one thread per player or display, with room/slot assignment shared through test data. Correlate acknowledgments with input sequence numbers; unsolicited snapshots are not action replies. Handle fragmented frames and preserve snapshot sequence accounting. Configure filtered-frame byte accounting if filters are used, then reconcile with host/provider network counters.

Use compiled/cached JSR223 Groovy for seeded bot decisions, protocol handling and assertions. Keep each client's state in its own thread variables; room coordination must be bounded and must not serialize unrelated clients. A bounded read/write loop must keep consuming snapshots while maintaining scheduled input. Record intended versus actual send times, receive backlog and missed deadlines. A blocking read that suppresses input under load makes the run invalid; JMeter sampler elapsed time alone is not action acknowledgment latency. Validate this at one-room baseline before scaling. If this loop cannot meet pacing, first evaluate a small asynchronous JMeter Java sampler rather than replacing JMeter with a separate Node generator.

Author/debug in the GUI; run measurements in CLI mode with CSV JTL output and expensive result-tree listeners disabled. Pin JMeter, Java, plugin and script versions. Monitor generator CPU, heap, GC, thread counts and schedule drift. Split across independent CLI engines if needed, assigning disjoint room/client IDs and seeds; an engine failure invalidates its measurement window. See [Apache JMeter best practices](https://jmeter.apache.org/usermanual/best-practices.html).

Additional engines must use identical test versions and workload settings. Preserve generator, room and client identifiers in merged results, align measurement windows and keep per-engine achieved rates visible. Increase aggregate offered load rather than accidentally duplicating room identities or reusing sessions. Run all generators separately from the game server. Generators in different regions can also measure geographic RTT; report that experiment separately from extra engines used to increase load capacity.

Use seeded bots to move through corridors, dig walls, collect pickups and drop legal bombs, then ready/rematch after rounds end. Measure active simulation occupancy; a run consisting mostly of waiting/dead rooms is not equivalent to simultaneous live matches. Keep at least 90% of rooms playing in the peak-active workload. Also test the natural mixture of lobby/countdown/active/result states separately.

Include high legitimate bomb/pickup counts, long flames and same-tick chains. Drive these through legal play; if a preconditioned arena fixture is needed for repeatability, label it and keep all subsequent input/limits identical to production. Test synchronized chain bursts as well as randomly staggered room activity.

For N four-player rooms, phase one's connection model is **4N player connections + one Chromecast display connection**, not five displays per room. Cover two- and three-player rooms too. Exercise capped spectators and reject excessive spectators so an unbounded display count cannot invalidate the room limit.

Keep the generator off the game server. Record generator CPU, event-loop delay, achieved input rate and snapshot-consumption rate. If it saturates, split generators and rerun; do not blame a generator bottleneck on the target. Packet drops caused by the harness also invalidate that run.

## Instrumentation

Collect one-second samples and interval histograms, preserving per-room and per-client distributions rather than only pooled averages:

| Measurement | What it establishes |
|---|---|
| Simulation step duration, scheduling lateness, missed steps and catch-up backlog | Whether more rooms delay game time and blast decisions |
| Input arrival → server application; action acknowledgment time | Server responsiveness separately from network round-trip time |
| Snapshot emission interval, sequence gaps and age at clients | Whether boards remain current under load |
| Node event-loop delay and GC pauses | Whether serialization, timers or memory pressure block all rooms |
| Process RSS/heap, whole-host available memory, swap/OOM, proxy usage | Memory capacity including the operating system and TLS service |
| Per-core CPU plus AWS utilization and burst capacity | Immediate headroom and sustainable CPU budget |
| Encoded snapshot size, WebSocket backlog and actual network bytes | Bandwidth cost and slow-client effects |
| Ready/round/match outcomes and room/session cleanup counts | Correctness and leaks under repetition |

Use server-local monotonic clocks for processing delays and client-local clocks for round-trip measurements. Never subtract unsynchronized browser and server wall clocks to claim one-way latency. Use RTT-controlled test paths to separate Internet delay from server degradation.

## Test sequence

1. **One-room baseline:** two, three and four players, then four players plus the single display. Warm up five minutes and sample fifteen minutes. Establish baseline game timing, memory, CPU, snapshot bytes and RTT.
2. **Incremental load:** test 1, 2, 4, 8, 16, 32 rooms and continue doubling only while resource and responsiveness gates pass. At each level use five-minute warmup plus fifteen-minute measurement. Repeat the critical levels three times with different seeds/time windows. Refine the first failing interval with intermediate room counts.
3. **Worst legal bursts:** synchronize maximum-capacity legal bomb chains and round transitions at candidate limits. Compare against staggered matches to expose shared event-loop spikes.
4. **Lifecycle/churn:** create and abandon rooms, repeatedly rematch, reconnect 25% of clients at once, and alternate joining/leaving spectators. Confirm expired rooms/sessions and simulation timers are actually released. Keep unrelated active rooms progressing during the churn.
5. **Network variants:** use isolated traffic shaping or a harness proxy for 50/150/300 ms RTT, jitter and short disconnects. Include a slow-reading display. Bound each socket's send backlog and disconnect a stale slow consumer rather than slowing every room. Do not change the host's unrelated network routes.
6. **Sustained CPU:** run the candidate limit for at least two hours while recording burst capacity. If credits steadily decline, calculate expected exhaustion from the observed drain and extend to depleted/low-credit conditions on the isolated instance, or reduce the limit. A run ending with declining credits cannot qualify continuous operation. Record separate short-session burst capacity only if its duration is explicitly bounded.
7. **Soak and recovery:** run the selected lower limit for eight hours with repeated rounds/churn. Return to idle, collect a settled heap/memory sample and restart the service; verify room cleanup, healthy joining and predictable loss of transient rooms on server restart. Repeat critical sustainable-load checks on another day.
8. **Overload:** submit 25% more room demand than the proposed admission limit and a bounded connection/join burst. Reject new room creation with a clear busy response while allowing existing participants to reconnect. Existing matches must retain the same correctness/responsiveness gates. Never evict an active room merely to admit a new one.

During tool-driven runs, stream progress and sample results rather than blocking silently for the full duration. Provisioning and test execution remain future work; writing the plan starts none of these loads.

## Initial acceptance gates

These are proposed measurable budgets, to be reviewed against the one-room baseline before the full sweep. Keep them fixed once the sweep begins.

| Gate | Proposed requirement |
|---|---|
| Correctness | Zero cross-room state/input effects, duplicate bomb actions, incorrect round awards or unexplained simulation divergence |
| Simulation | p99 step execution < half the configured tick interval; p99 scheduling lateness ≤ one interval; late-by-more-than-one-interval steps < 0.1%; no growing catch-up backlog |
| Server input delay | p95 ≤ 25 ms and p99 ≤ 50 ms from validated message arrival to application/acknowledgment, with no unexplained degradation > one tick relative to the one-room baseline |
| Snapshot cadence | p99 emission gap ≤ two configured snapshot intervals on the healthy path; no sustained queued snapshots for healthy clients |
| Memory | At least 20% whole-host memory remains available; no OOM or sustained swapping; no monotonic retained-room/timer/heap growth after repeated cleanup |
| Sustained CPU | Steady load stays within the instance's sustainable budget with operating headroom; no sustained burst-capacity drain used to justify the continuous limit |
| Lifecycle | Every abandoned room/timer expires within its configured grace/expiry allowance; reconnect restores the correct identity without stale held input |
| Generator validity | Generator remains below its own saturation point and achieves the configured traffic and active-room occupancy |

Report p50/p95/p99, counts, worst room/client and sampled traces. An aggregate percentile cannot hide a consistently starved room. Internet action RTT has a separate distribution and is not expected to meet a local-server processing budget.

## Turning results into a room limit

Publish the highest repeatably passing room count for each workload, then use the lowest of those maxima. Reserve at least 25% capacity headroom by selecting a lower **actually tested** count. Verify that the selected limit passes low-credit, soak and overload checks; a formula alone does not qualify it. If only one room passes and headroom cannot be demonstrated, report that limitation rather than promising general simultaneous-room capacity.

Define the admission cap over allocated match rooms, including paused/countdown/result rooms, so they cannot all resume into more active simulations than qualified. Separately cap lobby-only rooms, pending sockets, active players and spectator streams; record those limits in the report. The display is not a player slot. If CPU or memory thresholds are exceeded at the cap, stop admitting new rooms and investigate before increasing it.

The upgrade trigger is a need for more sustained concurrent rooms than the qualified limit, or repeated timing/CPU/memory failures at ordinary admitted load. Do not scale because of a single uninvestigated outlier. Requalify after changes to simulation rate, snapshot payload, compression, prediction protocol, maximum bombs, runtime or instance class.

## Cost and evidence deliverables

Save the JMeter `.jmx` plan, properties, Groovy scripts, dependency versions, seeds/configurations, CSV JTL results, full logs, latency histograms, sampled match assertions, AWS burst/CPU/network metrics and resource inventory in a dated bundle under `docs/diagnostics/bomberman-capacity/`. Generate a standalone report with room count versus timing/CPU/memory charts, pass/fail table, exact qualified instance, room/client caps, constraints and CLI rerun commands. Label unmeasured levels and any preliminary prototype results.

Cost the tested AWS bundle at its current listed price, then include actual optional snapshots, transfer above the region allowance and any temporary load-generator resources. Record and remove temporary resources when testing ends. Separate one-time validation charges from monthly operation; no purchase/provisioning is authorized by this planning task alone.

Calculate transfer from measured encoded messages and host network counters: room-hours × bytes per second × 3,600, plus static assets/reconnect overhead. Do not double-count the one Chromecast across every phase-one room. Record whether provider transfer allowances count inbound plus outbound usage. Compare the $7 Lightsail tier and any actually tested upgrade, and state how many simultaneous rooms each can sustainably admit.

## Completion checklist

- [ ] Confirm AWS and Cloudflare targets and capture current pricing/billing assumptions.
- [ ] Qualify the Cloudflare room adapter with comparable workloads and report cost/effort alongside AWS.
- [ ] Implement the protocol-realistic JMeter plan and server instrumentation; validate snapshot consumption, acknowledgment correlation and input pacing before scaling.
- [ ] Pass baseline, scale sweep, legal bursts, lifecycle and network tests.
- [ ] Pass low-credit/sustainable CPU and eight-hour soak checks.
- [ ] Select and validate an admission limit with capacity headroom and overload behavior.
- [ ] Record cost, artifacts, repeatable commands and cleanup receipts; link results from the multiplayer plan.
