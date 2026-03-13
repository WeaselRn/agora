Remaining issues, ranked:
🔴 1. Rate limit logic is broken when semaphore is 3
The _last_call_time is a single shared float, but 3 coroutines can now enter the semaphore block simultaneously. They all read the same _last_call_time, all see elapsed >= MIN_INTERVAL, all skip the sleep, and all fire at the same time — blowing through the rate limit. The interval check only works correctly with Semaphore(1).
Fix — track last call time per slot using a list, or more simply, update _last_call_time before the API call so the next coroutine entering sees it as "just used":
pythonasync with self._semaphore:
    now = time.monotonic()
    elapsed = now - self._last_call_time
    if elapsed < self.MIN_INTERVAL:
        await asyncio.sleep(self.MIN_INTERVAL - elapsed)
    self._last_call_time = time.monotonic()  # ← move this BEFORE the call
    response = await loop.run_in_executor(...)
    return response.text
This way the next coroutine entering the semaphore sees the updated timestamp and backs off correctly.
🔴 2. assert in runner will be silently stripped with python -O
Still present from before. One line fix:
python# replace this:
assert not unknown, f"Evaluated agent names not found in PERSONAS: {unknown}"

# with this:
if unknown:
    raise ValueError(f"Evaluated agent names not found in PERSONAS: {unknown}")
🔴 3. _llm singleton missing — new client per request
llm = create_llm_client() is still inside api_evaluate, meaning every HTTP request creates a fresh GeminiClient with its own semaphore and its own _last_call_time. Two concurrent requests = two independent rate limiters = double the API calls at the same moment. Move it to module level:
python# at module level, after app = FastAPI(...)
_llm = create_llm_client()

@app.post("/api/evaluate")
async def api_evaluate(request: EvaluateRequest):
    async def event_generator():
        ...
        async def run_pipeline():
            await evaluate_policy(request.policy_text, _llm, callback=sse_callback)