# Unified Local Dashboard

A small Flask command center for the local workspace at `Desktop\programming projects (other)`.

It does not replace HALO, Doc Dashboard, n8n, Ollama, Qdrant, ComfyUI, Cockpit, or AI Video Studio. It gives them one front door:

- service health checks and quick links
- local folder inventory
- n8n template list
- audio backlog counts
- McMaster deliverables list
- Git status for the local repos

## Run

Double-click:

```bat
Run Unified Dashboard.bat
```

Then open:

```text
http://localhost:8910
```

## Manual Run

```powershell
cd "C:\Users\ram\Desktop\programming projects (other)\Experiments\unified-dashboard"
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python server.py
```

## Notes

The dashboard only opens existing local URLs. It does not start or stop the other apps because some existing launchers kill broad `python.exe` processes, which could accidentally stop this dashboard or another service.
