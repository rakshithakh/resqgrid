# ResQGrid

A flood-relief coordination portal for reporting emergencies, tracking requests, dispatching relief vehicles, and visualizing flood and route data on an interactive map.

## How ResQGrid Works

### The flow in one breath

Message in, understood, located, trust-scored, prioritised, routed on real roads, approved by an officer, shown on a map.

### Plain-language answers

**What does the AI do?** It reads informal multilingual messages and fills a fixed form: needs, number of people, vulnerable groups, urgency. It never decides routes or allocations. Without a Gemini key, a built-in rules extractor does the same job, and the receipt shows which extractor was used.

**Why not let the AI plan routes?** It cannot guarantee that a plan is feasible or optimal. Routing uses shortest paths and an optimiser, so every decision can be checked.

**How is the location found?** From a ward or landmark name in the text, matched against OpenStreetMap place names, or from phone GPS snapped to the nearest road point. If both exist and disagree by more than 1.5 km, trust drops and an officer reviews it.

**What is the trust score?** It starts at 55%. Place found +10, phone verified +5, GPS agrees +10, and each extra independent verified reporter +15 (maximum +30).

Trust is reduced by:

- Phone not verified: -25
- GPS far from the claim: -30
- More than 800 people: -30
- Rescue claim from high ground with no flood hazard: -40
- No place found: -30
- Too many messages: -30

Below 50%, or with an unrecognised need type, the report goes to the officer review queue.

**How is priority calculated?**

```text
100 x (1 - e^(-raw/150))
```

Raw priority is:

```text
people (maximum 300)
x (1 + 0.35 per vulnerable group, maximum +1)
x type weight
x (1 + 0.3 per hour waiting, maximum 4 hours)
x (0.5 + 0.5 x trust)
```

Type weights are: rescue 2.0, medical 1.6, water 1.2, food 1.0, and shelter 0.8.

**How are routes planned?** The road map is a graph. Closed roads, meaning roads within a closure radius, are removed. Slow roads cost three times more. Shortest travel times come from Dijkstra. Google OR-Tools then solves a capacitated multi-depot routing problem: each truck has a capacity in kg, skipping a need costs a penalty that grows with priority, and arriving late is penalised more for urgent needs.

Load per need is people x kg per person: water 3, food 1, medical 0.5, shelter 2, and rescue 0.5. The load is capped at 450 kg.

**What is the comparison table?** The "nearest truck" baseline serves needs in the order they arrived, assigning each to the closest truck by straight-line distance. ResQGrid's plan is compared with that baseline using the same closed roads. With only one need, both plans are identical, so testing several needs is recommended.

**What is the agent?** A background loop notices new reports or closures and replans about a second later, then pushes the update to the screen. An officer must still approve dispatch.

**What if there is no internet or app access?** People can text the relief number. The phone network supplies the sender number, so no code is needed. Alternatively, they can send an emergency report, which is accepted but held for officer review.

**What stops fake reports?** Phone verification, GPS cross-checking, corroboration, plausibility checks, rate limits, and human review reduce the risk of harm, but they cannot stop coordinated fake reports.

**How is vehicle tracking done?** A driver signs in with a vehicle ID and PIN, then shares phone GPS every few seconds. The server keeps the latest point in memory for 90 seconds, and the officer map displays it. It does not currently change the plan.

**What is real vs simulated?** Road data, message reporting, routing, officer approval, and live driver GPS can be real or application-level features. Closures, vehicle movement without shared GPS, and the demo SMS network are simulated.

## Honest limitations

- Roads are two-way, and speeds are assumed by road type.
- There is no flood prediction.
- Replanning restarts vehicles from their depots.
- Demo accounts and demo OTPs are not secure for real use.
- Free hosting may sleep when idle.
