# 1) Google Gemini API (Python SDK)

### Official SDK

* **Package:** `google-genai`
* **Install:**

```bash
pip install google-genai
```

### Documentation

* [Gemini API Python SDK docs](https://ai.google.dev/gemini-api/docs/downloads?utm_source=chatgpt.com)

### Notes

* Google recommends the **GenAI SDK (GA)** as the official library. ([Google AI for Developers][1])
* Supports Python, JS, Go, Java.
* Replaces older/legacy Gemini libraries.

### Minimal Example (current pattern)

```python
from google import genai

client = genai.Client(api_key="YOUR_API_KEY")

response = client.models.generate_content(
    model="gemini-1.5-pro",
    contents="Explain Kubernetes in one paragraph"
)

print(response.text)
```

---

# 2) Anthropic Claude API (Python SDK)

### Official SDK

* **Package:** `anthropic`
* **Install:**

```bash
pip install anthropic
```

### Documentation

* [Anthropic Python SDK docs](https://platform.claude.com/docs/en/api/sdks/python?utm_source=chatgpt.com)

### Notes

* Requires Python **3.9+** ([Claude][2])
* Supports:

  * sync + async clients
  * streaming (SSE)
  * tool/function calling
  * Bedrock + Vertex integrations ([Claude][2])

### Minimal Example

```python
from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello Claude"}]
)

print(response.content)
```

---

# 3) OpenAI (ChatGPT / Responses API)

### Official SDK

* **Package:** `openai`
* **Install:**

```bash
pip install openai
```

### Documentation

* [OpenAI Python SDK docs](https://platform.openai.com/docs/libraries/python-bindings%23.docx?utm_source=chatgpt.com)
* [OpenAI Python GitHub repo](https://github.com/openai/openai-python?utm_source=chatgpt.com)

### Notes

* Official Python SDK with:

  * sync + async via `httpx`
  * typed models
  * Responses API (modern standard) ([GitHub][3])

### Minimal Example (modern API)

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.2",
    input="Explain ZFS ARC vs L2ARC briefly"
)

print(response.output_text)
```

---

# 4) OpenRouter API (Python SDK + OpenAI compatibility)

### Option A — Official SDK (Beta)

* **Package:** `openrouter`
* **Docs:**
* [OpenRouter Python SDK docs](https://openrouter.ai/docs/sdks/python/overview?utm_source=chatgpt.com)

### Install

```bash
pip install openrouter
```

### Example

```python
from openrouter import OpenRouter
import os

with OpenRouter(api_key=os.getenv("OPENROUTER_API_KEY")) as client:
    response = client.chat.send(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": "Hello"}]
    )

print(response)
```

### Notes

* Type-safe SDK generated from OpenAPI spec ([OpenRouter][4])
* Supports **300+ models via one API**

---

### Option B — Recommended (OpenAI SDK Compatibility)

OpenRouter is commonly used via the OpenAI SDK:

* [OpenRouter + OpenAI SDK guide](https://openrouter.ai/docs/guides/community/openai-sdk?utm_source=chatgpt.com)

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="YOUR_OPENROUTER_KEY"
)

response = client.chat.completions.create(
    model="anthropic/claude-sonnet-4",
    messages=[{"role": "user", "content": "Hello"}]
)

print(response.choices[0].message)
```

### Notes

* OpenRouter **reuses OpenAI SDK interface** for compatibility ([OpenRouter][5])
* Enables switching between:

  * OpenAI
  * Anthropic
  * Gemini
  * others (DeepSeek, etc.)

---

# Consolidated Comparison

| Provider      | Package                 | API Style       | Key Strength            |
| ------------- | ----------------------- | --------------- | ----------------------- |
| Google Gemini | `google-genai`          | Native SDK      | Tight Google ecosystem  |
| Anthropic     | `anthropic`             | Native SDK      | Tool use + streaming    |
| OpenAI        | `openai`                | Native SDK      | Most mature ecosystem   |
| OpenRouter    | `openrouter` / `openai` | Unified gateway | Multi-model abstraction |

---

# Key Practical Insight

For your homelab / multi-model pipelines:

* **Best abstraction layer:**
  → Use **OpenAI SDK + OpenRouter base_url**
* **Best native SDKs (feature-complete):**

  * Anthropic (`anthropic`)
  * OpenAI (`openai`)
  * Google (`google-genai`)

This allows:

* swapping models via config only
* unified message schema
* minimal vendor lock-in

---

If required, can provide:

* unified wrapper (single Python client supporting all 4)
* Docker-ready microservice
* benchmarking harness across providers

[1]: https://ai.google.dev/gemini-api/docs/downloads?utm_source=chatgpt.com "Gemini API libraries  |  Google AI for Developers"
[2]: https://platform.claude.com/docs/en/api/sdks/python?utm_source=chatgpt.com "Python SDK - Claude API Docs"
[3]: https://github.com/openai/openai-python?utm_source=chatgpt.com "GitHub - openai/openai-python: The official Python library for the OpenAI API"
[4]: https://openrouter.ai/docs/sdks/python/overview?utm_source=chatgpt.com "OpenRouter Python SDK | Complete Documentation | OpenRouter | Documentation"
[5]: https://openrouter.ai/docs/guides/community/openai-sdk?utm_source=chatgpt.com "OpenAI SDK Integration | OpenRouter SDK Support | OpenRouter | Documentation"
