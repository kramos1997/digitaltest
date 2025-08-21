# ClarityDesk - GDPR-First Deep Research Platform

## Overview

ClarityDesk is a production-ready research platform that provides Perplexity-style deep research with comprehensive citations, source tracking, and audit-ready evidence matrices. The application is designed as a GDPR-compliant research tool for business users, offering real-time answer synthesis with full source attribution and evidence trails.

The platform performs query expansion, searches multiple sources via SearXNG, scrapes and ranks content, then synthesizes comprehensive answers with numbered citations. It features a clean, professional interface optimized for business research workflows with comprehensive privacy controls.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: Server-rendered HTML with Jinja2 templates + HTMX for interactivity
- **Styling**: Tailwind CSS with custom component library and shadcn/ui components
- **Client Framework**: React with TypeScript (client directory) alongside traditional templates
- **Real-time Updates**: HTMX for streaming research results and progressive enhancement
- **Responsive Design**: Mobile-first approach with professional business UI

### Backend Architecture
- **Framework**: FastAPI with Python 3.11+, fully async with type hints
- **Architecture Pattern**: Dependency injection with modular service layers
- **API Design**: RESTful endpoints with streaming responses for real-time research
- **Rate Limiting**: slowapi integration for API protection
- **Error Handling**: Structured logging with GDPR-compliant data redaction

### Core Research Pipeline
- **Query Expansion**: Multi-strategy expansion (temporal, domain bias, context enhancement)
- **Search Integration**: SearXNG client with configurable endpoints
- **Content Processing**: Parallel scraping with readability extraction and trafilatura
- **Ranking System**: Heuristic scoring with optional LLM-based reranking
- **Answer Synthesis**: Multi-stage LLM pipeline with factchecking and citation validation
- **Evidence Matrix**: Audit-ready evidence trails linking claims to sources

### Data Storage Solutions
- **Database**: PostgreSQL with Drizzle ORM for schema management
- **Session Management**: PostgreSQL-backed sessions with connect-pg-simple
- **GDPR Mode**: Memory-only processing with automatic cleanup (no persistent storage)
- **Caching Strategy**: In-memory caching for research sessions

### Authentication and Authorization
- **Session-based**: Traditional session management without complex user accounts
- **Rate Limiting**: IP-based rate limiting with configurable thresholds
- **Privacy Controls**: GDPR mode with enhanced data protection and minimal logging

### LLM Integration Architecture
- **Multi-Provider Support**: Abstracted LLM client supporting Mistral API and OpenAI-compatible endpoints
- **Provider Selection**: Environment-driven configuration (Mistral EU for GDPR compliance)
- **Streaming**: Real-time response streaming for improved user experience
- **Prompt Engineering**: Specialized prompts for research synthesis, factchecking, and document ranking

## External Dependencies

### Search Services
- **SearXNG**: Primary search aggregation service (configurable endpoint via SEARX_URL)
- **Search Engines**: Multiple search engines aggregated through SearXNG

### LLM Providers
- **Mistral API**: Primary LLM provider with EU hosting for GDPR compliance
- **OpenAI-Compatible Endpoints**: Alternative provider support (e.g., vLLM deployments)
- **Configuration**: Environment-driven provider selection with fallback support

### Content Processing
- **Web Scraping**: httpx for HTTP requests, readability-lxml and trafilatura for content extraction
- **HTML Processing**: BeautifulSoup4 for DOM manipulation and cleaning

### Infrastructure Services
- **Database**: PostgreSQL (via @neondatabase/serverless for cloud deployment)
- **Build Tools**: Vite for frontend bundling, ESBuild for server compilation
- **Development**: TypeScript compilation, Tailwind CSS processing

### Monitoring and Compliance
- **Logging**: Structured JSON logging with GDPR-compliant data redaction
- **Privacy**: Automatic PII detection and redaction in GDPR mode
- **Rate Limiting**: Request throttling and abuse prevention