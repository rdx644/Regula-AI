# ADR 0001: Technology Stack

## Status
Accepted

## Context
We need a highly scalable, robust stack for the RegulaAI platform that supports rapid development, robust typing, and complex agentic AI workflows. The platform comprises a frontend dashboard, a backend API, agentic workflows, and document processing systems.

## Decision
We have decided to use the following stack:
- **Frontend**: Next.js with React, Tailwind CSS, and TypeScript. This provides a robust React framework with SSR capabilities, structured routing (App Router), and strict typing.
- **Backend API**: FastAPI (Python). Python is the industry standard for AI integrations, and FastAPI provides high performance, automatic OpenAPI documentation, and asynchronous capabilities.
- **Database**: PostgreSQL with `pgvector`. PostgreSQL serves as the reliable system of record, while `pgvector` enables unified storage of both relational compliance data and high-dimensional vectors for semantic search and retrieval.
- **Agent Orchestration**: LangGraph / LangChain. This allows for stateful, graph-based agent workflows needed for complex reasoning (Supervisor, Planning, Tool Execution).
- **Storage**: Private object storage (e.g., S3-compatible) to securely manage confidential regulatory documents and internal bank evidence.

## Consequences
- **Positive**: High developer velocity, excellent AI ecosystem support (Python/LangChain), robust data integrity (Postgres), and modern UI patterns (Next.js/Tailwind).
- **Negative**: Requires managing separate frontend and backend deployments, increasing initial DevOps complexity compared to a full-stack Next.js monolith. However, the separation is strictly necessary due to heavy Python AI requirements.
