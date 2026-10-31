from crew_workflow import crew

result = crew.kickoff(inputs={"topic": "Latest Generative AI breakthroughs"})

# Print the final output of the workflow using result.raw
print("Final Output: ", result.raw)


# The tasks_output list gives us access to outputs from each task in the order they were executed:
tasks_output = result.tasks_output
print("\n\nTasks Output:")

# output of the research task object
print("Task Description: ", tasks_output[0].description)
print("Output of research task: ", tasks_output[0])

# output of the writer task object
print("\nTask Description: ", tasks_output[1].description)
print("Output of writer task: ", tasks_output[1])

# output of the social media task object
print("\nTask Description: ", tasks_output[2].description)
print("Output of social media task: ", tasks_output[2])

# We can also access the agent that performed each task.
print("\nAgent for research task: ", tasks_output[0].agent)
print("Agent for writer task: ", tasks_output[1].agent)
print("Agent for social media task: ", tasks_output[2].agent)

# CrewAI provides detailed performance metrics that help you monitor resource usage
token_count = result.token_usage.total_tokens
prompt_tokens = result.token_usage.prompt_tokens
completion_tokens = result.token_usage.completion_tokens

print(f"Total tokens used: {token_count}")
print(f"Prompt tokens: {prompt_tokens} (used for instructions to the model)")
print(f"Completion tokens: {completion_tokens} (generated in response)")

