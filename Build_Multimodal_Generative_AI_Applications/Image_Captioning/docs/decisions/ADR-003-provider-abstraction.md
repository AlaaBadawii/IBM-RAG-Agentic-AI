# ADR-003: Provider Abstraction

## Context
The application must call a vision model but should not know how the provider works internally.

## Decision
Separate the provider client (`src/clients/openrouter.py`) from the business logic (`src/services/vision.py`). The client only talks to the API; the service orchestrates the pipeline.

## Why
- Provider can be swapped without touching service logic
- Testing requires mocking only the client interface
- Clear separation of concerns
- Prompt construction is independent of the provider

## Alternatives
- Monolithic code (provider logic mixed with business logic)
- Inline API calls throughout the application

## Consequences
- The client returns raw text; the service wraps it in `VisionResult`
- Changing providers requires a new client module, not service changes
- The message builder (`build_image_message`) is provider-agnostic
