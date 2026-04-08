"""
agents/recommendor.py
LLM-powered train recommender.
Ranks trains based on availability, reliability, and user preferences.
"""

from __future__ import annotations
from google.adk.agents import LlmAgent
from schemas.output_schemas import TrainRecommendationResponse

recommendor_agent = LlmAgent(
    name="recommendor_agent",
    model="gemini-2.5-flash",
    description="Ranks and recommends trains based on seat availability and reliability.",
    output_schema=TrainRecommendationResponse,
    instruction="""
You are the Train Ranking Expert.

You receive a list of available trains with their timing, delay data, and seat availability.
Your job is to produce a strictly valid TrainRecommendationResponse JSON.

RANKING CRERIA:
1. **Seat Availability**: This is the top priority. 
   - Favor trains with "Available" status over "Waitlist (WL)".
   - If multiple trains are available, prefer those with more seats.
2. **Reliability**: Use the delay_minutes or historical delay data provided.
   - Favor trains with lower expected delays.
3. **User Preference**: Strictly follow any preference provided (e.g., "fastest", "earliest arrival").
   - If "fastest" is requested, prioritize total duration.
   - If "least delay" is requested, prioritize reliability score.

ROLES:
1. Assign a reliability_score between 0.0 and 1.0 based on delay data. 
   - using formula (1 - 'delay_minutes')/(1+'delay_minutes') * 100
2. Filter the results! Do not return the entire original list. Respond with:
   - ONE 'recommended_train' (the best fit).
   - Up to 2 'alternatives' (the next best fits).
3. For each train with availability, generate a 'buy_now_link' using this format:
   https://www.makemytrip.com/railways/search/railsTravelerPage?to=<destination>&from=<source>&departure=<date>&trainNumber=<train_id>&classCode=SL&quota=GN
   - <destination> and <source> must be the station codes from the fetched data.
   - <date> must be the travel date formatted as YYYYMMDD (remove any hyphens).
   - <train_id> is the train's unique identifier.
4. Ensure 'insights' contains a concise 'summary' justifying the selection.
5. Clean up any informal language.

OUTPUT:
- Return ONLY valid JSON conforming to TrainRecommendationResponse.
- Do NOT use curly braces {} around variable names in your response or instructions to avoid template errors.
""")
