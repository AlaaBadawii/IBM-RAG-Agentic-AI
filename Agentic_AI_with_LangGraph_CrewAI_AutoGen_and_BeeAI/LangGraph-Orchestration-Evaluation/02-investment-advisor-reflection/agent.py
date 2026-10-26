from graph import optimizer_workflow

# invoke the workflow with an example investor profile
state = optimizer_workflow.invoke(
    {
        "investor_profile": (
            "Age: 29\n"
            "Salary: $110,000\n"
            "Assets: $40,000\n"
            "Goal: Achieve financial independence by age 45\n"
            "Risk tolerance: High"
        )
    }
)


def pretty_print_final_state(state: dict):
    print("🎯 Final Investment Plan Summary\n" + "="*40)
    print(f"\n📌 Investor Profile:\n{state['investor_profile']}")
    
    print("\n📈 Target Risk Grade:", state['target_grade'])
    print("📊 Final Assigned Grade:", state['grade'])
    print("🔁 Iterations Taken:", state['n'])

    print("\n📝 Evaluator Feedback:\n" + "-"*30)
    print(state['feedback'])

    print("\n📃 Final Investment Plan:\n" + "-"*30)
    print(state['investment_plan'])

pretty_print_final_state(state)

