from tavily import TavilyClient
import os

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def search_policy_evidence(policy_text: str) -> str:
    """
    Search for real-world policy examples using Tavily.
    """

    policy_text = str(policy_text)

    query = f"examples of policies similar to: {policy_text[:150]}"

    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=5
    )

    evidence = []

    for r in response.get("results", []):
        title = r.get("title", "")
        content = r.get("content", "")
        evidence.append(f"{title} — {content}")

    return "\n".join(evidence)