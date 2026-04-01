from google.adk.tools import google_search, load_web_page
from google.adk.agents.llm_agent import Agent

def get_curr_data(city: str) -> str:
    # Step 1: Search to find the right URL
    results = google_search(f"current temperature {city} weather")
    
    # Step 2: Fetch the live page — NOT the meta description
    url = results[0].url  # e.g. weather.com or timeanddate.com
    page_content = load(url)  # ADK's built-in URL loader
    
    # Step 3: Parse the live content for the actual value
    # (or pass page_content to the LLM to extract the temperature)
    return page_content

google_search_analyzer = Agent(
    model       ='gemini-2.5-flash',
    name        ='google_search_analyzer',
    description ='A search analyzer that uses google search to find latest informaition about current events, weather, or business hours.',
    instruction ="""
        When asked for real-time data like weather or prices:
        1. Use google_search to find a reliable source URL
        2. Use load_web_page on that URL to get fresh content
        3. Never use the search result snippet — it may be stale
    """,
    tools       =[google_search],
)