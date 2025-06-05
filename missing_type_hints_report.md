# Missing Return Type Annotations Report

This report lists functions in the leadfactory codebase that are missing return type annotations (`-> Type`). These are non-test files and exclude `__init__` methods.

## Critical Functions by Module

### Storage Module (`leadfactory/storage/`)
- **postgres_storage.py**
  - `connection(self):` (line 51) - Context manager, should be `-> Generator`
  - `cursor(self):` (line 57) - Context manager, should be `-> Generator`

- **interface.py**
  - `connection(self):` (line 23) - Abstract method
  - `cursor(self):` (line 34) - Abstract method

- **factory.py**
  - `reset_storage_instance():` (line 72) - Should be `-> None`

- **query_optimizer.py**
  - `connection(self):` (line 29) - Property
  - `track_query_performance(self, query_name: str):` (line 260) - Decorator
  - `vacuum_analyze_tables(self, tables: Optional[list[str]] = None):` (line 311)
  - `create_optimized_indexes(connection_string: str):` (line 410)

- **sharded_postgres_storage.py**
  - `close_all_pools(self):` (line 86)
  - `get_connection(self, shard_id: Optional[str] = None):`

### API Module (`leadfactory/api/`)
- **logs_api.py**
  - `init_app(self, app: Flask):` (line 85)
  - `health_check():` (line 949)
  - `index():` (line 956)

- **cache_manager.py**
  - `cache_api_response(ttl: int = 60):` (line 329) - Decorator
  - `cache_business_data(ttl: int = 3600):` (line 335) - Decorator
  - `cache_report(ttl: int = 7200):` (line 341) - Decorator

- **cache.py**
  - `clear(self):` (line 157)
  - `invalidate_pattern(self, pattern: str):` (line 250)
  - `clear_cache():` (line 294)

### Email Module (`leadfactory/email/`)
- **sendgrid_throttling.py**
  - `record_send_success(self, batch: EmailBatch, sent_count: int):` (line 590)
  - `record_send_failure(self, batch: EmailBatch, error: str):` (line 641)
  - `pause_throttling(self, reason: str = "Manual pause"):` (line 714)
  - `resume_throttling(self, reason: str = "Manual resume"):` (line 720)

- **sendgrid_warmup_dashboard.py**
  - `update_prometheus_metrics(self):` (line 356)
  - `create_warmup_dashboard(warmup_scheduler=None, integration_service=None):` (line 487)

- **sendgrid_warmup_metrics.py**
  - `record_warmup_started(self, ip_address: str):` (line 136)
  - `record_warmup_completed(self, ip_address: str, duration_days: int):` (line 142)
  - `record_warmup_paused(self, ip_address: str, reason: str):` (line 152)
  - `record_warmup_resumed(self, ip_address: str):` (line 158)

### Pipeline Module (`leadfactory/pipeline/`)
- **dag_traversal.py**
  - `add_dependency(self, dependency: StageDependency):` (line 148)
  - `remove_dependency(self, from_stage: PipelineStage, to_stage: PipelineStage):` (line 153)
  - `mark_stage_completed(self, stage: PipelineStage, result: StageResult):` (line 420)
  - `mark_stage_failed(self, stage: PipelineStage, error: str):` (line 426)
  - `reset(self):` (line 450)

- **data_preservation.py**
  - `with_data_preservation(operation_type: str):` (line 299) - Decorator factory

- **dedupe.py** & **dedupe_legacy_wrapper.py**
  - Multiple database connection mock methods
  - `merge_businesses(business1, business2, is_dry_run: bool = False):`
  - `get_potential_duplicates(limit: Optional[int] = None):`
  - `calculate_completeness_score(business: dict):`

- **email_queue.py**
  - `load_sendgrid_config():` - Configuration loader

- **retry_mechanisms.py**
  - `record_success(self):`
  - `record_failure(self):`
  - Decorator functions

### Services Module (`leadfactory/services/`)
- **gpu_manager.py**
  - `async start_monitoring(self):` (line 362)
  - `async stop_monitoring(self):` (line 393)
  - `async stop_gpu_instance(self, instance_id: str):` (line 903)
  - `async main():` (line 1143)

- **ip_pool_manager.py**
  - `async start_monitoring(self):` (line 176)
  - `async stop_monitoring(self):` (line 207)
  - `async main():` (line 609)

- **bounce_monitor.py**
  - `SQLiteDatabaseConnection(db_path: str = None):` (line 23) - Context manager

- **pdf_generator.py**
  - Multiple methods for PDF generation and manipulation

- **report_template_engine.py**
  - Template filter functions

### Cost Module (`leadfactory/cost/`)
- **budget_config.py**
  - `set_enabled(self, enabled: bool, persist: bool = True):` (line 561)
  - `import_configuration(self, config_data: dict[str, Any], persist: bool = True):` (line 659)
  - `reset_budget_config():` (line 744)

- **budget_alerting.py**
  - `reset_notification_service():` (line 633)

- **budget_decorators.py**
  - Multiple decorator functions for budget checking
  - `extract_openai_parameters(*args, **kwargs):` (line 128)

- **gpt_usage_tracker.py**
  - Decorator functions for tracking GPT usage

### Monitoring Module (`leadfactory/monitoring/`)
- **alert_manager.py**
  - `add_alert_rule(self, rule: AlertRule):` (line 388)
  - `remove_alert_rule(self, rule_name: str):` (line 397)
  - `add_notification_channel(self, channel: NotificationChannel):` (line 407)
  - `check_alerts(self):` (line 416)

- **bounce_rate_monitor.py**
  - `async start(self):` (line 76)
  - `async stop(self):` (line 88)
  - `async stop_automated_monitoring():` (line 426)

- **conversion_tracking.py**
  - `cleanup_old_data(self, retention_days: int = 90):` (line 675)

- **dashboard.py**
  - Multiple Flask route handlers

### Scoring Module (`leadfactory/scoring/`)
- **rule_converter.py**
  - `main():` (line 358)

- **simplified_yaml_parser.py**
  - `validate_score(cls, v, info):` (line 79) - Pydantic validator

- **yaml_parser.py**
  - Multiple Pydantic validators

### Middleware Module (`leadfactory/middleware/`)
- **budget_middleware.py**
  - `create_express_budget_middleware(config: Optional[MiddlewareConfig] = None):`
  - `create_fastapi_budget_middleware(config: Optional[MiddlewareConfig] = None):`
  - `create_flask_budget_middleware(config: Optional[MiddlewareConfig] = None):`

## Priority Functions to Fix

1. **Storage Interface Methods** - These are core to the application
2. **API Route Handlers** - Public-facing functions should have clear return types
3. **Async Service Methods** - Important for understanding coroutine behavior
4. **Decorator Functions** - Should specify they return decorators/callables
5. **Context Managers** - Should specify Generator return types

## Recommendations

1. Start with the storage module as it's fundamental to the application
2. Add return type hints to all public API methods
3. Ensure all async functions have proper return type annotations
4. Update decorator functions to show they return Callable types
5. Add return type hints to context managers (typically `-> Generator`)
