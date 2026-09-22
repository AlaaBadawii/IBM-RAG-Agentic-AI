# ADR-002: Base64 Data URLs for Image Representation

## Context
JSON is text-based; images are binary. We needed a way to send binary image data through a text-based API.

## Decision
Use Base64-encoded data URLs (`data:image/<type>;base64,<encoded>`) as the image representation.

## Why
- Single string can represent any binary image
- Works with the OpenAI-compatible chat completion API
- No multipart form encoding needed
- Universal support across vision-capable models

## Alternatives
- Multipart form data (requires different API structure)
- Cloud storage URLs (requires provider to fetch from URL)
- Image embeddings (loses pixel-level detail)

## Consequences
- Image payload size increases ~33% due to Base64 encoding
- Image optimization (resize) is needed to control costs
- The `src/images/encoder.py` module encapsulates all encoding logic
