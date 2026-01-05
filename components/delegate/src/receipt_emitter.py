"""
Receipt Emission with Retry Logic

Ensures receipt emissions don't fail silently.
Failed emissions are queued for retry to maintain audit trail integrity.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional
from collections import deque

import httpx

logger = logging.getLogger(__name__)

# In-memory retry queue (production: use Redis or database)
_retry_queue: deque = deque(maxlen=1000)
_retry_worker_running = False


class ReceiptEmissionError(Exception):
    """Receipt emission failed after retries"""
    pass


async def emit_receipt_with_retry(
    memorygate_url: str,
    tenant_id: str,
    receipt_data: dict,
    max_retries: int = 3,
    timeout: float = 10.0,
) -> str:
    """
    Emit receipt to MemoryGate with retry logic.
    
    Raises ReceiptEmissionError if all retries fail.
    Failed receipts are queued for background retry.
    """
    receipt_id = receipt_data["receipt_id"]
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{memorygate_url}/receipts",
                    json=receipt_data,
                    headers={"X-API-Key": f"dev-key-{tenant_id}"},
                    timeout=timeout,
                )
                response.raise_for_status()
                
            logger.info(
                f"Receipt emitted successfully",
                extra={
                    "receipt_id": receipt_id,
                    "phase": receipt_data["phase"],
                    "task_id": receipt_data["task_id"],
                    "attempt": attempt + 1,
                }
            )
            return receipt_id
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                # Duplicate - already stored, treat as success
                logger.warning(
                    f"Receipt already exists (duplicate)",
                    extra={"receipt_id": receipt_id}
                )
                return receipt_id
            elif e.response.status_code in (400, 422):
                # Validation error - don't retry
                logger.error(
                    f"Receipt validation failed",
                    extra={
                        "receipt_id": receipt_id,
                        "status_code": e.response.status_code,
                        "error": e.response.text,
                    }
                )
                raise ReceiptEmissionError(f"Receipt validation failed: {e.response.text}")
            else:
                logger.warning(
                    f"Receipt emission attempt {attempt + 1} failed",
                    extra={
                        "receipt_id": receipt_id,
                        "status_code": e.response.status_code,
                        "error": str(e),
                    }
                )
                
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(
                f"Receipt emission attempt {attempt + 1} failed (connection)",
                extra={
                    "receipt_id": receipt_id,
                    "error": str(e),
                }
            )
            
        except Exception as e:
            logger.error(
                f"Unexpected error emitting receipt",
                extra={
                    "receipt_id": receipt_id,
                    "error": str(e),
                }
            )
            
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    # All retries failed - queue for background retry
    _queue_for_retry(memorygate_url, tenant_id, receipt_data)
    
    raise ReceiptEmissionError(
        f"Failed to emit receipt {receipt_id} after {max_retries} attempts. Queued for retry."
    )


def _queue_for_retry(memorygate_url: str, tenant_id: str, receipt_data: dict):
    """Queue failed receipt for background retry"""
    _retry_queue.append({
        "memorygate_url": memorygate_url,
        "tenant_id": tenant_id,
        "receipt_data": receipt_data,
        "queued_at": datetime.utcnow().isoformat(),
        "retry_count": 0,
    })
    
    logger.warning(
        f"Receipt queued for background retry",
        extra={
            "receipt_id": receipt_data["receipt_id"],
            "queue_size": len(_retry_queue),
        }
    )


async def retry_worker(interval_seconds: int = 60):
    """
    Background worker that retries failed receipt emissions.
    
    Run this as a background task in the application lifespan.
    """
    global _retry_worker_running
    _retry_worker_running = True
    
    logger.info("Receipt retry worker started")
    
    while _retry_worker_running:
        try:
            await asyncio.sleep(interval_seconds)
            
            if not _retry_queue:
                continue
                
            logger.info(f"Processing {len(_retry_queue)} queued receipts")
            
            # Process up to 10 receipts per cycle
            for _ in range(min(10, len(_retry_queue))):
                if not _retry_queue:
                    break
                    
                item = _retry_queue.popleft()
                item["retry_count"] += 1
                
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{item['memorygate_url']}/receipts",
                            json=item["receipt_data"],
                            headers={"X-API-Key": f"dev-key-{item['tenant_id']}"},
                            timeout=10.0,
                        )
                        response.raise_for_status()
                        
                    logger.info(
                        f"Queued receipt successfully emitted",
                        extra={
                            "receipt_id": item["receipt_data"]["receipt_id"],
                            "retry_count": item["retry_count"],
                        }
                    )
                    
                except Exception as e:
                    if item["retry_count"] < 10:
                        # Re-queue if under max retries
                        _retry_queue.append(item)
                        logger.warning(
                            f"Retry failed, re-queued",
                            extra={
                                "receipt_id": item["receipt_data"]["receipt_id"],
                                "retry_count": item["retry_count"],
                                "error": str(e),
                            }
                        )
                    else:
                        # Give up after 10 retries
                        logger.error(
                            f"Giving up on receipt after 10 retries",
                            extra={
                                "receipt_id": item["receipt_data"]["receipt_id"],
                                "error": str(e),
                            }
                        )
                        
        except Exception as e:
            logger.error(f"Error in retry worker: {e}")


def stop_retry_worker():
    """Stop the retry worker gracefully"""
    global _retry_worker_running
    _retry_worker_running = False
    logger.info("Receipt retry worker stopped")


def get_retry_queue_size() -> int:
    """Get current retry queue size for monitoring"""
    return len(_retry_queue)
