from graph import workflow

app = workflow.compile()

if __name__ == "__main__":
    # Note:  The correct password is secure_password,
    # it's fixed because we don't have any auth system yet,
    # so make sure to enter that to authenticate successfully.
    inputs = {"username": "test_user"}
    result = app.invoke(inputs)
    print(result)
