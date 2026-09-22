# ADR-001: OpenRouter as Provider

## Context
We needed a vision-capable LLM for multimodal image understanding. Direct provider SDKs (OpenAI, Anthropic) would lock us to a single provider.

## Decision
Use OpenRouter as the intermediary. It provides an OpenAI-compatible API across multiple model providers.

## Why
- Access to multiple vision models through one interface
- Model switching requires configuration changes only
- OpenAI-compatible SDK means no provider-specific code

## Alternatives
- Direct OpenAI API (single provider lock-in)
- Direct Anthropic API (different API structure)

## Consequences
- One provider client (`src/clients/openrouter.py`) isolates all provider-specific code
- Adding a new provider only requires a new client module
- OpenRouter-specific errors are translated to application-level errors
