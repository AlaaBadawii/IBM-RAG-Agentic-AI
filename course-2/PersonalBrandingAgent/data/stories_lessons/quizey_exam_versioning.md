# Quizey Exam Versioning — Copy-on-Write for Fairness

## Type

Architecture

## Context

Building Quizey V2 (`/home/alaabadawii/Quizey_V2/`), an exam platform. Teachers
needed to edit an exam after publishing it — while preserving what a launched
attempt actually ran against.

## Problem

If a teacher edits a published exam while students are taking it, what happens
to in-flight attempts and to grading? Naively editing a live exam would break
fairness and grading integrity.

## What I Did

Designed the exam model so editing a **published** exam auto-creates a new
version via `create_exam_version()` — a copy-on-write. Each published exam is
immutable; a new version starts as a draft, linked to its family by a
self-referential `root_exam_id`.

## Decision / Insight

Immutability via copy-on-write is clean: published artifacts stay immutable
while still being editable (by editing the new version). Versioning (demote-on-
publish) means only one version per family is published at a time, and the old
version remains gradable throughout editing — fairness before feature flush.

## Result

The exam domain now supports version families with copy-on-write, publish/
demote semantics, and a `(v{n})` title suffix with a 249-char cap. Attempts
reference the version they were created against.

## Engineering Lesson

When a "simple edit" requirement collides with in-flight users, the product's
integrity priorities should drive the data design. Immutability + versioning is
cleaner and safer than mutable shared state.

## Why This Matters

This is backend/systems thinking — architecture follows product priorities
(fair grading, consistency). It supports the backend engineering and
architecture direction.

## Evidence

- `/home/alaabadawii/Quizey_V2/app/services/exam_service.py`
- `/home/alaabadawii/Quizey_V2/docs/engineering/phase-1-foundation/00-summary.md`
- KB: `in_progress_projects/quizey_v2.md`

## Content Potential

- Architecture decision post ("why exam versioning is copy-on-write")
- Engineering tradeoff story tied to product fairness

Story strength:
STRONG

Reason:
A clear product-driven engineering decision with concrete implementation and a
transferable architectural lesson (immutability/copy-on-write).