"""Integration layer: someone else's system, behind a boundary we control.

Each subpackage wraps one external service and returns structured results
rather than raising or printing, so a caller can always tell what happened.
Nothing above this layer talks to an external service directly, and nothing
below it knows what the rest of the application wants.

    app.integrations.linkedin   publishing to LinkedIn (Step 5)
"""
