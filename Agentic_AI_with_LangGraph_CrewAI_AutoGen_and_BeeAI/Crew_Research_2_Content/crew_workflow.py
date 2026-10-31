from crewai import Crew, Process

from agents import research_agent, social_media_agent, writer_agent
from tasks import research_task, social_media_task, writer_task

crew = Crew(
    agents=[research_agent, writer_agent, social_media_agent],
    tasks=[research_task, writer_task, social_media_task],
    process=Process.sequential,
    verbose=True
)

