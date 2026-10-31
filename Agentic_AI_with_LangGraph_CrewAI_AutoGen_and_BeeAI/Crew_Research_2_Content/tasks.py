from crewai import Task

from agents import research_agent, social_media_agent, writer_agent

research_task = Task(
    description="Analyze the major {topic}, identifying key trends and technologies. Provide a detailed report on their potential impact",
    agent=research_agent,
    expected_output="A detailed report on {topic}, including trends, emerging technologies, and their impact.",
)

writer_task = Task(
    description="Create an engaging blog post based on the research findings about {topic}. Tailor the content for a tech-savvy audience, ensuring clarity and interest.",
    agent=writer_agent,
    expected_output="A 4-paragraph blog post on {topic}, written clearly and engagingly for tech enthusiasts.",
)

social_media_task = Task(
    description="Summarize the blog post about {topic} into 2–3 engaging social media posts "
    "suitable for platforms like LinkedIn or Twitter. Make sure the tone is informative, "
    "professional, and encourages further reading.",
    agent=social_media_agent,
    expected_output="A series of 2-3 social media posts on {topic}, each crafted to engage audiences on platforms like Twitter, LinkedIn, and Instagram, highlighting the key insights from the blog content.",
)
