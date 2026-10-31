# Requirements Checklist

Source: `fs-assessment-spotter.pdf` — "Full Stack Developer — Weather-Aware Truck Routing".
Original wording is quoted verbatim. **Where** points to the implementation and the tests that verify it.

Legend: `[x]` done and verified · `[~]` needs the candidate's own account (GitHub / hosting / Loom) — everything for it is prepared

Paths: `B` = `backend/trips/`, `F` = `frontend/src/`, `BT` = `backend/trips/tests/`, `FT` = frontend `__tests__/`.

---

## A. Product goal & stack

| # | Requirement (quoted) | Where | Status |
|---|---|---|---|
| A1 | "Build a **React + Django** web app" | `backend/` Django 6.1 + DRF 3.18 · `frontend/` React 19 + Vite 8 | [x] |
| A2 | "that helps a truck driver choose the safest route based on **weather, load weight, and travel time**." | Weather: `B/services/weather.py` · load: `B/services/risk.py` load rules · time: `B/services/recommend.py` tiebreak | [x] |

## B. Inputs — "The user enters:"

| # | Requirement (quoted) | Where | Status |
|---|---|---|---|
| B1 | "Origin & destination" | `F/components/PlaceInput.tsx` (debounced suggestions), `B/views.py GeocodeView`, `B/serializers.py PlaceField` (text or picked place) · `BT/test_api.py` | [x] |
| B2 | "Departure date/time" | `F/components/TripForm.tsx` datetime-local, validated in `F/lib/validation.ts` + `B/serializers.py` · `FT/validation.test.ts`, `BT/test_api.py` | [x] |
| B3 | "Load weight" | Same form + validators (whole lb, 0–80,000) · `FT/TripForm.test.tsx`, `BT/test_api.py` | [x] |

## C. Behaviour — "The app should:"

| # | Requirement (quoted) | Where | Status |
|---|---|---|---|
| C1 | "Generate **3 route options** using a routing API." | `B/services/routing.py` OSRM alternatives + distinct via-point detours (strict, then relaxed pass) · `BT/test_routing.py`; live: Dallas–Houston, Chicago–Denver, LA–NYC, Seattle–Portland, Atlanta–Charlotte, Miami–Tampa, Denver–SLC all returned 3 | [x] |
| C2 | "Sample weather every **10 / 25 / 50 miles**," | Interval selector `F/components/TripForm.tsx`; `B/services/checkpoints.py` (mile 0, every N, destination) · `BT/test_checkpoints.py` | [x] |
| C3 | "using the truck's **estimated arrival time** at each checkpoint." | ETA from OSRM per-segment durations (`Route.position_at`); forecast hour chosen by ETA in `Forecast.conditions` · `BT/test_checkpoints.py`, `BT/test_weather.py::TestTimeSemantics` | [x] |
| C4 | "Calculate weather risk using the provided risk/load rules." | `B/services/risk.py` · `BT/test_risk.py` (every edge) | [x] |
| C5 | "Recommend the best route, balancing **weather risk and travel time**." | `B/services/recommend.py` lexicographic order + explanation · `BT/test_recommend.py`; UI banner `F/components/Results.tsx` | [x] |
| C6 | "Show all routes, checkpoints, risk levels, ETAs, and route summaries on a map." — each of: all routes · checkpoints · risk levels · ETAs · route summaries | `F/components/map/MapView.tsx` + `layers.ts`: 3 route lines (click to select, summary popup), risk-coloured checkpoint layer (click → ETA, wind/rain/snow, level, cause), route summary labels (time · distance), legend; panel route cards + checkpoint timeline (`CheckpointList.tsx`) | [x] |
| C7 | "Show a **weather heatmap along the trip corridor** with a **0–48 hour forecast slider**." | `B/services/heatmap.py` (corridor grid, 49 hourly slots from departure) · `F/components/map/HeatmapLayer.tsx`, `heatmapGLLayer.ts`, `ForecastSlider.tsx` · `BT/test_heatmap.py`, `FT/heatmapFrames.test.ts` | [x] |
| C8 | "You may use third-party APIs for routing, geocoding, and weather. You do not need to build a routing engine." | OSRM (routing), Photon (geocoding), Open-Meteo (weather), OpenFreeMap (tiles) — all keyless | [x] |

## D. Risk rules — "Use these thresholds to classify weather at each checkpoint:"

| # | Condition | Low | Moderate | High | Severe | No Travel | Where | Status |
|---|---|---|---|---|---|---|---|---|
| D1 | Wind | "<25 mph" | "25–34" | "35–44" | "45–54" | "≥55 mph" | `risk.py WIND_EDGES_MPH` · `test_risk.py::test_wind_bands_light_load` | [x] |
| D2 | Rain | "<0.10 in/hr" | "0.10–0.25" | "0.25–0.50" | "0.50–1.00" | ">1.00" | `risk.py RAIN_EDGES_IN_HR` · `test_risk.py::test_rain_bands` | [x] |
| D3 | Snow | "<0.5 in/hr" | "0.5–1.0" | "1.0–2.0" | "2.0–3.0" | ">3.0" | `risk.py SNOW_EDGES_IN_HR` · `test_risk.py::test_snow_bands` | [x] |

## E. Load rules — "Load rules:"

| # | Requirement (quoted) | Where | Status |
|---|---|---|---|
| E1 | "≥55 mph → **No Travel** for any load" | `risk.wind_level` · `test_risk.py::TestLoadRules` | [x] |
| E2 | "45–54 mph + >30,000 lb → **No Travel**" | `risk.wind_level` (30,000 vs 30,001 tested) | [x] |
| E3 | "35–44 mph + >40,000 lb → **Severe**" | `risk.wind_level` (40,000 vs 40,001 tested); end-to-end in `test_api.py::test_load_rule_drives_the_recommendation` | [x] |

## F. Route recommendation — "Prefer:"

| # | Requirement (quoted) | Where | Status |
|---|---|---|---|
| F1 | "1. Fewest Severe miles" | `recommend.CRITERIA` (preceded by No Travel miles, J3) · `test_recommend.py` | [x] |
| F2 | "2. Fewest High miles" | same | [x] |
| F3 | "3. Lowest average risk" | mile-weighted 0–4 · same | [x] |
| F4 | "4. Shortest travel times" | same | [x] |

## G. Deliverables — "Deliverables"

| # | Requirement (quoted) | Where | Status |
|---|---|---|---|
| G1 | "GitHub repository" | Local git repository ready to push (`.gitignore`, migrations included) | [~] push to the candidate's GitHub |
| G2 | "Hosted application" | `Dockerfile` (single image) + `render.yaml` blueprint; production mode verified locally (WhiteNoise SPA + gzip + API) | [~] deploy with the candidate's Render account |
| G3 | "**5–10 min Loom walkthrough**" | Talking points: README sections "How it works", "Decisions", "Performance" | [~] record |

## H. Evaluation — drives priorities, not features

| # | Requirement (quoted) | How it is addressed | Status |
|---|---|---|---|
| H1 | "40% Routes, Weather, risk & recommendation logic" | Pure, documented service functions; ETA-correct hour selection; 120 backend tests incl. every threshold/load edge | [x] |
| H2 | "40% UI, map & heatmap smoothness and performance" | Lazy MapLibre chunk; GPU layers; custom WebGL heatmap (slider step = one 60 fps frame, measured); cached plans; gzip | [x] |
| H3 | "15% Code quality" | Typed frontend, layered backend (views → services), consistent error model, no dead code | [x] |
| H4 | "5% Documentation & walkthrough" | README + this checklist; walkthrough to record (G3) | [x] / [~] |
| H5 | "**Prioritize correctness and clarity over extra features.**" | No features beyond the brief (no accounts, history, exports) | [x] |

---

## I. Engineering rules from the build brief (not in the PDF)

| # | Requirement | Where | Status |
|---|---|---|---|
| I1 | Django + DRF, latest | Django 6.1.2, DRF 3.18.3 (`backend/requirements.txt`) | [x] |
| I2 | React + Vite | React 19.3, Vite 8.3 | [x] |
| I3 | Serializers, viewsets, proper status codes and validation errors | `B/serializers.py`, `B/views.py TripPlanViewSet`; 201/400/404/405/422/502/503 in `B/exceptions.py` · `test_api.py` | [x] |
| I4 | No N+1 queries | One row per plan, JSON results; no related lookups exist | [x] |
| I5 | Paginate every list endpoint | No list endpoints (405 on `GET /api/trip-plans/`); `PageNumberPagination` configured globally | [x] |
| I6 | Indexes on filter/order/lookup fields | UUID primary key (lookups), `created_at` indexed (default ordering) | [x] |
| I7 | `.only()` / `.values()` where full objects aren't needed | `views.get_queryset`: `.only(...)` for heatmap, `.defer("heatmap")` otherwise | [x] |
| I8 | Lean serializers, no per-row queries | `TripPlanSerializer` reads stored JSON only | [x] |
| I9 | Caching for expensive reads | Geocode 24 h, routes 1 h, weather per cell 1 h, heatmap persisted on the plan, HTTP `Cache-Control`, TanStack Query | [x] |
| I10 | Query counts verified | `django_assert_num_queries` in `test_api.py` (create 1, retrieve 1, heatmap 2 then 1) | [x] |
| I11 | CORS configured | `django-cors-headers`, `CORS_ALLOWED_ORIGINS` env | [x] |
| I12 | Settings via environment variables | `config/settings.py`, `.env.example` | [x] |
| I13 | Migrations committed | `B/migrations/0001_initial.py` | [x] |
| I14 | Seed script / fixtures — "if needed, not necessary" | Not needed: all data is live (forecasts, routes); `scripts/smoke_live.py` exercises real providers | [x] |
| I15 | Functional components + hooks | All components are functions; hooks in `F/api/queries.ts`, `F/hooks/` | [x] |
| I16 | TanStack Query; no duplicate requests | Plans keyed by inputs (identical resubmit = 0 requests, verified in browser), heatmap per plan, geocode per query | [x] |
| I17 | Debounce search inputs | `useDebouncedValue` 300 ms in `useGeocode` | [x] |
| I18 | Lazy-load routes / heavy chunks | Single page; the 1 MB MapLibre map is `React.lazy` (`F/App.tsx`) | [x] |
| I19 | Avoid needless re-renders | Slider state isolated in `HeatmapLayer`; `memo` on `RouteCard`/`CheckpointList`/hour bars; map driven imperatively | [x] |
| I20 | Loading, empty and error states | `StatusMessage` (results), map overlays (loading / base map error / hint), slider loading/error + retry, suggestion states | [x] |
| I21 | Clean, responsive UI | Map + side panel ≥ 900 px; map on top with the panel below on phones (screenshot-verified at 390 px) | [x] |
| I22 | Form validation matches backend | `F/lib/validation.ts` mirrors `B/serializers.py`; server field errors shown on inputs | [x] |
| I23 | README with setup, decisions, ambiguity resolutions | `README.md` | [x] |
| I24 | Tests; runs first try; API fast | 120 backend + 26 frontend tests, typecheck, build; browser E2E (Playwright) on dev and production builds; timings in README | [x] |
| I25 | No extra features; nothing left out | Sections A–H | [x] |

---

## J. Ambiguities & gaps — resolutions (J1–J4 confirmed by the candidate; the rest use the most literal reading; all recorded in README)

| # | Question | Resolution |
|---|---|---|
| J1 | "every 10 / 25 / 50 miles" — user-selectable interval, or chosen automatically? | **Confirmed:** user picks 10, 25 or 50 mi per trip (default 25). |
| J2 | Slider "0–48 hour forecast" — hour 0 = departure time or current time? | **Confirmed:** hour 0 = departure time, so the heatmap lines up with the trip. |
| J3 | Recommendation priorities never mention **No Travel** miles. | **Confirmed:** No Travel is strictly worse than Severe: compare No Travel miles first, then rules 1–4 exactly. Routes with any No Travel segment are flagged. |
| J4 | "Wind" — sustained wind speed or gusts? | **Confirmed:** sustained 10 m wind speed (literal). |
| J5 | Band edges overlap ("0.10–0.25", "0.25–0.50"). | Lower bound inclusive: Moderate = [0.10, 0.25), High = [0.25, 0.50), Severe = [0.50, 1.00], No Travel > 1.00. Same for snow; wind in integer mph bands → [25,35), [35,45), [45,55), ≥55. |
| J6 | "Rain" — which precipitation? | Liquid rain + convective showers, in/hr (preceding-hour accumulation). Snow = snowfall in/hr. |
| J7 | How checkpoint risk becomes "miles". | Each checkpoint represents the route miles nearest to it (half the gap to the previous and next checkpoint). |
| J8 | "Lowest average risk" scale. | Low=0, Moderate=1, High=2, Severe=3, No Travel=4, mile-weighted mean. |
| J9 | Checkpoint risk when several conditions apply. | The worst level among wind (after load rules), rain and snow. |
| J10 | Load weight range/units. | Pounds, 0–80,000 lb (US federal gross weight cap). |
| J11 | Departure date/time zone and allowed window. | Browser local time; from 1 h ago up to 7 days ahead (forecast horizon is 16 days and must cover the trip + 48 h heatmap). |
| J12 | Routing provider (no truck profile is required by the doc). | OSRM (keyless, no distance limit). If it returns fewer than 3 routes, extra distinct routes are generated through offset via-points. |
| J13 | What the heatmap shows. | A continuous risk index (0–4) computed from the same thresholds and load rules, so its colours match the checkpoint risk colours. |
| J14 | Hosting / GitHub / Loom need the candidate's accounts. | Repo + Dockerfile + Render blueprint are prepared; pushing, deploying and recording are left to the candidate. |
