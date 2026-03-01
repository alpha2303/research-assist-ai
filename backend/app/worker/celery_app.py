"""Celery application configuration for async task processing."""

from celery import Celery

from app.core.config import get_settings

# Get application settings
settings = get_settings()

# Create Celery app
celery_app = Celery(
    "research_assist_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"]  # Module containing task definitions
)

# Celery configuration
celery_app.conf.update(
    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task result settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",  # For Redis sentinel (if used)
    },
    
    # Task routing
    task_routes={
        "app.worker.tasks.process_document": {"queue": "document_processing"},
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Don't prefetch tasks (better for long-running tasks)
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (prevent memory leaks)
    
    # Retry settings
    task_acks_late=True,  # Acknowledge task after completion (not before)
    task_reject_on_worker_lost=True,  # Requeue task if worker crashes
    
    # Rate limiting
    task_time_limit=3600,  # Hard time limit: 1 hour
    task_soft_time_limit=3300,  # Soft time limit: 55 minutes
)

# Optional: Configure Celery beat for periodic tasks (future use)
celery_app.conf.beat_schedule = {
    # Example periodic task
    # 'cleanup-old-results': {
    #     'task': 'app.worker.tasks.cleanup_old_results',
    #     'schedule': crontab(hour=2, minute=0),  # Run at 2 AM daily
    # },
}

if __name__ == "__main__":
    celery_app.start()
