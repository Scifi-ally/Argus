@echo off
REM Serves outputs\ on 127.0.0.1 only and opens the black viewer.
start "" http://127.0.0.1:8712/viewer.html
python -m http.server 8712 --bind 127.0.0.1 --directory "%~dp0outputs"
