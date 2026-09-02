from model import granite_response, llama_response, mistral_response


def call_all_models(system_prompt, user_prompt):
    llama_result = llama_response(system_prompt, user_prompt)
    granite_result = granite_response(system_prompt, user_prompt)
    mistral_result = mistral_response(system_prompt, user_prompt)

    print("Llama Response:\n", llama_result)
    print("\nGranite Response:\n", granite_result)
    print("\nMistral Response:\n", mistral_result)


if __name__ == "__main__":
    call_all_models(
        "You are a helpful assistant who provides concise and accurate answers.",
        "What is the capital of Canada? Tell me a cool fact about it as well.",
    )
