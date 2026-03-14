from tavily import TavilyClient
import os
from dotenv import load_dotenv

load_dotenv()

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

response = client.search(
    query="congestion pricing policy examples",
    search_depth="advanced",
    max_results=3
)

print(response)