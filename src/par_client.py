"""Thin stdlib-only client for the parallel.ai API platform.

No third-party SDK: uses urllib only. The API key is read from the
PARALLEL_API_KEY environment variable and is never printed or logged.
"""
import json
import os
import time
import urllib.error
import urllib.request

API_BASE = "https://api.parallel.ai"
API_KEY_ENV = "PARALLEL_API_KEY"
PLACEHOLDER_KEY = "REPLACE_ME"
DEFAULT_TIMEOUT = 60


class ParallelAPIError(Exception):
    """Raised for transport errors and non-2xx API responses."""

    def __init__(self, message, status=None, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


def _resolve_api_key(api_key=None):
    key = api_key or os.environ.get(API_KEY_ENV, "")
    if not key or key == PLACEHOLDER_KEY:
        raise ParallelAPIError(
            f"Missing Parallel API key. Set the {API_KEY_ENV} environment variable "
            "(copy .env.example to .env and replace REPLACE_ME). "
            "Get a key at https://platform.parallel.ai"
        )
    return key


class ParallelClient:
    def __init__(self, api_key=None, base_url=API_BASE, timeout=DEFAULT_TIMEOUT):
        self._api_key = _resolve_api_key(api_key)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self):
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "parallel-fda-scaffold/0.1",
        }

    def _request(self, method, path, body=None, timeout=None):
        url = self.base_url + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except Exception:
                payload = None
            # Never include the key in error output (payload is the response body).
            detail = (payload or {}).get("message") or (payload or {}).get("detail")
            if detail is None and payload is not None:
                detail = json.dumps(payload)[:500]
            raise ParallelAPIError(
                f"{method} {path} -> HTTP {exc.code}: {detail or 'request failed'}",
                status=exc.code,
                payload=payload,
            )
        except urllib.error.URLError as exc:
            raise ParallelAPIError(f"{method} {path} -> connection error: {exc.reason}")

    def _post(self, path, body, timeout=None):
        return self._request("POST", path, body, timeout)

    def _get(self, path, timeout=None):
        return self._request("GET", path, None, timeout)

    def _delete(self, path, timeout=None):
        return self._request("DELETE", path, None, timeout)

    # ---- Search ----
    def search(self, objective, search_queries, max_results=10):
        """Web search with LLM-optimized excerpts. search_queries: 2-3 keyword queries."""
        return self._post(
            "/v1/search",
            {
                "objective": objective,
                "search_queries": search_queries,
                "max_results": max_results,
            },
        )

    # ---- Extract ----
    def extract(self, url, objective):
        """Clean markdown extraction from a URL (handles JS pages and PDFs).

        Request: {"urls": [...], "objective": ...} -> response.results[0]
        carries excerpts[] / full_content. Verified docs.parallel.ai.
        """
        return self._post(
            "/v1/extract", {"urls": [url], "objective": objective}
        )

    # ---- Task (deep research) ----
    def task_run(self, objective, output_schema=None, webhook_url=None):
        """Start an async deep-research run. Returns a run handle with a run id."""
        body = {"objective": objective}
        if output_schema is not None:
            body["output_schema"] = output_schema  # TODO: verify field name
        if webhook_url:
            body["webhook_url"] = webhook_url  # TODO: verify field name
        return self._post("/v1/tasks/runs", body, timeout=self.timeout)

    def task_result(self, run_id):
        """Fetch the current state/result of a task run."""
        # TODO: verify against docs.parallel.ai (endpoint path + status/output fields)
        return self._get(f"/v1/tasks/runs/{run_id}")

    def wait_for_task(self, run_id, timeout=600, interval=10):
        """Poll a task run until it completes; returns the parsed output payload."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            res = self.task_result(run_id)
            status = str(res.get("status", "")).lower()
            if status in ("completed", "succeeded", "success", "done"):
                # TODO: verify the output field name against docs.parallel.ai
                return res.get("output", res.get("result", res))
            if status in ("failed", "error", "cancelled"):
                raise ParallelAPIError(f"Task {run_id} ended with status '{status}'")
            time.sleep(interval)
        raise ParallelAPIError(f"Task {run_id} timed out after {timeout}s")

    # ---- Chat ----
    def chat(self, messages, system=None, model="parallel-chat"):
        """OpenAI-compatible chat completions with web grounding."""
        # TODO: verify model name and grounding parameters against docs.parallel.ai
        msgs = ([{"role": "system", "content": system}] if system else []) + list(messages)
        return self._post("/v1/chat/completions", {"model": model, "messages": msgs})

    # ---- FindAll ----
    def findall(self, objective, criteria=None):
        """Entity discovery at web scale from natural-language criteria."""
        body = {"objective": objective}
        if criteria:
            body["criteria"] = criteria  # TODO: verify field name
        return self._post("/v1beta/findall/runs", body)

    # ---- Monitors ----
    def create_monitor(self, name, objective, url, frequency, webhook_url):
        """Register a scheduled change monitor with webhook notifications."""
        # TODO: verify against docs.parallel.ai (field names, frequency values)
        return self._post(
            "/v1alpha/monitors",
            {
                "name": name,
                "objective": objective,
                "url": url,
                "frequency": frequency,
                "webhook_url": webhook_url,
            },
        )

    def list_monitors(self):
        # TODO: verify against docs.parallel.ai
        return self._get("/v1alpha/monitors")

    def delete_monitor(self, monitor_id):
        # TODO: verify against docs.parallel.ai
        return self._delete(f"/v1alpha/monitors/{monitor_id}")

    # ---- Task groups ----
    def task_group(self, tasks):
        """Submit a batch of research tasks (up to 1000 per call)."""
        # TODO: verify against docs.parallel.ai (request/response shape, SSE streaming)
        return self._post("/v1beta/tasks/groups", {"tasks": tasks})
