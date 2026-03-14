from tavily import TavilyClient
import os

# Initialize Tavily client
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def search_policy_evidence(policy_text: str) -> str:
    """
    Retrieve real-world policy examples or research related to the policy text.
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
        url = r.get("url", "")

        evidence.append(f"{title} — {content} ({url})")

    return "\n".join(evidence)