# Project Context Snapshot

## Project Summary
dev-memory is a Python-based CLI tool that automates the generation of daily standup and developer logs by collecting Git activity from multiple repositories.

## Core Objective
To aggregate daily and monthly development activities (commits and working tree) into JSON and Markdown reports to streamline the daily standup process.

## Architecture Overview
The project follows a five-layered architecture: Data Aggregation (Git models), Analyzer Layer (rule-based classification), Presentation Layer (Markdown generation), Execution/Scheduling Layer (Cron and startup recovery), and Notification Layer (Discord delivery).

## Tech Stack
- Python
- Git
- JSON
- Markdown
- Discord API
- Gemini AI
- unittest
- urllib


## Key Decisions
- Use of Python standard library only for the core CLI tool
- Implementation of a 06:00 cut-off window for daily reports
- Monday special rule to include Friday-Sunday activity
- Presentational-only AI narratives that do not modify raw JSON data
- Idempotency and state tracking via a state.json file
- Dual scheduling using Cron and a startup recovery fallback


## Constraints
- Core logic must rely on the Python standard library
- AI failures must not prevent report generation
- Discord notification errors must not block the main execution flow
- Discord message length is limited to 1800 characters before utilizing attachments


## Assumptions


## Open Problems


## Risks
- Cron execution failure when the device is off or in sleep mode
- Discord rate limiting and HTTP status errors (401, 403, 404, 429)
- Security risks such as request smuggling (noted in related reading)
- Invalid Git repository paths and AI service failures


## Current Focus
Generating automated LinkedIn captions and development logs from the dev-memory project to provide objective standup updates.

## Next Steps


## Bootstrap Prompt

You are continuing development of the following project.

Below is the current structured project state:

project_summary: dev-memory is a Python-based CLI tool that automates the generation of daily standup and developer logs by collecting Git activity from multiple repositories.
core_objective: To aggregate daily and monthly development activities (commits and working tree) into JSON and Markdown reports to streamline the daily standup process.
architecture_overview: The project follows a five-layered architecture: Data Aggregation (Git models), Analyzer Layer (rule-based classification), Presentation Layer (Markdown generation), Execution/Scheduling Layer (Cron and startup recovery), and Notification Layer (Discord delivery).
tech_stack:
- Python
- Git
- JSON
- Markdown
- Discord API
- Gemini AI
- unittest
- urllib
key_decisions:
- Use of Python standard library only for the core CLI tool
- Implementation of a 06:00 cut-off window for daily reports
- Monday special rule to include Friday-Sunday activity
- Presentational-only AI narratives that do not modify raw JSON data
- Idempotency and state tracking via a state.json file
- Dual scheduling using Cron and a startup recovery fallback
constraints:
- Core logic must rely on the Python standard library
- AI failures must not prevent report generation
- Discord notification errors must not block the main execution flow
- Discord message length is limited to 1800 characters before utilizing attachments
assumptions:
open_problems:
risks:
- Cron execution failure when the device is off or in sleep mode
- Discord rate limiting and HTTP status errors (401, 403, 404, 429)
- Security risks such as request smuggling (noted in related reading)
- Invalid Git repository paths and AI service failures
todos:
- Generate daily and monthly reports
- Install and remove cron jobs
- Install and remove startup hooks
- Send reports to Discord with automated retries
- Execute unit tests for date range logic and delivery systems
current_focus: Generating automated LinkedIn captions and development logs from the dev-memory project to provide objective standup updates.
next_steps:

Instructions:
- Do not re-explain basics.
- Assume all technical decisions listed are already accepted.
- Focus only on advancing the project.
- Be precise and technical.
- Avoid generic advice.
