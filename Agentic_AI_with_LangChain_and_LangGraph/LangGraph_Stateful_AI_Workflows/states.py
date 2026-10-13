from typing import TypedDict


class AuthState(TypedDict):
    username: str | None
    password: str | None
    is_authenticated: bool | None
    output: str | None

# Defining the input node
def input_node(state):
    print(state)
    if state.get('username', "") == "":
        username = input("What is your username? ")

    password = input ("Enter your password: ")

    if state.get('username', "") == "":
        return {"username": username, "password": password}
    else:
        return {"password": password}


# Defining the validate credentials Node
def validate_credentials_node(state):
    username = state.get("username", "")
    password = state.get("password", "")

    print(f"Username: {username} - Password: {password}")

    if username == "test_user" and password == "secure_password":
        is_authenticated = True
    else:
        is_authenticated = False

    return {"is_authenticated": is_authenticated}

# Defining success node
def success_node(state):
    return {"output": "Authentication successful! Welcome."}


# Defining the failuer node
def failure_node(state):
    return {"output": "Authentication failed, please try again!"}

# Definind router
def router(state):
    if state['is_authenticated']:
        return 'success_node'
    else:
        return 'failure_node'

