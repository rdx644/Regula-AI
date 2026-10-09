import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from pythonjsonlogger import jsonlogger

from app.core.config import settings


class RequestContextFilter(logging.Filter):
    """Add request context to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Add default values
        record.request_id = getattr(record, "request_id", "-")
        record.organization_id = getattr(record, "organization_id", "-")
        record.user_id = getattr(record, "user_id", "-")
        record.workflow_id = getattr(record, "workflow_id", "-")
        record.agent_run_id = getattr(record, "agent_run_id", "-")
        return True


class StructuredJSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logs."""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        # Exception stacks can contain SQL bind values or private documents.
        if record.exc_info:
            log_record.pop("exc_info", None)
            log_record["error_type"] = record.exc_info[0].__name__
        
        # Add standard fields
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["module"] = record.module
        log_record["function"] = record.funcName
        log_record["line"] = record.lineno
        
        # Add context fields if present
        for field in ["request_id", "organization_id", "user_id", "workflow_id", "agent_run_id", "agent_step_id"]:
            if hasattr(record, field):
                log_record[field] = getattr(record, field)
        
        # Add model info if present
        for field in ["model", "provider", "tokens_used", "latency_ms"]:
            if hasattr(record, field):
                log_record[field] = getattr(record, field)


def setup_logging():
    """Configure structured logging for the application."""
    
    log_level = logging.INFO
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    # Set formatter
    formatter = StructuredJSONFormatter(
        "%(timestamp)s %(level)s %(name)s %(message)s",
        timestamp=True,
    )
    handler.setFormatter(formatter)
    
    # Add context filter
    handler.addFilter(RequestContextFilter())
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = [handler]
    
    # Configure specific loggers
    for logger_name in ["uvicorn", "uvicorn.access", "fastapi", "sqlalchemy.engine"]:
        logger = logging.getLogger(logger_name)
        logger.handlers = [handler]
        logger.setLevel(log_level)
        logger.propagate = False
    # SDK/SQL debug output may include credentials, document text and bind values.
    for logger_name in ["sqlalchemy.engine", "boto3", "botocore", "urllib3", "httpx", "httpcore", "openai"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding request context to logs."""
    
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.old_factory = logging.getLogRecordFactory()
    
    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.kwargs.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, *args):
        logging.setLogRecordFactory(self.old_factory)


def log_agent_execution(
    logger: logging.Logger,
    agent_name: str,
    workflow_type: str,
    organization_id: str,
    user_id: str = None,
    request_id: str = None,
    workflow_id: str = None,
    agent_run_id: str = None,
    agent_step_id: str = None,
    model: str = None,
    provider: str = None,
    tokens_used: int = None,
    latency_ms: int = None,
    status: str = "started",
    error: str = None,
):
    """Log agent execution with structured context."""
    extra = {
        "agent_name": agent_name,
        "workflow_type": workflow_type,
        "organization_id": organization_id,
        "user_id": user_id or "-",
        "request_id": request_id or "-",
        "workflow_id": workflow_id or "-",
        "agent_run_id": agent_run_id or "-",
        "agent_step_id": agent_step_id or "-",
        "model": model or "-",
        "provider": provider or "-",
        "tokens_used": tokens_used or 0,
        "latency_ms": latency_ms or 0,
        "agent_status": status,
        "error": "",
    }
    
    if status == "started":
        logger.info(f"Agent {agent_name} started", extra=extra)
    elif status == "completed":
        logger.info(f"Agent {agent_name} completed", extra=extra)
    elif status == "failed":
        logger.error(f"Agent {agent_name} failed", extra=extra)
    else:
        logger.info(f"Agent {agent_name} {status}", extra=extra)


def log_tool_call(
    logger: logging.Logger,
    tool_name: str,
    agent_name: str,
    organization_id: str,
    request_id: str = None,
    workflow_id: str = None,
    agent_run_id: str = None,
    agent_step_id: str = None,
    duration_ms: int = None,
    status: str = "started",
    error: str = None,
):
    """Log tool invocation with structured context."""
    extra = {
        "tool_name": tool_name,
        "agent_name": agent_name,
        "organization_id": organization_id,
        "request_id": request_id or "-",
        "workflow_id": workflow_id or "-",
        "agent_run_id": agent_run_id or "-",
        "agent_step_id": agent_step_id or "-",
        "duration_ms": duration_ms or 0,
        "tool_status": status,
        "error": "",
    }
    
    if status == "started":
        logger.info(f"Tool {tool_name} started", extra=extra)
    elif status == "completed":
        logger.info(f"Tool {tool_name} completed", extra=extra)
    elif status == "failed":
        logger.error(f"Tool {tool_name} failed", extra=extra)
