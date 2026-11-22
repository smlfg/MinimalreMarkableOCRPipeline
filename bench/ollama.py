#!/usr/bin/env python3
"""Minimal keep-alive Ollama HTTP transport for VLM labeling/benchmarks."""

import base64, http.client, json
from pathlib import Path


class OllamaClient:
    """Persistent HTTP keep-alive client with one automatic reconnect."""

    def __init__(self, host: str = "localhost", port: int = 11434, timeout: int = 90):
        self.host, self.port, self.timeout = host, port, timeout
        self.conn = http.client.HTTPConnection(host, port, timeout=timeout)

    def __enter__(self) -> "OllamaClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def _reconnect(self) -> None:
        self.close()
        self.conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)

    def query(self, model: str, png_path: Path, prompt: str, num_predict: int = 80) -> str:
        body = json.dumps({
            "model": model, "prompt": prompt, "stream": False, "keep_alive": "5m",
            "options": {"temperature": 0, "num_predict": num_predict},
            "images": [base64.b64encode(png_path.read_bytes()).decode("ascii")],
        })
        headers = {"Content-Type": "application/json"}
        for attempt in range(2):
            try:
                self.conn.request("POST", "/api/generate", body=body, headers=headers)
                data = json.loads(self.conn.getresponse().read().decode("utf-8"))
                return (data.get("response") or "").strip()
            except Exception:
                self._reconnect()
                if attempt == 1:
                    return ""
        return ""

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
