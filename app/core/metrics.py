from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
HTTP_LATENCY = Histogram("http_request_duration_seconds", "HTTP latency", ["method", "path"])
DB_ERRORS = Counter("db_errors_total", "Database errors")
AI_REQUESTS = Counter("ai_requests_total", "AI assistant requests", ["outcome"])
AI_LATENCY = Histogram("ai_latency_seconds", "LLM call latency", ["operation"])
AI_TOOL_CALLS = Counter("ai_tool_invocations_total", "AI tool invocations", ["tool", "outcome"])
CELERY_FAILURES = Counter("celery_task_failures_total", "Celery task failures", ["task"])
