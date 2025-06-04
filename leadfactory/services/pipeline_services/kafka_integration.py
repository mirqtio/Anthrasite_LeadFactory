"""
Kafka integration for async pipeline processing.

Provides message queue functionality for distributed processing,
event streaming, and workflow coordination.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
import uuid

try:
    from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
    from aiokafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False


logger = logging.getLogger(__name__)


@dataclass
class PipelineMessage:
    """Message structure for pipeline processing."""
    message_id: str
    task_type: str  # scrape, enrich, dedupe, score, mockup, email
    payload: Dict[str, Any]
    priority: int = 5
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = None
    processing_deadline: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())


class KafkaManager:
    """
    Manages Kafka producers and consumers for pipeline processing.
    
    Provides high-level interfaces for publishing pipeline tasks
    and consuming them for distributed processing.
    """
    
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        """Initialize Kafka manager."""
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.consumers = {}
        self.topic_handlers = {}
        self.running = False
        
        # Pipeline topics configuration
        self.topics = {
            "scrape.requests": {"partitions": 4, "replication": 1},
            "enrich.requests": {"partitions": 8, "replication": 1},
            "dedupe.requests": {"partitions": 2, "replication": 1},
            "score.requests": {"partitions": 4, "replication": 1},
            "mockup.requests": {"partitions": 4, "replication": 1},
            "email.requests": {"partitions": 4, "replication": 1},
            "pipeline.events": {"partitions": 2, "replication": 1},
            "pipeline.errors": {"partitions": 1, "replication": 1}
        }
        
        if not KAFKA_AVAILABLE:
            logger.warning("aiokafka not available, using mock implementation")
    
    async def start(self):
        """Start Kafka connections."""
        if not KAFKA_AVAILABLE:
            logger.info("Kafka mock mode - no actual connections")
            self.running = True
            return
        
        try:
            # Initialize producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                compression_type="gzip",
                acks='all',
                retries=3
            )
            await self.producer.start()
            
            self.running = True
            logger.info("Kafka manager started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Kafka manager: {e}")
            raise
    
    async def stop(self):
        """Stop Kafka connections."""
        if not KAFKA_AVAILABLE:
            self.running = False
            return
        
        self.running = False
        
        # Stop all consumers
        for consumer in self.consumers.values():
            await consumer.stop()
        
        # Stop producer
        if self.producer:
            await self.producer.stop()
        
        logger.info("Kafka manager stopped")
    
    async def publish_task(
        self, 
        task_type: str, 
        payload: Dict[str, Any],
        priority: int = 5,
        max_retries: int = 3
    ) -> str:
        """
        Publish a pipeline task to the appropriate topic.
        
        Args:
            task_type: Type of task (scrape, enrich, etc.)
            payload: Task data
            priority: Priority level (1-10, lower is higher priority)
            max_retries: Maximum retry attempts
            
        Returns:
            Message ID
        """
        topic = f"{task_type}.requests"
        
        message = PipelineMessage(
            message_id=str(uuid.uuid4()),
            task_type=task_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries
        )
        
        if KAFKA_AVAILABLE and self.producer and self.running:
            try:
                # Use priority as partition key for load balancing
                partition_key = str(priority).encode('utf-8')
                
                await self.producer.send_and_wait(
                    topic,
                    value=asdict(message),
                    key=partition_key
                )
                
                logger.debug(f"Published task {message.message_id} to {topic}")
                
            except KafkaError as e:
                logger.error(f"Failed to publish task to {topic}: {e}")
                raise
        else:
            # Mock mode - just log
            logger.info(f"Mock publish: {task_type} task {message.message_id}")
        
        return message.message_id
    
    async def subscribe_to_tasks(
        self,
        task_types: List[str],
        handler: Callable[[PipelineMessage], Any],
        consumer_group: str = "pipeline_workers"
    ):
        """
        Subscribe to pipeline tasks and process them with a handler.
        
        Args:
            task_types: List of task types to consume
            handler: Async function to process messages
            consumer_group: Kafka consumer group ID
        """
        if not KAFKA_AVAILABLE:
            logger.info(f"Mock subscription to {task_types}")
            return
        
        topics = [f"{task_type}.requests" for task_type in task_types]
        
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=consumer_group,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            enable_auto_commit=False
        )
        
        try:
            await consumer.start()
            self.consumers[consumer_group] = consumer
            
            logger.info(f"Started consumer {consumer_group} for topics: {topics}")
            
            # Process messages
            async for message in consumer:
                if not self.running:
                    break
                
                try:
                    # Parse message
                    pipeline_message = PipelineMessage(**message.value)
                    
                    # Process with handler
                    await handler(pipeline_message)
                    
                    # Commit offset on success
                    await consumer.commit()
                    
                    logger.debug(f"Processed message {pipeline_message.message_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
                    # Handle retry logic
                    if pipeline_message.retry_count < pipeline_message.max_retries:
                        pipeline_message.retry_count += 1
                        await self.publish_retry(pipeline_message)
                    else:
                        await self.publish_error(pipeline_message, str(e))
                    
                    # Commit to move past the failed message
                    await consumer.commit()
        
        except Exception as e:
            logger.error(f"Consumer {consumer_group} error: {e}")
        finally:
            await consumer.stop()
    
    async def publish_retry(self, message: PipelineMessage):
        """Publish a message for retry."""
        topic = f"{message.task_type}.requests"
        
        if KAFKA_AVAILABLE and self.producer:
            await self.producer.send_and_wait(
                topic,
                value=asdict(message),
                key=str(message.priority).encode('utf-8')
            )
        
        logger.info(f"Retrying message {message.message_id} (attempt {message.retry_count})")
    
    async def publish_error(self, message: PipelineMessage, error: str):
        """Publish a message to the error topic."""
        error_data = {
            "original_message": asdict(message),
            "error": error,
            "failed_at": datetime.utcnow().isoformat()
        }
        
        if KAFKA_AVAILABLE and self.producer:
            await self.producer.send_and_wait(
                "pipeline.errors",
                value=error_data
            )
        
        logger.error(f"Message {message.message_id} failed permanently: {error}")
    
    async def publish_event(self, event_type: str, data: Dict[str, Any]):
        """Publish a pipeline event for monitoring/analytics."""
        event_data = {
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "event_id": str(uuid.uuid4())
        }
        
        if KAFKA_AVAILABLE and self.producer:
            await self.producer.send_and_wait(
                "pipeline.events",
                value=event_data
            )
        
        logger.debug(f"Published event: {event_type}")


class WorkflowManager:
    """
    Manages async workflow execution using Kafka.
    
    Orchestrates pipeline workflows by publishing tasks to appropriate
    queues and coordinating the execution flow.
    """
    
    def __init__(self, kafka_manager: KafkaManager):
        """Initialize workflow manager."""
        self.kafka = kafka_manager
        self.active_workflows = {}
    
    async def start_workflow(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        stages: List[str] = None
    ) -> str:
        """
        Start an async workflow execution.
        
        Args:
            workflow_id: Unique workflow identifier
            input_data: Initial workflow data
            stages: Pipeline stages to execute
            
        Returns:
            Workflow execution ID
        """
        if stages is None:
            stages = ["scrape", "enrich", "dedupe", "score", "mockup", "email"]
        
        execution_id = f"{workflow_id}_{datetime.utcnow().isoformat()}"
        
        workflow_context = {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "stages": stages,
            "current_stage": 0,
            "input_data": input_data,
            "stage_results": {},
            "status": "running",
            "created_at": datetime.utcnow()
        }
        
        self.active_workflows[execution_id] = workflow_context
        
        # Start with first stage
        await self._execute_next_stage(execution_id)
        
        # Publish workflow started event
        await self.kafka.publish_event("workflow.started", {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "stages": stages
        })
        
        return execution_id
    
    async def _execute_next_stage(self, execution_id: str):
        """Execute the next stage in the workflow."""
        workflow = self.active_workflows.get(execution_id)
        if not workflow:
            return
        
        stage_index = workflow["current_stage"]
        if stage_index >= len(workflow["stages"]):
            # Workflow complete
            await self._complete_workflow(execution_id)
            return
        
        stage_name = workflow["stages"][stage_index]
        
        # Prepare task payload
        task_payload = {
            "execution_id": execution_id,
            "stage_name": stage_name,
            "input_data": workflow["input_data"],
            "previous_results": workflow["stage_results"]
        }
        
        # Publish task
        message_id = await self.kafka.publish_task(
            stage_name,
            task_payload,
            priority=3  # Workflow tasks get higher priority
        )
        
        logger.info(f"Started stage {stage_name} for workflow {execution_id}")
    
    async def handle_stage_completion(self, message: PipelineMessage, result: Dict[str, Any]):
        """Handle completion of a workflow stage."""
        payload = message.payload
        execution_id = payload.get("execution_id")
        stage_name = payload.get("stage_name")
        
        if execution_id not in self.active_workflows:
            logger.warning(f"Unknown workflow execution: {execution_id}")
            return
        
        workflow = self.active_workflows[execution_id]
        
        # Store stage result
        workflow["stage_results"][stage_name] = result
        workflow["current_stage"] += 1
        
        # Publish stage completion event
        await self.kafka.publish_event("stage.completed", {
            "execution_id": execution_id,
            "stage_name": stage_name,
            "result_summary": {
                "success": True,
                "items_processed": result.get("items_processed", 0)
            }
        })
        
        # Execute next stage
        await self._execute_next_stage(execution_id)
    
    async def _complete_workflow(self, execution_id: str):
        """Complete a workflow execution."""
        workflow = self.active_workflows.get(execution_id)
        if not workflow:
            return
        
        workflow["status"] = "completed"
        workflow["completed_at"] = datetime.utcnow()
        
        # Publish completion event
        await self.kafka.publish_event("workflow.completed", {
            "execution_id": execution_id,
            "workflow_id": workflow["workflow_id"],
            "stages_completed": len(workflow["stage_results"]),
            "total_processing_time": (
                workflow["completed_at"] - workflow["created_at"]
            ).total_seconds()
        })
        
        logger.info(f"Workflow {execution_id} completed successfully")


# Global instances
kafka_manager = KafkaManager()
workflow_manager = WorkflowManager(kafka_manager)


async def example_task_handler(message: PipelineMessage):
    """Example task handler for demonstration."""
    logger.info(f"Processing {message.task_type} task {message.message_id}")
    
    # Simulate processing
    await asyncio.sleep(1)
    
    # Simulate success
    result = {
        "items_processed": 10,
        "processing_time": 1.0,
        "success": True
    }
    
    # Handle workflow stage completion
    if "execution_id" in message.payload:
        await workflow_manager.handle_stage_completion(message, result)


async def main():
    """Example usage of Kafka integration."""
    try:
        # Start Kafka manager
        await kafka_manager.start()
        
        # Start a consumer for demonstration
        consumer_task = asyncio.create_task(
            kafka_manager.subscribe_to_tasks(
                ["scrape", "enrich"],
                example_task_handler,
                "demo_workers"
            )
        )
        
        # Start a workflow
        execution_id = await workflow_manager.start_workflow(
            "demo_workflow",
            {"zip_codes": ["10002"], "verticals": ["hvac"]},
            ["scrape", "enrich"]
        )
        
        print(f"Started workflow: {execution_id}")
        
        # Wait a bit for demonstration
        await asyncio.sleep(5)
        
        consumer_task.cancel()
        
    finally:
        await kafka_manager.stop()


if __name__ == "__main__":
    asyncio.run(main())