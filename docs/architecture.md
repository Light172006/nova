# Nova — Architecture

This document explains how Nova's pieces fit together. For the visual version, see [`nova-architecture.svg`](nova-architecture.svg) in this same folder.

## Overview

Nova is a local-first, multi-agent assistant. A single orchestrator (Nova itself) reasons about what you're asking for and decides how to handle it — answer directly, hand off to one specialized agent, or chain several agents together. Everything runs on your own machine; there is no cloud backend and no data leaves your computer.

## The core idea: orchestrator and chat agent share one model

Nova (the orchestrator) and the chat agent are **not** two different models — they're the same underlying LLM, called with two different system prompts and two different jobs:

- As **Nova**, the model is given a description of the available agents (as callable tools) and asked to reason about the request: does this need a direct answer, one agent, or a sequence of agents?
- As the **chat agent**, the same model is given a persona prompt and asked to either answer directly or narrate what another agent just did.

This keeps VRAM usage manageable on consumer hardware (a single loaded model doing double duty) and avoids running two separate model processes competing for the same 6GB of VRAM.

## Input and output layers

Voice is a translation layer, not a decision-maker, and sits in front of everything else:

```
Your voice → Speech-to-text (Whisper) → Nova → ... → Chat/voice agent → Text-to-speech → Speaker
```

STT converts speech to text before Nova ever sees it; TTS converts the chat agent's final reply back to speech. Neither layer decides anything — they just convert formats.

## The agents

| Agent | Responsibility | Notes |
|---|---|---|
| **Chat / voice agent** | Direct Q&A, and narrating what other agents did | Same model as Nova, different prompt. Also the only agent that produces spoken output. |
| **Automation agent** | OS-level actions — opening apps, running local commands | Triggered by voice or text; no model reasoning needed beyond what Nova already decided. |
| **Browsing agent** | Fetches and navigates the web | Wraps existing tooling (Playwright / `browser-use`) rather than being built from scratch. |
| **Writer / scribe agent** | Summarization, email drafting, activity log compression | Dual role: user-facing writing (emails, docs) and internal log summarization. Likely prompt-only, no fine-tuning needed. |
| **Coding agent** | Code editing and generation | Wraps existing tooling (Aider or similar). Until built, the chat agent handles minimal, self-contained coding requests as a placeholder — no file or repo-level operations. |

## Routing: single-hop vs. chains

Some requests need one agent. Others need a sequence. Nova has to tell the difference:

- **Single-hop** — "open YouTube" → automation agent, done.
- **Chain** — "what's today's political status" → browsing agent fetches → writer agent summarizes → chat/voice agent speaks the result.

For v1, chains are handled as a small number of fixed, known patterns (like the browse → summarize → speak example above), rather than a general-purpose planner that invents new sequences on the fly. A general planner is a later-stage problem.

## Agent contract

Every agent returns a consistent shape, regardless of what it actually does internally:

```
{status, result, needs_followup}
```

This is what lets Nova and the chat agent's narration layer treat every agent the same way, and it's what makes swapping a placeholder (like the temporary coding stand-in) for the real thing a one-line change rather than a rewrite.

## Memory — two separate systems

Nova needs two distinct kinds of memory, and they are deliberately not the same store:

### Conversational memory (chat agent only)
Semantic recall of past conversations, used only by the chat agent. Each turn is embedded and stored; before generating a reply, the top-k most relevant past turns are retrieved and added to the prompt.

- Storage: Chroma or pgvector

### Activity memory (Nova + all agents)
A record of what's actually been *done* — not what was said, but what happened. Hierarchical and compressed to keep reads fast regardless of how long Nova has been running:

- **Day file** — raw JSON Lines, one entry per action, written by every agent as it works
- **Week file** — a compressed summary of that week's day files
- **Month file** — a compressed summary of that month's week files

Nova reads the week and month summaries once, at boot. The chat agent reads today's day file during conversation, when relevant (e.g. "what have I been doing today"). Day files are rolled up and retired once summarized, so raw detail doesn't accumulate indefinitely.

## Confirmation before action

Any action with real-world side effects — sending an email, for instance — pauses for explicit confirmation before executing. Nova does not autonomously send, delete, or otherwise commit irreversible actions on your behalf without you confirming first. This applies broadly across agents, not just to one example case.

## What's deliberately out of scope for v1

- **Voice interruption** — handling you talking over Nova mid-response. Planned for a later version.
- **General multi-step planning** — Nova selects from known chain patterns rather than freely composing new ones.
- **Multi-user / hosted deployment** — Nova is built for a single user on a single machine. This is a design choice, not a limitation to be fixed later.

## Related documents

- [`nova-architecture.svg`](nova-architecture.svg) — the visual diagram
- [`setup.md`](setup.md) — installation and first-run instructions