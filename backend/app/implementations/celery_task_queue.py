"""Celery-based implementation of the TaskQueue interface.

Wraps Celery's task submission, status checking, and cancellation APIs
behind the abstract TaskQueue contract, allowing the business layer to
remain agnostic of the concrete queue technology.
"""

import asyncio
import time
from typing import Any

from celery import Celery
from celery.result import AsyncResult

from app.core.interfaces.task_queue import TaskQueue, TaskResult, TaskStatus

# Map Celery state strings → TaskStatus enum
_CELERY_STATE_MAP: dict[str, TaskStatus] = {
    "PENDING": TaskStatus.PENDING,
    "STARTED": TaskStatus.RUNNING,
    "RETRY": TaskStatus.RUNNING,
    "SUCCESS": TaskStatus.COMPLETED,
    "FAILURE": TaskStatus.FAILED,
    "REVOKED": TaskStatus.CANCELLED,
}


class CeleryTaskQueue(TaskQueue):
    """TaskQueue implementation backed by Celery + Redis.

    Parameters
    ----------
    celery_app:
        A configured ``Celery`` instance (typically imported from
        ``app.worker.celery_app``).
    """

    def __init__(self, celery_app: Celery) -> None:
        self._app = celery_app

    # ------------------------------------------------------------------
    # TaskQueue interface
    # ------------------------------------------------------------------

    async def submit_task(
        self,
        task_name: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        priority: int = 5,
    ) -> str:
        """Submit a named Celery task and return its task ID."""
        result: AsyncResult = self._app.send_task(
            task_name,
            args=args or [],
            kwargs=kwargs or {},
            priority=priority,
        )
        task_id: str = result.id  # type: ignore[assignment]
        return task_id

    async def get_task_status(self, task_id: str) -> TaskResult:
        """Query Celery for the current state of *task_id*."""
        result = AsyncResult(task_id, app=self._app)
        status = _CELERY_STATE_MAP.get(result.state, TaskStatus.PENDING)

        error = None
        task_result = None
        if status == TaskStatus.COMPLETED:
            task_result = result.result
        elif status == TaskStatus.FAILED:
            error = str(result.result) if result.result else "Unknown error"

        return TaskResult(
            task_id=task_id,
            status=status,
            result=task_result,
            error=error,
        )

    async def cancel_task(self, task_id: str) -> bool:
        """Revoke (cancel) a Celery task."""
        self._app.control.revoke(task_id, terminate=True)
        return True  # Celery revoke is fire-and-forget

    async def wait_for_task(
        self,
        task_id: str,
        timeout: float | None = None,
        poll_interval: float = 0.5,
    ) -> TaskResult:
        """Poll until the task reaches a terminal state or *timeout* expires."""
        start = time.monotonic()
        while True:
            task_result = await self.get_task_status(task_id)
            if task_result.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ):
                return task_result

            if timeout is not None and (time.monotonic() - start) >= timeout:
                raise TimeoutError(
                    f"Task {task_id} did not complete within {timeout}s"
                )

            await asyncio.sleep(poll_interval)

    async def close(self) -> None:
        """No persistent connections to close for Celery."""
        pass
