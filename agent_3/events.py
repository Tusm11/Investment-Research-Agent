from pydantic import BaseModel,Field
from typing import List
class Event(BaseModel):
    """Standard schema for a company event extracted from the news"""
    date:str=Field(description="Date of the news article")
    headline:str=Field(description="Headline of the news article")
    event_types:List[str]=Field(description="List of event types describing the event.")
    importance:str=Field(description="Importance level of the event: LOW, MEDIUM, HIGH, VERY_HIGH")
    summary:str=Field(description="Concise and short summary of the event")
    confidence:float=Field(description="Confidence score between 0 and 1 indicating the reliability of the extracted event information")

    