import logging

from autogen import ConversableAgent, GroupChat, GroupChatManager

from llm_config import llm_config

logging.getLogger("autogen.oai.client").setLevel(logging.ERROR)


# step 1: Create Agents

# Patient Agent
patient_agent = ConversableAgent(
    name="patient",
    system_message="You describe symptoms and ask for medical help.",
    llm_config=llm_config,
)

# Diagnosis Agent
diagnosis_agent = ConversableAgent(
    name="diagnosis",
    system_message="You analyze symptoms and provide a possible diagnosis. Summarize key points in one response.",
    llm_config=llm_config,
)

# Pharmacy Agent
pharmacy_agent = ConversableAgent(
    name="pharmacy",
    system_message="You recommend medications based on the provided diagnosis, only respond once",
    llm_config=llm_config,
)

# Consultation Agent
consultation_agent = ConversableAgent(
    name="consultation",
    system_message="You determine if a doctor's visit is required. Provide a final summary with clear next steps. IMPORTANT: End your response with 'CONSULTATION_COMPLETE' to signal the end of the conversation.",
    llm_config=llm_config,
)

# Step 2: Create GroupChat for structured interaction
groupchat = GroupChat(
    agents=[diagnosis_agent, pharmacy_agent, consultation_agent],
    messages=[],
    max_round=5,
    speaker_selection_method="round_robin",
)

# Step 3: Create GroupChatManager to Handle Conversation
manager = GroupChatManager(name="manager", groupchat=groupchat)


# Step 4: Start the conversation with the patient agent
print("\n🤖 Welcome to the AI Healthcare Consultation System!")
symptoms = input("Please describe your symptoms: ")
print("\n🩺 Diagnosing symptoms...")

response = patient_agent.initiate_chat(
    recipient=manager,
    message=f"I am feeling {symptoms}. Can you help me understand what might be wrong?"
)

