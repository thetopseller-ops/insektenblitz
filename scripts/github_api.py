"""GitHub-API Hilfsfunktionen fuer die Content-Maschine.

Stellt drei Funktionen bereit:
  - get_file_sha   : SHA einer bestehenden Datei auf main holen (oder None)
  - push_file      : Single-File-Push via Contents-API (Draft-Vorschau)
  - commit_files   : Atomarer Multi-Datei-Commit via Git Data API (Approve-Move)

Alle Funktionen laden GH_PAT + GH_REPO aus der Umgebung / lokalen .env.
HTTP-Fehler fuehren zu sys.exit (kritisch — kein stiller Teilzustand).
Keine Secrets werden geloggt oder gedruckt.
"""
import base64
import os
import sys
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_secret(key_name: str) -> str:
    """Laedt einen Secret-Wert: erst os.environ, dann .env-Datei, sonst sys.exit.

    Im GitHub-Actions-Kontext (D-06) werden GH_PAT/GH_REPO auf die eingebauten
    GITHUB_TOKEN/GITHUB_REPOSITORY gemappt — so pusht der Code ohne langlebiges
    PAT. Faellt der Actions-Wert leer aus, greift der normale Pfad unten.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        if key_name == "GH_PAT" and os.environ.get("GITHUB_TOKEN"):
            return os.environ.get("GITHUB_TOKEN")
        if key_name == "GH_REPO" and os.environ.get("GITHUB_REPOSITORY"):
            return os.environ.get("GITHUB_REPOSITORY")
    val = os.environ.get(key_name)
    if val:
        return val
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == key_name:
                return value.strip().strip('"').strip("'")
    sys.exit(f"{key_name} fehlt — bitte in .env setzen (siehe .env.example).")


def _get_headers(pat: str) -> dict:
    """Gemeinsame GitHub-API-Header."""
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=8),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=True,
)
def _http_get(url: str, headers: dict, params: dict | None = None, timeout: int = 20) -> requests.Response:
    """GET-Request mit Retry/Backoff bei Timeout/ConnectionError (3 Versuche, 2-8s).

    reraise=True: nach Erschoepfung der Versuche wirft die originale Exception.
    HTTPError (4xx/5xx) wird NICHT retried — das sind keine transienten Fehler.
    """
    resp = requests.get(url, headers=headers, params=params, timeout=timeout)
    return resp


def get_file_sha(path: str) -> "str | None":
    """SHA einer bestehenden Datei auf main zurueckgeben, oder None bei 404.

    Args:
        path: Pfad zur Datei relativ zum Repo-Root (z.B. "draft-2026-06-18.html").

    Returns:
        SHA-String oder None wenn Datei nicht existiert.
    """
    pat = _load_secret("GH_PAT")
    repo = _load_secret("GH_REPO")
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    try:
        resp = _http_get(url, headers=_get_headers(pat), params={"ref": "main"}, timeout=20)
        resp.raise_for_status()
        return resp.json()["sha"]
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        sys.exit(f"GitHub API Fehler: {e.response.status_code} — {e.response.text[:200]}")


def push_file(path: str, content_bytes: bytes, message: str) -> dict:
    """Erstellt oder aktualisiert EINE Datei auf main via Contents-API.

    Verwendet fuer den Draft-Vorschau-Push (Single-File). Bei Update wird der
    aktuelle SHA automatisch geholt, damit GitHub kein Conflict zurueckgibt.

    Args:
        path:          Pfad relativ zum Repo-Root (z.B. "draft-2026-06-18.html").
        content_bytes: Dateiinhalt als bytes.
        message:       Commit-Nachricht.

    Returns:
        API-Antwort als dict.

    Raises:
        SystemExit bei HTTP-Fehler (kritisch — kein stiller Fehlschlag).
    """
    pat = _load_secret("GH_PAT")
    repo = _load_secret("GH_REPO")
    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    payload: dict = {
        "message": message,
        "content": base64.b64encode(content_bytes).decode(),
        "branch": "main",
    }

    existing_sha = get_file_sha(path)
    if existing_sha is not None:
        payload["sha"] = existing_sha

    try:
        resp = requests.put(url, headers=_get_headers(pat), json=payload, timeout=30)
        resp.raise_for_status()
    except requests.HTTPError as e:
        sys.exit(f"GitHub API Fehler: {e.response.status_code} — {e.response.text[:200]}")

    return resp.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=8),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=True,
)
def _http_request(method: str, url: str, headers: dict, timeout: int = 30, **kwargs) -> requests.Response:
    """requests.request mit Retry/Backoff fuer commit_files-_call (Timeout/ConnectionError).

    reraise=True: sys.exit-Verhalten bei echten Fehlern (nach reraise) bleibt unveraendert.
    HTTPError (4xx/5xx) wird NICHT retried (kein transienter Fehler).
    """
    resp = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
    return resp


def commit_files(changes: list, message: str) -> None:
    """Schreibt mehrere Datei-Aenderungen in EINEM Commit auf main via Git Data API.

    Jeder Eintrag in changes ist ein dict mit:
      - "path"    : str  — Pfad relativ zum Repo-Root
      - "content" : bytes | str  — Dateiinhalt (add/update); FEHLT bei delete
      - "delete"  : bool (optional) — True wenn die Datei entfernt werden soll

    Die Git-Data-Sequenz:
      1. GET .../git/ref/heads/main         -> aktuellen Commit-SHA
      2. GET .../git/commits/{sha}          -> base-tree-SHA
      3. POST .../git/trees                 -> neuer Tree-SHA
      4. POST .../git/commits               -> neuer Commit-SHA
      5. PATCH .../git/refs/heads/main      -> Ref auf neuen Commit setzen

    Der Ref wird erst im letzten Schritt gesetzt -> kein Teilzustand auf main
    wenn ein frueherer Schritt fehlschlaegt.

    Args:
        changes: Liste von Aenderungs-Dicts (s.o.).
        message: Commit-Nachricht.

    Raises:
        SystemExit bei HTTP-Fehler in einem der Schritte.
    """
    pat = _load_secret("GH_PAT")
    repo = _load_secret("GH_REPO")
    base = f"https://api.github.com/repos/{repo}"
    headers = _get_headers(pat)

    def _call(method: str, url: str, **kwargs) -> dict:
        try:
            resp = _http_request(method, url, headers=headers, timeout=30, **kwargs)
            resp.raise_for_status()
        except requests.HTTPError as e:
            sys.exit(f"GitHub API Fehler: {e.response.status_code} — {e.response.text[:200]}")
        return resp.json()

    # Schritt 1: aktuellen Commit-SHA von main holen
    ref_data = _call("GET", f"{base}/git/ref/heads/main")
    current_commit_sha = ref_data["object"]["sha"]

    # Schritt 2: base-tree-SHA aus dem aktuellen Commit holen
    commit_data = _call("GET", f"{base}/git/commits/{current_commit_sha}")
    base_tree_sha = commit_data["tree"]["sha"]

    # Schritt 3: neuen Tree bauen
    tree_entries = []
    for change in changes:
        path = change["path"]
        if change.get("delete"):
            # Datei entfernen: sha=null im Tree
            tree_entries.append({
                "path": path,
                "mode": "100644",
                "type": "blob",
                "sha": None,
            })
        else:
            content = change["content"]
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            tree_entries.append({
                "path": path,
                "mode": "100644",
                "type": "blob",
                "content": content,
            })

    new_tree = _call("POST", f"{base}/git/trees", json={
        "base_tree": base_tree_sha,
        "tree": tree_entries,
    })
    new_tree_sha = new_tree["sha"]

    # Schritt 4: neuen Commit erstellen
    new_commit = _call("POST", f"{base}/git/commits", json={
        "message": message,
        "tree": new_tree_sha,
        "parents": [current_commit_sha],
    })
    new_commit_sha = new_commit["sha"]

    # Schritt 5: Ref auf neuen Commit setzen (erst jetzt ist der Commit sichtbar)
    _call("PATCH", f"{base}/git/refs/heads/main", json={"sha": new_commit_sha})


def delete_file(path: str, message: str) -> "dict | None":
    """Loescht EINE Datei auf main via Contents-API.

    Idempotent: wenn die Datei nicht existiert (SHA == None), wird nichts getan.
    Verwendet fuer den Reject-Pfad (D-06) — bewusst einfacher Single-File-Call,
    kein atomarer Multi-Datei-Bedarf.

    Args:
        path:    Pfad relativ zum Repo-Root (z.B. "draft-2026-06-18.html").
        message: Commit-Nachricht.

    Returns:
        API-Antwort als dict, oder None wenn Datei nicht existiert.

    Raises:
        SystemExit bei HTTP-Fehler (kritisch — kein stiller Fehlschlag).
    """
    pat = _load_secret("GH_PAT")
    repo = _load_secret("GH_REPO")

    sha = get_file_sha(path)
    if sha is None:
        print(f"  delete_file: '{path}' nicht gefunden — nichts zu loeschen.")
        return None

    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    payload = {
        "message": message,
        "sha": sha,
        "branch": "main",
    }

    try:
        resp = requests.delete(url, headers=_get_headers(pat), json=payload, timeout=30)
        resp.raise_for_status()
    except requests.HTTPError as e:
        sys.exit(f"GitHub API Fehler: {e.response.status_code} — {e.response.text[:200]}")

    return resp.json()


def get_text_file(path: str) -> str:
    """Liest den Inhalt einer Datei von main und gibt ihn als UTF-8-String zurueck.

    Verwendet fuer den Approve-Move: Draft-Inhalt lesen, bevor er via
    commit_files als blog-[slug].html geschrieben wird (D-05).

    Args:
        path: Pfad relativ zum Repo-Root (z.B. "draft-2026-06-18.html").

    Returns:
        Dateiinhalt als str (UTF-8).

    Raises:
        SystemExit wenn Datei nicht existiert (Approve auf nicht vorhandenen
        Draft ist ein Fehler, kein toleranter Fall).
    """
    pat = _load_secret("GH_PAT")
    repo = _load_secret("GH_REPO")
    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    try:
        resp = _http_get(url, headers=_get_headers(pat), params={"ref": "main"}, timeout=20)
        resp.raise_for_status()
    except requests.HTTPError as e:
        sys.exit(f"GitHub API Fehler: {e.response.status_code} — {e.response.text[:200]}")

    content_b64 = resp.json()["content"]
    return base64.b64decode(content_b64).decode("utf-8")
