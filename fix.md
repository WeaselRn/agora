I checked your file. The issue is not your route — your backend is working correctly. The real issue is how the response works.

Your endpoint:

@app.post("/api/evaluate")
async def api_evaluate(request: EvaluateRequest):

does NOT return JSON.
It returns a Server-Sent Events stream (SSE).

Specifically this line:

return EventSourceResponse(event_generator())

So your frontend cannot use normal fetch().then(res => res.json()).

Why your fetch stays pending

Your backend sends multiple streamed events like:

evaluation
evaluation
evaluation
debate
debate
synthesis
complete

Instead of a single JSON response.

Because of that:

fetch() → Promise stays pending

until the entire stream finishes (which takes ~2 minutes).

Correct way to call this API

You must use EventSource, not fetch.

Replace your fetch code with this:

const source = new EventSource("http://localhost:8000/api/evaluate");

source.onmessage = (event) => {
  console.log("message:", event.data);
};

source.addEventListener("evaluation", (event) => {
  console.log("evaluation:", JSON.parse(event.data));
});

source.addEventListener("debate", (event) => {
  console.log("debate:", JSON.parse(event.data));
});

source.addEventListener("synthesis", (event) => {
  console.log("synthesis:", JSON.parse(event.data));
});

source.addEventListener("complete", () => {
  console.log("done");
  source.close();
});
BUT there's a second problem

Standard EventSource cannot send POST data.

Your backend expects:

{
  "policy_text": "..."
}

So you have two options:

Option 1 (Recommended)

Change backend to GET + query param

@app.get("/api/evaluate")
async def api_evaluate(policy_text: str):

Then frontend works with EventSource:

const source = new EventSource(
  `http://localhost:8000/api/evaluate?policy_text=${encodeURIComponent(policyText)}`
);
Option 2

Keep POST and implement manual streaming fetch (harder).

Why your request takes ~2 minutes

Your pipeline runs:

1️⃣ 5 agent evaluations
2️⃣ 2 debate rounds
3️⃣ synthesis

Each agent calls the LLM.

So total LLM calls roughly:

5 evaluations
+ 10 debate calls
+ 1 synthesis
= 16 LLM calls

That explains the ~2 minute runtime.

show me a much cleaner frontend SSE client (about 30 lines) that will render each agent result live as it arrives.