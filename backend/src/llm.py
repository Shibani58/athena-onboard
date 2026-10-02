"""LLM + embeddings via the Google Gemini API (free tier), with an offline fallback.

The original project used Amazon Bedrock (Titan Text + Titan Embeddings). This rebuild
swaps in a free provider behind the same two functions, so it can be changed in one place.
"""
import json
import math
import os
import re
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models"
TEXT_MODEL = os.environ.get("LLM_MODEL", "gemini-2.5-flash")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "gemini-embedding-001")


def _key():
    return os.environ.get("GEMINI_API_KEY", "").strip()


def available():
    return bool(_key())


def _post(url, payload, timeout=20):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "x-goog-api-key": _key()},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def embed(texts):
    """Return one embedding vector per text."""
    if available():
        body = {"requests": [{"model": f"models/{EMBED_MODEL}", "content": {"parts": [{"text": t}]}} for t in texts]}
        out = _post(f"{API}/{EMBED_MODEL}:batchEmbedContents", body)
        return [e["values"] for e in out["embeddings"]]
    return [_bag_of_words(t) for t in texts]


def generate_json(prompt):
    """Ask the LLM for a JSON object and parse it."""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
    }
    out = _post(f"{API}/{TEXT_MODEL}:generateContent", body, timeout=25)
    text = out["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def cosine(a, b):
    if isinstance(a, dict):  # sparse bag-of-words fallback
        dot = sum(v * b.get(k, 0) for k, v in a.items())
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
    else:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _bag_of_words(text):
    vec = {}
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if len(word) > 2:
            vec[word] = vec.get(word, 0) + 1
    return vec
