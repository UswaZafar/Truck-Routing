# Run Weather-Aware Truck Routing on another computer

Step-by-step setup from the zip file. It takes about 5 minutes, most of it downloads.

## 1. Install the tools (once per computer)

| Tool | Version | Where |
|---|---|---|
| Python | 3.12 or newer (built with 3.13) | https://www.python.org/downloads/ — on Windows, tick **"Add python.exe to PATH"** in the installer |
| Node.js | 20.19 or newer (built with 24 LTS) | https://nodejs.org/ |
| Git | optional | https://git-scm.com/ |

You also need an internet connection: routes (OSRM), place search (Photon), weather (Open-Meteo) and map tiles
(OpenFreeMap) come from free public services. **No API keys or accounts are needed.**

Check the installs in a new terminal:

```powershell
python --version    # Python 3.12+   (if this opens the Microsoft Store, see Troubleshooting)
node --version      # v20.19+ or v22+/v24+
```

## 2. Unzip

Unzip `weather-truck-routing.zip` into a folder with a **short path**, for example `C:\Projects\`. On Windows,
deep folders (like a long path inside Downloads) can break the Python install with "The filename or extension is
too long". You get one folder:

```
weather-truck-routing/
  backend/     Django + DRF API (routing, weather, risk rules, heatmap)
  frontend/    React + Vite app (form, map, heatmap slider)
  docs/        screenshot
  README.md    how it works, API, design decisions
  CHECKLIST.md requirements from the brief and where each is implemented
  SETUP.md     this file
```

Not in the zip, because the steps below recreate them: the Python environment (`backend/.venv`), the Node
packages (`frontend/node_modules`), the SQLite database and build output. Your `.env` file is not included
either: the app does not read it, and every setting has a working default.

## 3. Start the backend (terminal 1)

**Windows (PowerShell):**

```powershell
cd weather-truck-routing\backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

Calling `.venv\Scripts\python.exe` directly means you never need to "activate" the environment, which
PowerShell often blocks.

**macOS / Linux:**

```bash
cd weather-truck-routing/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver
```

Leave it running. The API is at http://127.0.0.1:8000/api/. `migrate` creates the SQLite database file
(`backend/db.sqlite3`); it has no username or password.

## 4. Start the frontend (terminal 2)

```powershell
cd weather-truck-routing\frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. The dev server forwards every `/api/...` request to the backend on port 8000,
so both must be running.

## 5. Check that it works

1. Origin: type `Denver` and pick the suggestion. Destination: `Salt Lake City`.
2. Load weight: `41000`, then **Plan routes**.
3. Within a few seconds you should see three routes on the map, "Take Route …" with the reason, three route
   cards, the checkpoint timeline, and the forecast card at the bottom of the map. Drag the slider or press
   Play to move the heatmap through the next 48 hours.

## Every time after that

Only two commands, each in its own terminal:

```powershell
cd weather-truck-routing\backend;  .venv\Scripts\python.exe manage.py runserver
cd weather-truck-routing\frontend; npm run dev
```

## Run the tests (optional)

```powershell
cd backend;  .venv\Scripts\python.exe -m pytest     # 120 tests, no internet needed (providers are faked)
cd frontend; npm test; npm run typecheck; npm run build   # 32 tests, type check, production build
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` opens the Microsoft Store or "not found" | Use `py` instead of `python` in step 3 (`py -m venv .venv`), or turn off the `python.exe` entries in Settings → Apps → Advanced app settings → App execution aliases. Then open a new terminal. |
| `python -m venv` or `pip install` fails with "[WinError 206] The filename or extension is too long" | The folder path is too long for Windows. Move the project to a short path such as `C:\Projects\weather-truck-routing`, delete `backend\.venv`, and repeat step 3. |
| `npm ci` fails with an engine or syntax error | Node is too old. Install the current LTS from nodejs.org and open a new terminal. |
| "That port is already in use" for 8000 | Another backend is still running; close that terminal. The frontend expects the backend on port 8000. (If 5173 is taken, Vite picks the next port by itself and prints it.) |
| "Cannot reach the server" in the app | The backend terminal is not running or crashed; start step 3 again. |
| "Weather service rate limit reached" | Open-Meteo's free limits are per internet connection: 600 locations per minute, 5,000 per hour, 10,000 per day. Wait a minute (or an hour) and retry. |
| Map stays blank | Map tiles come from tiles.openfreemap.org; check the internet connection or a firewall/VPN. |

## Settings (optional)

All settings are environment variables with working defaults; `.env.example` lists them. You only need them
for deployment, for example `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, or
`OPEN_METEO_API_KEY` for a paid weather plan. Deployment steps are in README.md under "Deploy".

## Git

The zip contains the `.git` folder, so the project history comes along. Recent work (the bright redesign and
the heatmap request fix) is not committed yet: `git status` lists it. Commit it before pushing to GitHub.
