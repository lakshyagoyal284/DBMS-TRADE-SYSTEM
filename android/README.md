# Trading App (Android)

Native Android app for the TA-Lib Trading Dashboard. Talks to the FastAPI
backend (`api_server.py` on the PC, port 8000) over Tailscale.

## Features
- **Dashboard** – portfolio value, P&L (realized/unrealized), cash, positions, win rate + portfolio trend sparkline
- **Holdings** – open positions with live P&L per stock (searchable by symbol); tap a holding for entry date, RSI and the bot's exit plan
- **Trades** – full trade history with per-trade P&L (searchable + BUY/SELL filter); tap a trade for a full detail sheet
- **Signals** – recent strategy signals (BUY/SELL/EXIT) with RSI & band info
- **Performance** – portfolio value / returns chart over time with day P&L
- **Email alerts** – configure SMTP (toggle, server, port, app password, recipient) and send test emails from the app's Settings
- **Push alerts** – local notifications when a new signal or trade appears (instant while open, ~15 min background checks)
- **Start/Stop trading** and run a manual trading cycle from your phone
- Auto-refresh every 15s, dark theme, PIN-protected access to your PC's API

## Install the app
Copy `app/build/outputs/apk/debug/app-debug.apk` to your phone and open it.
Allow "Install unknown apps" for your file manager/browser.

On first launch, enter:
- **Server URL:** `http://<PC-Tailscale-IP>:8000` (e.g. `http://100.75.238.70:8000`)
- **PIN:** the 6-digit PIN from `dashboard_control_pin.txt` on the PC

Make sure the PC's `api_server.py` is running:
```
py -3.10 api_server.py
```

## Rebuild the APK (on the PC)
```
cd android
export JAVA_HOME="C:/Users/laksh/.jdks/jdk-17.0.20+8"
export ANDROID_HOME="$LOCALAPPDATA/Android/Sdk"
./gradlew.bat assembleDebug
```
Output: `app/build/outputs/apk/debug/app-debug.apk`

## Project structure
- `app/src/main/java/com/tradingapp/data/ApiClient.kt` – OkHttp API client (Bearer PIN auth)
- `app/src/main/java/com/tradingapp/data/Models.kt` – JSON models
- `app/src/main/java/com/tradingapp/ui/AppViewModel.kt` – state + data loading
- `app/src/main/java/com/tradingapp/ui/screens/` – Settings, Dashboard, Holdings, Trades, Signals
