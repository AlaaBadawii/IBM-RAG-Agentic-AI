import logging

from autogen import ConversableAgent, GroupChat, GroupChatManager

from llm_config import llm_config

logging.getLogger("autogen.aoi.client").setLevel(logging.ERROR)


planner_message = "Create a short lesson plan for 4th grades."
reviewer_message = "Review a plan and suggest up to 3 brief edites"
teacher_message = "Suggest a topic and reply DONE when satisfied."

lesson_planner = ConversableAgent(
    name="planner_agent",
    system_message=planner_message,
    description="Makes lesson plans.",
    llm_config=llm_config,
)

lesson_reviewer = ConversableAgent(
    name="reviewer_agent",
    system_message=reviewer_message,
    description="Reviews lesson plans and suggests edits.",
    llm_config=llm_config,
)

teacher = ConversableAgent(
    name="teacher_agent",
    system_message=teacher_message,
    llm_config=llm_config,
    is_termination_msg=lambda x: "DONE" in (x.get("content", "") or "").upper(),
)


groupchat = GroupChat(
    agents=[teacher, lesson_planner, lesson_reviewer],
    speaker_selection_method="auto",
)


manager = GroupChatManager(
    name="groupchat_manager",
    groupchat=groupchat,
    llm_config=llm_config,
)


teacher.initiate_chat(
    recipient=manager,
    message="Make a simple lesson about the moon",
    max_trurns=6,
    summary_method="reflection_with_llm"
)

