"""
Personalization Orchestrator with GPU Auto-Spin Integration.

Coordinates between the pipeline orchestrator and GPU manager to
automatically scale GPU resources based on personalization workload.
"""

import asyncio
import logging
import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from .gpu_manager import gpu_manager, GPUInstanceType
from .personalization_service import personalization_service
from .pipeline_services.orchestrator import orchestrator
from .pipeline_services.kafka_integration import kafka_manager


logger = logging.getLogger(__name__)


@dataclass
class WorkloadPrediction:
    """Prediction of personalization workload."""
    predicted_tasks: int
    confidence: float
    time_horizon_minutes: int
    recommended_instances: List[GPUInstanceType]
    estimated_cost: float


class PersonalizationOrchestrator:
    """
    Orchestrates personalization workloads with GPU auto-spin.
    
    Monitors queue depth, predicts workload, and automatically
    provisions GPU resources to maintain performance targets.
    """
    
    def __init__(self):
        """Initialize personalization orchestrator."""
        self.running = False
        self.performance_targets = {
            "max_queue_wait_time": 300,  # 5 minutes max wait
            "target_utilization": 0.75,  # 75% target utilization
            "max_cost_per_hour": 25.0,   # Max $25/hour
            "min_throughput": 10          # Min 10 tasks/hour
        }
        
        self.workload_history = []
        self.prediction_model = WorkloadPredictor()
        
        # Integration points
        self.gpu_manager = gpu_manager
        self.personalization_service = personalization_service
        self.pipeline_orchestrator = orchestrator
        
        # Metrics tracking
        self.metrics = {
            "total_tasks_processed": 0,
            "gpu_hours_used": 0.0,
            "total_cost": 0.0,
            "average_wait_time": 0.0,
            "throughput_per_hour": 0.0,
            "cost_per_task": 0.0
        }
    
    async def start(self):
        """Start the personalization orchestrator."""
        self.running = True
        
        # Start dependent services
        await self.personalization_service.start()
        monitoring_task = asyncio.create_task(self.gpu_manager.start_monitoring())
        
        # Start orchestration loop
        orchestration_task = asyncio.create_task(self._orchestration_loop())
        
        logger.info("Personalization Orchestrator started")
        
        try:
            await asyncio.gather(monitoring_task, orchestration_task)
        except asyncio.CancelledError:
            pass
    
    async def stop(self):
        """Stop the personalization orchestrator."""
        self.running = False
        
        # Stop dependent services
        await self.personalization_service.stop()
        await self.gpu_manager.stop_monitoring()
        
        logger.info("Personalization Orchestrator stopped")
    
    async def _orchestration_loop(self):
        """Main orchestration loop."""
        while self.running:
            try:
                # Collect current metrics
                await self._collect_metrics()
                
                # Predict workload
                prediction = await self._predict_workload()
                
                # Make scaling decisions
                await self._make_scaling_decisions(prediction)
                
                # Route personalization tasks
                await self._route_personalization_tasks()
                
                # Update performance tracking
                await self._update_performance_tracking()
                
                # Log status
                await self._log_orchestration_status()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in orchestration loop: {e}")
                await asyncio.sleep(30)
    
    async def _collect_metrics(self):
        """Collect metrics from all services."""
        # Get queue metrics
        queue_size = self.personalization_service.get_queue_size()
        
        # Get GPU manager status
        gpu_status = self.gpu_manager.get_status()
        
        # Get personalization service stats
        service_stats = self.personalization_service.get_stats()
        
        # Store workload history
        self.workload_history.append({
            "timestamp": datetime.utcnow(),
            "queue_size": queue_size,
            "active_instances": gpu_status["active_instances"],
            "processing_tasks": service_stats["engine_stats"]["tasks_processed"],
            "gpu_utilization": service_stats["engine_stats"].get("gpu_utilization", 0.0)
        })
        
        # Keep only last 24 hours of history
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        self.workload_history = [
            h for h in self.workload_history 
            if h["timestamp"] > cutoff_time
        ]
    
    async def _predict_workload(self) -> WorkloadPrediction:
        """Predict future personalization workload."""
        if len(self.workload_history) < 10:
            # Not enough history, use conservative prediction
            current_queue = self.personalization_service.get_queue_size()
            return WorkloadPrediction(
                predicted_tasks=max(current_queue, 20),
                confidence=0.5,
                time_horizon_minutes=60,
                recommended_instances=[GPUInstanceType.LOCAL_GPU],
                estimated_cost=0.0
            )
        
        return await self.prediction_model.predict_workload(self.workload_history)
    
    async def _make_scaling_decisions(self, prediction: WorkloadPrediction):
        """Make GPU scaling decisions based on predictions."""
        current_queue = self.personalization_service.get_queue_size()
        gpu_status = self.gpu_manager.get_status()
        
        # Calculate current processing capacity
        active_instances = gpu_status["active_instances"]
        current_capacity = active_instances * 8  # Assume 8 tasks per instance
        
        # Decision logic
        if prediction.predicted_tasks > current_capacity * 1.5:
            # Need more capacity
            await self._scale_up_recommendation(prediction)
        elif prediction.predicted_tasks < current_capacity * 0.3:
            # Too much capacity
            await self._scale_down_recommendation()
        
        # Emergency scaling for large queues
        if current_queue > 100:
            await self._emergency_scale_up()
    
    async def _scale_up_recommendation(self, prediction: WorkloadPrediction):
        """Recommend scaling up GPU resources."""
        for instance_type in prediction.recommended_instances:
            # Check if we should start this instance type
            if await self._should_start_instance(instance_type, prediction):
                instance_id = await self.gpu_manager.start_gpu_instance(instance_type)
                if instance_id:
                    logger.info(
                        f"Started {instance_type.value} instance {instance_id} "
                        f"for predicted workload of {prediction.predicted_tasks} tasks"
                    )
                break
    
    async def _scale_down_recommendation(self):
        """Recommend scaling down GPU resources."""
        # Find idle instances to stop
        gpu_status = self.gpu_manager.get_status()
        for instance_id, instance_info in gpu_status["instances"].items():
            if (instance_info["current_tasks"] == 0 and 
                instance_info["status"] == "running"):
                await self.gpu_manager.stop_gpu_instance(instance_id)
                logger.info(f"Stopped idle instance {instance_id}")
                break  # Stop one at a time
    
    async def _emergency_scale_up(self):
        """Emergency scaling for very large queues."""
        logger.warning("Emergency scaling triggered for large queue")
        instance_id = await self.gpu_manager.start_gpu_instance(
            GPUInstanceType.AWS_P3_2XLARGE
        )
        if instance_id:
            logger.info(f"Emergency instance {instance_id} started")
    
    async def _should_start_instance(
        self, 
        instance_type: GPUInstanceType, 
        prediction: WorkloadPrediction
    ) -> bool:
        """Determine if we should start a specific instance type."""
        # Check budget constraints
        gpu_status = self.gpu_manager.get_status()
        current_spend = gpu_status["cost_tracking"]["current_spend"]
        daily_budget = gpu_status["cost_tracking"]["daily_budget"]
        
        if current_spend >= daily_budget * 0.9:
            logger.warning("Approaching daily budget limit, skipping scale-up")
            return False
        
        # Check if instance type is cost-effective for prediction
        config = self.gpu_manager.resource_configs[instance_type]
        estimated_runtime = prediction.time_horizon_minutes / 60
        estimated_cost = config.cost_per_hour * estimated_runtime
        
        if estimated_cost > prediction.estimated_cost * 1.2:
            return False  # Too expensive
        
        return True
    
    async def _route_personalization_tasks(self):
        """Route personalization tasks through pipeline."""
        # This integrates with the main pipeline orchestrator
        # to ensure personalization tasks are properly queued
        
        # Check if any workflows need personalization
        active_executions = self.pipeline_orchestrator.list_active_executions()
        
        for execution_id in active_executions:
            execution_status = self.pipeline_orchestrator.get_execution_status(execution_id)
            if execution_status and execution_status["status"] == "running":
                # Check if this execution needs personalization
                stages_completed = execution_status.get("stages_completed", [])
                if "mockup" in stages_completed and "personalization" not in stages_completed:
                    await self._trigger_personalization_stage(execution_id, execution_status)
    
    async def _trigger_personalization_stage(self, execution_id: str, execution_status: Dict[str, Any]):
        """Trigger personalization stage for a workflow execution."""
        try:
            # Get mockup results
            mockup_results = execution_status["stage_results"].get("mockup", {})
            business_data = execution_status["input_data"]
            
            # Submit personalization tasks
            task_types = ["website_mockup_generation", "ai_content_personalization"]
            
            for task_type in task_types:
                task_id = await self.personalization_service.submit_task(
                    task_type,
                    business_data,
                    {"mockup_data": mockup_results},
                    priority=3  # High priority for pipeline tasks
                )
                
                logger.info(f"Submitted {task_type} task {task_id} for execution {execution_id}")
                
        except Exception as e:
            logger.error(f"Failed to trigger personalization for {execution_id}: {e}")
    
    async def _update_performance_tracking(self):
        """Update performance metrics."""
        service_stats = self.personalization_service.get_stats()
        gpu_status = self.gpu_manager.get_status()
        
        # Update metrics
        self.metrics["total_tasks_processed"] = service_stats["engine_stats"]["tasks_processed"]
        self.metrics["total_cost"] = gpu_status["cost_tracking"]["current_spend"]
        
        # Calculate derived metrics
        if self.metrics["total_tasks_processed"] > 0:
            self.metrics["cost_per_task"] = (
                self.metrics["total_cost"] / self.metrics["total_tasks_processed"]
            )
        
        # Calculate throughput (tasks per hour)
        if len(self.workload_history) >= 2:
            recent_history = self.workload_history[-12:]  # Last 6 minutes
            if len(recent_history) >= 2:
                time_diff = (recent_history[-1]["timestamp"] - recent_history[0]["timestamp"]).total_seconds() / 3600
                task_diff = recent_history[-1]["processing_tasks"] - recent_history[0]["processing_tasks"]
                if time_diff > 0:
                    self.metrics["throughput_per_hour"] = task_diff / time_diff
    
    async def _log_orchestration_status(self):
        """Log current orchestration status."""
        queue_size = self.personalization_service.get_queue_size()
        gpu_status = self.gpu_manager.get_status()
        
        logger.info(
            f"Orchestration Status: "
            f"Queue={queue_size}, "
            f"GPU_Instances={gpu_status['active_instances']}, "
            f"Cost=${gpu_status['cost_tracking']['current_spend']:.2f}, "
            f"Throughput={self.metrics['throughput_per_hour']:.1f}/hr"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive orchestration status."""
        return {
            "running": self.running,
            "performance_targets": self.performance_targets,
            "metrics": self.metrics,
            "queue_size": self.personalization_service.get_queue_size(),
            "gpu_status": self.gpu_manager.get_status(),
            "service_stats": self.personalization_service.get_stats(),
            "workload_history_size": len(self.workload_history)
        }


class WorkloadPredictor:
    """Predicts personalization workload based on historical data."""
    
    async def predict_workload(self, history: List[Dict[str, Any]]) -> WorkloadPrediction:
        """Predict future workload based on history."""
        if not history:
            return WorkloadPrediction(
                predicted_tasks=20,
                confidence=0.1,
                time_horizon_minutes=60,
                recommended_instances=[GPUInstanceType.LOCAL_GPU],
                estimated_cost=0.0
            )
        
        # Simple prediction based on recent trends
        recent_queues = [h["queue_size"] for h in history[-10:]]
        recent_processing = [h["processing_tasks"] for h in history[-10:]]
        
        # Calculate trend
        if len(recent_queues) >= 2:
            queue_trend = (recent_queues[-1] - recent_queues[0]) / len(recent_queues)
            processing_trend = (recent_processing[-1] - recent_processing[0]) / len(recent_processing)
        else:
            queue_trend = 0
            processing_trend = 0
        
        # Predict queue size in 1 hour
        current_queue = recent_queues[-1] if recent_queues else 0
        predicted_queue = max(0, current_queue + queue_trend * 12)  # 12 * 5-minute intervals
        
        # Add some buffer for safety
        predicted_tasks = int(predicted_queue * 1.2)
        
        # Recommend instances based on predicted load
        if predicted_tasks > 100:
            recommended_instances = [GPUInstanceType.AWS_P3_2XLARGE]
            estimated_cost = 3.06
        elif predicted_tasks > 50:
            recommended_instances = [GPUInstanceType.AWS_G4DN_2XLARGE]
            estimated_cost = 0.752
        elif predicted_tasks > 20:
            recommended_instances = [GPUInstanceType.AWS_G4DN_XLARGE]
            estimated_cost = 0.526
        else:
            recommended_instances = [GPUInstanceType.LOCAL_GPU]
            estimated_cost = 0.0
        
        confidence = min(0.9, len(history) / 100.0)  # Higher confidence with more data
        
        return WorkloadPrediction(
            predicted_tasks=predicted_tasks,
            confidence=confidence,
            time_horizon_minutes=60,
            recommended_instances=recommended_instances,
            estimated_cost=estimated_cost
        )


# Global instance
personalization_orchestrator = PersonalizationOrchestrator()


async def main():
    """Example usage of personalization orchestrator."""
    try:
        await personalization_orchestrator.start()
    except KeyboardInterrupt:
        await personalization_orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())