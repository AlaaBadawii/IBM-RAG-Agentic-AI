from beeai_framework.agents.experimental import RequirementAgent
from beeai_framework.agents.experimental.requirements.ask_permission import (
    AskPermissionRequirement,
)
from beeai_framework.agents.experimental.requirements.conditional import (
    ConditionalRequirement,
)
from beeai_framework.memory import UnconstrainedMemory
from beeai_framework.middleware.trajectory import GlobalTrajectoryMiddleware
from beeai_framework.tools import Tool
from beeai_framework.tools.handoff import HandoffTool
from beeai_framework.tools.search.wikipedia import WikipediaTool
from beeai_framework.tools.think import ThinkTool
from beeai_framework.tools.weather import OpenMeteoTool

from llm import get_llm

# Agent 1: Destination Researsh Expert
destination_expert = RequirementAgent(
    llm=get_llm("watsonx"),
    tools=[WikipediaTool(), ThinkTool()],
    memory=UnconstrainedMemory(),
    instructions="""
You are a Destination Research Expert specializing in comprehensive travel destination analysis.

Your expertise:
- Landmarks and tourist activities
- Best times to visit and seasonal considerations
- Transportation options and accessibility
- Safety considerations and travel advisories

Always provide detailed, factual information with clear source attribution.
""",
    middlewares=[GlobalTrajectoryMiddleware(included=[Tool])],
    requirements=[
        ConditionalRequirement(
            ThinkTool,
            force_at_step=1,
            min_invocations=1,
            max_invocations=5,
            consecutive_allowed=False
        ),
        ConditionalRequirement(
            WikipediaTool,
            only_after=[ThinkTool],
            min_invocations=1,
            max_invocations=4,
            consecutive_allowed=False
        ),
    ]
)

# Agent 2: Travel Meteorologist
travel_meteorologist = RequirementAgent(
    llm=get_llm("watsonx"),
    tools=[OpenMeteoTool(), ThinkTool()],
    memory=UnconstrainedMemory(),
    instructions="""
You are a Travel Meteorologist specializing in weather analysis for travel planning.

Your expertise:
- Climate patterns and seasonal weather analysis
- Travel-specific weather recommendations
- Packing suggestions based on weather forecasts
- Activity planning based on weather conditions
- Regional climate variations and microclimates
- Weather-related travel risks and precautions

Focus on actionable weather guidance for travelers.
""",
    middlewares=[GlobalTrajectoryMiddleware(included=[Tool])],
    requirements=[
        ConditionalRequirement(
            ThinkTool,
            force_at_step=1,
            min_invocations=1,
            max_invocations=2,
        ),
        ConditionalRequirement(
            OpenMeteoTool,
            only_after=[ThinkTool],
            min_invocations=1,
            max_invocations=1
        )
    ]
)

# Agent 3: Language & Cultural expert
language_and_culture_expert = RequirementAgent(
    llm=get_llm("watsonx"),
    tools=[WikipediaTool(), ThinkTool()],
    memory=UnconstrainedMemory(),
    instructions="""
You are a Language & Cultural Expert specializing in linguistic and cultural guidance for travelers.

Your expertise:
- Local languages and dialects spoken in destinations
- Essential phrases and communication tips for travelers
- Cultural etiquette, customs, and social norms
- Religious and cultural sensitivities to be aware of
- Local communication styles and business etiquette
- Cultural festivals, events, and local celebrations
- Dining customs, tipping practices, and social interactions

Always emphasize cultural sensitivity and respectful travel practices.
""",
    middlewares=[GlobalTrajectoryMiddleware(included=[Tool])],
    requirements=[
        ConditionalRequirement(
            ThinkTool,
            force_at_step=1,
            min_invocations=1,
            max_invocations=3,
            consecutive_allowed=False
        ),
        ConditionalRequirement(
            WikipediaTool,
            force_after=ThinkTool,
            min_invocations=1,
            max_invocations=3
        )
    ]
)

# Agent 4: Travel Coordinator (Main Interface)

# Create handoff tools for coordination with unique names
handoff_to_destination = HandoffTool(
    destination_expert,
    name="DestinationResearch",
    description="Consult our Destination Research Expert for comprehensive information about travel destinations, attractions, and practical travel guidance.",
)
handoff_to_weather = HandoffTool(
    travel_meteorologist,
    name="WeatherPlanning",
    description="Consult our Travel Meteorologist for weather forecasts, climate analysis, and weather-appropriate travel recommendations.",
)

handoff_to_language = HandoffTool(
    language_and_culture_expert,
    name="LanguageCulturalGuidance",
    description="Consult our Language & Cultural Expert for essential phrases, cultural etiquette, and communication guidance for respectful travel.",
)

travel_coordinator = RequirementAgent(
    llm=get_llm("watsonx"),
    tools=[
        handoff_to_destination,
        handoff_to_weather,
        handoff_to_language,
        ThinkTool(),
    ],
    memory=UnconstrainedMemory(),
    instructions="""
You are the Travel Coordinator, the main interface for comprehensive travel planning.

Your role:
- Understand traveler requirements and preferences
- Coordinate with specialized expert agents as needed
- Synthesize information from multiple sources
- Create comprehensive, actionable travel recommendations
- Ensure all aspects of travel planning are covered

Available Expert Agents:
- Destination Expert: Practical destination information
- Travel Meteorologist: Weather analysis and climate recommendations  
- Language Expert: Language tips, cultural etiquette, and communication guidance

Coordination Process:
1. Think about what information is needed for comprehensive travel planning
2. Delegate specific queries to appropriate expert agents using handoff tools
3. Gather insights from multiple specialists
4. Synthesize information into cohesive travel recommendations
5. Provide a complete travel planning summary

Always ensure travelers receive well-rounded guidance covering destinations and landmarks, weather, and cultural considerations.
""",
    middlewares=[GlobalTrajectoryMiddleware(included=[Tool])],
    requirements=[
        ConditionalRequirement(ThinkTool, consecutive_allowed=False),
        AskPermissionRequirement(["DestinationResearch", "WeatherPlanning"]),
    ],
)
