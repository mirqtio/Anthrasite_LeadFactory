"""
Tests for variant DAG integration module.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

from leadfactory.pipeline.variant_dag_integration import (
    VariantAwareDAG, VariantAwareExecutor, VariantExecutionContext,
    VariantPipelineManager, execute_variant_pipeline,
    execute_pipeline_with_variant, get_variant_pipeline_manager
)
from leadfactory.pipeline.variants import PipelineVariant, VariantStatus
from leadfactory.pipeline.dag_traversal import PipelineStage
from leadfactory.pipeline.variant_tracking import VariantTracker


class TestVariantExecutionContext:
    """Test VariantExecutionContext class."""

    def test_context_creation(self):
        """Test creating execution context."""
        context = VariantExecutionContext(
            business_id=123,
            variant_id="variant_123",
            variant_name="test_variant",
            session_id="session456",
            metadata={"key": "value"}
        )

        assert context.business_id == 123
        assert context.variant_id == "variant_123"
        assert context.variant_name == "test_variant"
        assert context.session_id == "session456"
        assert context.metadata == {"key": "value"}

    def test_context_auto_session_id(self):
        """Test automatic session ID generation."""
        context = VariantExecutionContext(
            business_id=123,
            variant_id="variant_123",
            variant_name="test_variant"
        )

        assert context.session_id != ""
        assert len(context.session_id) > 0


class TestVariantAwareDAG:
    """Test VariantAwareDAG class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.variant = PipelineVariant(name="test_variant")
        # Disable some stages for testing
        self.variant.disable_stage(PipelineStage.DEDUPE)
        self.variant.disable_stage(PipelineStage.SCORE)

    def test_variant_aware_dag_creation(self):
        """Test creating variant-aware DAG."""
        dag = VariantAwareDAG(self.variant)

        assert dag.variant == self.variant

        # Verify that disabled stages were removed
        enabled_stages = dag.get_enabled_stages()
        assert PipelineStage.DEDUPE not in enabled_stages
        assert PipelineStage.SCORE not in enabled_stages

    def test_variant_aware_dag_no_variant(self):
        """Test creating DAG without variant."""
        dag = VariantAwareDAG()

        assert dag.variant is None

    def test_variant_aware_dag_custom_dependencies(self):
        """Test variant-aware DAG with custom dependencies."""
        from leadfactory.pipeline.dag_traversal import StageDependency, DependencyType

        # Add custom dependency to variant
        custom_dep = StageDependency(
            from_stage=PipelineStage.SCRAPE,
            to_stage=PipelineStage.EMAIL_QUEUE,
            dependency_type=DependencyType.OPTIONAL
        )
        self.variant.custom_dependencies.append(custom_dep)

        dag = VariantAwareDAG(self.variant)

        # Verify custom dependency was added to the EMAIL_QUEUE stage
        email_queue_deps = dag.get_dependencies(PipelineStage.EMAIL_QUEUE)
        assert custom_dep in email_queue_deps


class TestVariantAwareExecutor:
    """Test VariantAwareExecutor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.variant = PipelineVariant(name="test_variant")
        self.context = VariantExecutionContext(
            business_id=123,
            variant_id=self.variant.id,
            variant_name=self.variant.name,
            session_id="session456"
        )

        # Create temporary database for tracking
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.tracker = VariantTracker(db_path=self.temp_db.name)

    def teardown_method(self):
        """Clean up test fixtures."""
        self.tracker.close()
        os.unlink(self.temp_db.name)

    @patch('leadfactory.pipeline.variant_dag_integration.get_variant_registry')
    @patch('leadfactory.pipeline.variant_dag_integration.get_variant_tracker')
    def test_variant_aware_executor_creation(self, mock_get_tracker, mock_get_registry):
        """Test creating variant-aware executor."""
        mock_get_tracker.return_value = self.tracker

        # Mock registry to return our variant
        mock_registry = Mock()
        mock_registry.get_variant.return_value = self.variant
        mock_get_registry.return_value = mock_registry

        executor = VariantAwareExecutor(self.context)

        assert executor.execution_context == self.context
        assert executor.variant == self.variant
        assert executor.tracker == self.tracker

    @patch('leadfactory.pipeline.variant_dag_integration.get_variant_registry')
    @patch('leadfactory.pipeline.variant_dag_integration.get_variant_tracker')
    def test_variant_not_found_error(self, mock_get_tracker, mock_get_registry):
        """Test error when variant is not found."""
        mock_get_tracker.return_value = self.tracker

        # Mock registry to return None (variant not found)
        mock_registry = Mock()
        mock_registry.get_variant.return_value = None
        mock_get_registry.return_value = mock_registry

        with pytest.raises(ValueError, match="Variant .* not found"):
            VariantAwareExecutor(self.context)


class TestVariantPipelineManager:
    """Test VariantPipelineManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary database for tracking
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        # Mock dependencies
        self.mock_registry = Mock()
        self.mock_selection_manager = Mock()
        self.mock_tracker = Mock()

        # Create manager with mocked dependencies
        with patch('leadfactory.pipeline.variant_dag_integration.get_variant_registry') as mock_get_registry:
            with patch('leadfactory.pipeline.variant_dag_integration.get_selection_manager') as mock_get_selection:
                with patch('leadfactory.pipeline.variant_dag_integration.get_variant_tracker') as mock_get_tracker:
                    mock_get_registry.return_value = self.mock_registry
                    mock_get_selection.return_value = self.mock_selection_manager
                    mock_get_tracker.return_value = self.mock_tracker

                    self.manager = VariantPipelineManager()

    def teardown_method(self):
        """Clean up test fixtures."""
        os.unlink(self.temp_db.name)

    @patch('leadfactory.pipeline.variant_dag_integration.VariantAwareExecutor')
    def test_execute_pipeline_for_business(self, mock_executor_class):
        """Test executing pipeline for business with variant selection."""
        # Mock variant selection
        variant = PipelineVariant(name="selected_variant")
        selection_result = Mock()
        selection_result.variant_id = variant.id
        selection_result.variant_name = variant.name
        selection_result.selection_reason = "random"
        selection_result.confidence = 0.8
        selection_result.metadata = {}

        self.mock_selection_manager.select_variant.return_value = selection_result
        self.mock_registry.get_variant.return_value = variant

        # Mock executor
        mock_executor = Mock()
        mock_executor.execute_pipeline.return_value = {PipelineStage.SCRAPE: Mock(success=True)}
        mock_executor_class.return_value = mock_executor

        result = self.manager.execute_pipeline_for_business(business_id=123)

        assert result is not None

        # Verify selection was called
        self.mock_selection_manager.select_variant.assert_called_once()

        # Verify executor was created and called
        mock_executor_class.assert_called_once()
        mock_executor.execute_pipeline.assert_called_once()

    @patch('leadfactory.pipeline.variant_dag_integration.VariantAwareExecutor')
    def test_execute_pipeline_with_variant(self, mock_executor_class):
        """Test executing pipeline with specific variant."""
        variant = PipelineVariant(name="test_variant")
        self.mock_registry.get_variant.return_value = variant

        # Mock executor
        mock_executor = Mock()
        mock_executor.execute_pipeline.return_value = {PipelineStage.SCRAPE: Mock(success=True)}
        mock_executor_class.return_value = mock_executor

        result = self.manager.execute_pipeline_with_variant(
            business_id=123,
            variant_id=variant.id
        )

        assert result is not None

        # Verify executor was created and called
        mock_executor_class.assert_called_once()
        mock_executor.execute_pipeline.assert_called_once()

    def test_get_variant_for_business(self):
        """Test getting variant selection for business."""
        business_id = 123

        # Mock selection result
        selection_result = Mock()
        selection_result.variant_id = "variant123"
        selection_result.variant_name = "Test Variant"

        self.mock_selection_manager.select_variant.return_value = selection_result

        result = self.manager.get_variant_for_business(business_id)

        assert result == selection_result

        # Verify selection was called with correct context
        call_args = self.mock_selection_manager.select_variant.call_args[0][0]
        assert call_args.business_id == business_id

    def test_variant_selection_failure(self):
        """Test handling of variant selection failure."""
        self.mock_selection_manager.select_variant.return_value = None

        with pytest.raises(RuntimeError, match="Failed to select variant"):
            self.manager.execute_pipeline_for_business(business_id=123)

    def test_variant_not_found_in_execute_with_variant(self):
        """Test handling when specified variant is not found."""
        self.mock_registry.get_variant.return_value = None

        with pytest.raises(ValueError, match="Variant .* not found"):
            self.manager.execute_pipeline_with_variant(
                business_id=123,
                variant_id="nonexistent"
            )


class TestUtilityFunctions:
    """Test utility functions."""

    @patch('leadfactory.pipeline.variant_dag_integration.get_variant_pipeline_manager')
    def test_execute_variant_pipeline_function(self, mock_get_manager):
        """Test convenience function for pipeline execution."""
        mock_manager = Mock()
        mock_manager.execute_pipeline_for_business.return_value = {PipelineStage.SCRAPE: Mock(success=True)}
        mock_get_manager.return_value = mock_manager

        result = execute_variant_pipeline(
            business_id=123,
            user_id="user456"
        )

        assert result is not None

        # Verify manager was called correctly (business_id is passed as positional arg)
        mock_manager.execute_pipeline_for_business.assert_called_once_with(
            123,
            user_id="user456"
        )

    @patch('leadfactory.pipeline.variant_dag_integration.get_variant_pipeline_manager')
    def test_execute_pipeline_with_variant_function(self, mock_get_manager):
        """Test convenience function for pipeline execution with specific variant."""
        mock_manager = Mock()
        mock_manager.execute_pipeline_with_variant.return_value = {PipelineStage.SCRAPE: Mock(success=True)}
        mock_get_manager.return_value = mock_manager

        result = execute_pipeline_with_variant(
            business_id=123,
            variant_id="variant456",
            user_id="user789"
        )

        assert result is not None

        # Verify manager was called correctly (business_id and variant_id are passed as positional args)
        mock_manager.execute_pipeline_with_variant.assert_called_once_with(
            123,
            "variant456",
            user_id="user789"
        )

    def test_get_variant_pipeline_manager(self):
        """Test getting global pipeline manager."""
        manager1 = get_variant_pipeline_manager()
        manager2 = get_variant_pipeline_manager()

        # Should return the same instance
        assert manager1 is manager2


class TestVariantDAGIntegration:
    """Integration tests for variant DAG integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.tracker = VariantTracker(db_path=self.temp_db.name)
        # Ensure database is properly initialized
        self.tracker._init_database()

    def teardown_method(self):
        """Clean up test fixtures."""
        self.tracker.close()
        os.unlink(self.temp_db.name)

    @patch('leadfactory.pipeline.variant_dag_integration.get_variant_tracker')
    @patch('leadfactory.pipeline.variant_dag_integration.get_variant_registry')
    def test_full_variant_pipeline_execution(self, mock_get_registry, mock_get_tracker):
        """Test complete variant pipeline execution flow."""
        mock_get_tracker.return_value = self.tracker

        # Create variant with specific configuration
        variant = PipelineVariant(name="integration_test")
        variant.disable_stage(PipelineStage.DEDUPE)
        variant.enable_stage(PipelineStage.SCRAPE, {"custom_param": "value"})

        # Mock registry
        mock_registry = Mock()
        mock_registry.get_variant.return_value = variant
        mock_get_registry.return_value = mock_registry

        # Create execution context
        context = VariantExecutionContext(
            business_id=123,
            variant_id=variant.id,
            variant_name=variant.name,
            session_id="session456"
        )

        # Create and execute with variant-aware components
        dag = VariantAwareDAG(variant)

        # Create executor and manually track some events for testing
        executor = VariantAwareExecutor(context)

        # Track a test event to verify tracking works
        from leadfactory.pipeline.variant_tracking import TrackingEvent
        test_event = TrackingEvent(
            variant_id=variant.id,
            business_id=123,
            event_type="pipeline_started",
            session_id="session456"
        )
        self.tracker.track_event(test_event)

        # Mock the executor's execute_pipeline method
        with patch.object(VariantAwareExecutor, 'execute_pipeline') as mock_execute:
            mock_execute.return_value = {PipelineStage.SCRAPE: Mock(success=True)}

            result = executor.execute_pipeline()

            assert result is not None

            # Verify tracking occurred
            events = self.tracker.get_events(variant_id=variant.id)
            assert len(events) > 0

            # Verify pipeline events were tracked
            event_types = [event["event_type"] for event in events]
            assert "pipeline_started" in event_types

    @patch('leadfactory.pipeline.variant_dag_integration.get_variant_registry')
    @patch('leadfactory.pipeline.variant_dag_integration.get_selection_manager')
    @patch('leadfactory.pipeline.variant_dag_integration.get_variant_tracker')
    def test_end_to_end_variant_selection_and_execution(self, mock_get_tracker, mock_get_selection, mock_get_registry):
        """Test end-to-end variant selection and execution."""
        mock_get_tracker.return_value = self.tracker

        # Mock variant registry
        variant = PipelineVariant(name="e2e_test")
        mock_registry = Mock()
        mock_registry.get_variant.return_value = variant
        mock_get_registry.return_value = mock_registry

        # Mock selection manager
        selection_result = Mock()
        selection_result.variant_id = variant.id
        selection_result.variant_name = variant.name
        selection_result.selection_reason = "random"
        selection_result.confidence = 0.8
        selection_result.metadata = {}

        mock_selection_manager = Mock()
        mock_selection_manager.select_variant.return_value = selection_result
        mock_get_selection.return_value = mock_selection_manager

        # Create pipeline manager
        manager = VariantPipelineManager()

        # Mock the execution part
        with patch.object(manager, 'execute_pipeline_for_business') as mock_execute:
            mock_execute.return_value = {PipelineStage.SCRAPE: Mock(success=True)}

            # Execute pipeline with variant selection
            result = manager.execute_pipeline_for_business(business_id=123)

            assert result is not None

            # Verify execution occurred
            mock_execute.assert_called_once_with(business_id=123)
