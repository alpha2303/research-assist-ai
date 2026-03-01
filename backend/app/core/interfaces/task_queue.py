"""
TaskQueue interface for asynchronous task processing.

This interface abstracts task queue operations to allow swapping
implementations (e.g., Celery+Redis → AWS SQS) without changing
business logic.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class TaskStatus(Enum):
    """Status of an asynchronous task"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskResult:
    """Result of a task execution"""
    
    def __init__(
        self,
        task_id: str,
        status: TaskStatus,
        result: Any | None = None,
        error: str | None = None,
        progress: dict[str, Any] | None = None,
    ):
        self.task_id = task_id
        self.status = status
        self.result = result
        self.error = error
        self.progress = progress or {}


class TaskQueue(ABC):
    """
    Abstract interface for asynchronous task queue operations.
    
    Implementations:
    - CeleryTaskQueue: Celery with Redis backend (local development)
    - SQSTaskQueue: AWS SQS (production)
    """
    
    @abstractmethod
    async def submit_task(
        self,
        task_name: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        priority: int = 5,
    ) -> str:
        """
        Submit a task for asynchronous execution.
        
        Args:
            task_name: Name/identifier of the task to execute
            args: Positional arguments for the task
            kwargs: Keyword arguments for the task
            priority: Task priority (0-9, higher = more priority)
            
        Returns:
            Task ID for tracking
        """
        pass
    
    @abstractmethod
    async def get_task_status(self, task_id: str) -> TaskResult:
        """
        Get the current status and result of a task.
        
        Args:
            task_id: ID returned by submit_task
            
        Returns:
            TaskResult with current status and any available result/error
        """
        pass
    
    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """
        Attempt to cancel a pending or running task.
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def wait_for_task(
        self,
        task_id: str,
        timeout: float | None = None,
        poll_interval: float = 0.5,
    ) -> TaskResult:
        """
        Wait for a task to complete.
        
        Args:
            task_id: ID of the task to wait for
            timeout: Maximum time to wait in seconds (None = wait forever)
            poll_interval: How often to check status in seconds
            
        Returns:
            Final TaskResult
            
        Raises:
            TimeoutError: If timeout is reached before task completes
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close queue connections and cleanup resources"""
        pass
