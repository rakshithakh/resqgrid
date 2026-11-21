# ResQGrid

A flood relief coordination portal built for the IDEA//FORGE hackathon (Track 2, emergency response and logistics).

People affected by a flood send a request in English, Hindi or Kannada, either through a web form or by SMS.
The backend works out what they need, where they are and how far to trust the report, then plans relief truck
routes on real OpenStreetMap roads. When a road is closed or a new report arrives, the plan is recalculated
automatically. An officer approves each dispatch before trucks are released.

## How it works

1. **Reading the message.** `extract.py` pulls out the need type (water, food, medical, rescue, shelter),
   head-count, vulnerable groups and urgency. It uses Gemini when `GEMINI_API_KEY` is set and falls back to a
   keyword-based extractor otherwise. The model is never asked for coordinates or routes.
2. **Finding the place.** A ward or landmark named in the text is matched against OpenStreetMap place names.
   Phone GPS is snapped to the nearest road node.
3. **Trust score.** Each need starts at 55% and goes up or down depending on phone verification, whether GPS
   agrees with the stated place, independent reports of the same need, and plausibility checks (for example a
   head-count of 5,000). Needs below 50% wait in a review queue for an officer.
4. **Priority.** People affected, vulnerable groups, need type, waiting time and trust give a score from 0 to 100.
5. **Routing.** Closed roads are removed from the graph, travel times come from Dijkstra, and OR-Tools solves a
   capacitated multi-depot routing problem. The result is compared with a "nearest truck, first come" baseline.
6. **Agent loop.** A background task notices new reports or closures and replans a moment later.

Optimisation and trust scoring are ordinary algorithms on purpose; the language model only reads the messages.

## Demo accounts

| Role | Sign in |
|---|---|
| Citizen | Any 10-digit number. In demo mode the one-time code is shown on screen |
| Officer | `controlroom` / `Relief@2026` |
| Driver | Any vehicle, PIN `1234` |

## Running it locally

Backend (Python 3.10+):

    cd backend
    pip install -r requirements.txt
    uvicorn app.main:app --port 8000

Frontend (Node 18+), in another terminal:

    cd frontend
    npm install
    npm run dev

Then open http://localhost:5173. The app starts empty; use **Load sample data** in the control room to fill it.

### Real map

Without a map download the app runs on a small synthetic grid. To use real roads around Hubballi:

    cd backend
    python -m app.fetch_osm            # needs internet, takes a minute or two
    python -m app.fetch_osm --compress # writes the .gz copy that can be committed

Use `--lat`, `--lng` and `--km` for another place. If the Overpass servers are busy, `--print-query` prints the
query so you can run it on overpass-turbo.eu and load the exported file with `--file raw.json`.

### Settings

Everything is optional; see `backend/.env.example`. Copy it to `backend/.env` to change `SMS_PROVIDER`
(`demo`, `fast2sms` or `android`), `GEMINI_API_KEY`, `MAP_MODE` and others.

### Tests

    cd backend
    pip install pytest
    pytest

## Deployment

The backend runs on Render (`render.yaml`) and the frontend on Vercel (`frontend/vercel.json`). On Vercel set
`VITE_API_URL` to the Render address. Render's free plan wipes the SQLite file when the service sleeps, so set
`AUTOSEED=1` if you want sample data after each restart. A `Dockerfile` is also included for running website and
API together as one service.

## Layout

    backend/app/core.py      road graph, place matching, routing, dispatch solver
    backend/app/extract.py   Gemini or keyword extraction of needs from a message
    backend/app/store.py     SQLite access, report ingestion, trust and priority, planning
    backend/app/osm.py       builds the road graph from downloaded OpenStreetMap data
    backend/app/smsout.py    optional outgoing SMS for one-time codes
    backend/app/main.py      REST API, WebSocket updates, agent loop
    backend/tests/           pytest suite
    frontend/src/            React pages and components, Leaflet map

## What is simulated

Flood closures are placed by hand, trucks move along their planned route unless a driver shares real GPS,
and the SMS network is an on-page phone simulator. Live GPS from drivers is shown on the map but does not
change the plan.

## Known limitations

- Roads are treated as two-way and speeds come from road type, not traffic.
- Replanning sends trucks from their depots again instead of from where they currently are.
- The demo accounts and demo one-time codes are not secure and are not meant for real use.
- There is no flood prediction.

## Credits

Map data from OpenStreetMap contributors (ODbL), fetched with the Overpass API. Elevation from Open-Meteo.
Built with FastAPI, Pydantic, NetworkX, Google OR-Tools, React, Vite, Leaflet and React Router. Optional message
understanding with the Gemini API. An AI coding assistant (Claude, by Anthropic) was used while building this
project; I reviewed and tested the code myself.
