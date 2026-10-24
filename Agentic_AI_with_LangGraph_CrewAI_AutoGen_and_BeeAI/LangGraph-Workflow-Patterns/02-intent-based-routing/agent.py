from graph import app

input_text = {"user_input": "Can you translate this sentence: I love programming?"}

result = app.invoke(input_text)
print("========= test translate =========")
print(result["output"])
print(result["task_type"])


input_text = {
    "user_input": "Can you summarize this sentence: I love programming so much it is the best thing ever. All I want to do is programming?"
}

result = app.invoke(input_text)

print("========= test summarize =========")
print(result["output"])
print(result["task_type"])