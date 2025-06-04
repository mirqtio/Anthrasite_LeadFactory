"""
Long-term Test Analytics and Prediction System.

Implements machine learning models to predict test instabilities,
correlation analysis, and comprehensive reporting for CI pipeline health.
Part of Task 14: CI Pipeline Test Monitoring and Governance Framework.
"""

import json
import logging
import sqlite3
import statistics
import threading
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Optional ML dependencies with fallbacks
try:
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from .test_monitoring import TestExecution, TestMetrics, metrics_collector

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Result of test instability prediction."""

    test_id: str
    test_name: str
    test_suite: str
    instability_probability: float
    risk_level: str  # "low", "medium", "high", "critical"
    contributing_factors: List[str]
    confidence: float
    prediction_date: datetime


@dataclass
class CorrelationAnalysis:
    """Result of correlation analysis between code changes and test failures."""

    analysis_id: str
    time_period: Tuple[datetime, datetime]
    commit_hash: str
    files_changed: List[str]
    affected_tests: List[str]
    correlation_strength: float  # 0.0 to 1.0
    failure_pattern: str
    analysis_date: datetime


@dataclass
class TrendAnalysis:
    """Trend analysis for test performance over time."""

    test_id: str
    test_name: str
    analysis_period: Tuple[datetime, datetime]
    trend_direction: str  # "improving", "stable", "degrading", "volatile"
    trend_strength: float  # 0.0 to 1.0
    seasonal_patterns: List[str]
    anomalies_detected: List[datetime]
    forecast_next_week: Dict[str, float]


class TestAnalyticsEngine:
    """Advanced analytics engine for test performance prediction and analysis."""

    def __init__(self, db_path: str = "test_analytics.db"):
        self.db_path = db_path
        self.prediction_models: Dict[str, Any] = {}
        self.anomaly_detectors: Dict[str, Any] = {}
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self._lock = threading.Lock()

        self._init_analytics_database()
        if SKLEARN_AVAILABLE:
            self._train_initial_models()
        else:
            logger.warning("Scikit-learn not available, using simplified analytics")

    def _init_analytics_database(self):
        """Initialize analytics database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prediction_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id TEXT NOT NULL,
                    test_name TEXT NOT NULL,
                    test_suite TEXT NOT NULL,
                    instability_probability REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    contributing_factors TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    prediction_date TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS correlation_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id TEXT NOT NULL,
                    commit_hash TEXT NOT NULL,
                    files_changed TEXT NOT NULL,
                    affected_tests TEXT NOT NULL,
                    correlation_strength REAL NOT NULL,
                    failure_pattern TEXT NOT NULL,
                    analysis_date TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trend_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id TEXT NOT NULL,
                    test_name TEXT NOT NULL,
                    trend_direction TEXT NOT NULL,
                    trend_strength REAL NOT NULL,
                    seasonal_patterns TEXT,
                    anomalies_detected TEXT,
                    forecast_data TEXT,
                    analysis_date TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS weekly_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_start TEXT NOT NULL,
                    week_end TEXT NOT NULL,
                    report_data TEXT NOT NULL,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

    def _train_initial_models(self):
        """Train initial prediction models using historical data."""
        if not SKLEARN_AVAILABLE:
            return

        logger.info("Training initial prediction models...")

        # Get historical test data
        historical_data = self._prepare_training_data()

        if len(historical_data) < 100:  # Not enough data for meaningful training
            logger.info("Insufficient historical data for model training")
            return

        # Train instability prediction model
        try:
            X, y = self._create_feature_matrix(historical_data)

            if len(X) > 0:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42
                )

                # Train Random Forest for instability prediction
                rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
                rf_model.fit(X_train, y_train)

                # Evaluate model
                y_pred = rf_model.predict(X_test)
                accuracy = accuracy_score(y_test, y_pred)

                self.prediction_models["instability"] = rf_model
                logger.info(
                    f"Instability prediction model trained with {accuracy:.2f} accuracy"
                )

                # Train anomaly detection model
                anomaly_model = IsolationForest(contamination=0.1, random_state=42)
                anomaly_model.fit(X_train)
                self.anomaly_detectors["test_performance"] = anomaly_model

                # Fit scaler for feature normalization
                self.scaler.fit(X_train)

        except Exception as e:
            logger.error(f"Error training models: {e}")

    def _prepare_training_data(self) -> List[Dict[str, Any]]:
        """Prepare training data from historical test executions."""
        # Get test executions from the monitoring database
        with sqlite3.connect(metrics_collector.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT test_id, test_name, test_suite, status, duration, timestamp, build_id
                FROM test_executions
                WHERE timestamp >= date('now', '-90 days')
                ORDER BY timestamp ASC
            """
            )

            executions = cursor.fetchall()

        # Group by test_id and create training samples
        test_groups = defaultdict(list)
        for execution in executions:
            test_groups[execution[0]].append(
                {
                    "test_id": execution[0],
                    "test_name": execution[1],
                    "test_suite": execution[2],
                    "status": execution[3],
                    "duration": execution[4],
                    "timestamp": datetime.fromisoformat(execution[5]),
                    "build_id": execution[6],
                }
            )

        training_data = []
        for test_id, executions in test_groups.items():
            if len(executions) >= 10:  # Minimum executions for meaningful analysis
                training_data.extend(self._create_training_samples(executions))

        return training_data

    def _create_training_samples(
        self, executions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Create training samples from test execution history."""
        samples = []

        # Sort by timestamp
        executions.sort(key=lambda x: x["timestamp"])

        # Create sliding window samples
        window_size = 10
        for i in range(window_size, len(executions)):
            window = executions[i - window_size : i]
            target_execution = executions[i]

            # Calculate features for the window
            pass_rate = sum(1 for e in window if e["status"] == "passed") / len(window)
            avg_duration = statistics.mean(
                [e["duration"] for e in window if e["duration"]]
            )
            duration_variance = (
                statistics.variance([e["duration"] for e in window if e["duration"]])
                if len(window) > 1
                else 0
            )

            # Calculate trend
            recent_pass_rate = (
                sum(1 for e in window[-5:] if e["status"] == "passed") / 5
            )
            trend = recent_pass_rate - pass_rate

            # Time features
            time_since_last_failure = 0
            for j in range(len(window) - 1, -1, -1):
                if window[j]["status"] != "passed":
                    break
                time_since_last_failure += 1

            # Target: will the next execution fail?
            target_unstable = target_execution["status"] != "passed"

            sample = {
                "test_id": target_execution["test_id"],
                "pass_rate": pass_rate,
                "avg_duration": avg_duration,
                "duration_variance": duration_variance,
                "trend": trend,
                "time_since_last_failure": time_since_last_failure,
                "execution_count": len(window),
                "target_unstable": target_unstable,
            }

            samples.append(sample)

        return samples

    def _create_feature_matrix(
        self, training_data: List[Dict[str, Any]]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Create feature matrix and target vector for machine learning."""
        if not training_data:
            return np.array([]), np.array([])

        features = []
        targets = []

        feature_names = [
            "pass_rate",
            "avg_duration",
            "duration_variance",
            "trend",
            "time_since_last_failure",
            "execution_count",
        ]

        for sample in training_data:
            feature_vector = [sample.get(name, 0) for name in feature_names]
            features.append(feature_vector)
            targets.append(sample["target_unstable"])

        return np.array(features), np.array(targets)

    def predict_test_instability(self, test_id: str) -> Optional[PredictionResult]:
        """Predict the likelihood of test instability."""
        if not SKLEARN_AVAILABLE or "instability" not in self.prediction_models:
            return self._simple_instability_prediction(test_id)

        # Get recent test metrics
        test_metrics = metrics_collector.get_test_metrics(test_id)
        if not test_metrics:
            return None

        # Prepare features
        features = self._extract_prediction_features(test_metrics)
        if not features:
            return None

        # Make prediction
        model = self.prediction_models["instability"]
        feature_vector = np.array(features).reshape(1, -1)

        # Normalize features
        if self.scaler:
            feature_vector = self.scaler.transform(feature_vector)

        # Get prediction probability
        instability_prob = model.predict_proba(feature_vector)[0][
            1
        ]  # Probability of instability
        confidence = max(model.predict_proba(feature_vector)[0])

        # Determine risk level
        if instability_prob >= 0.8:
            risk_level = "critical"
        elif instability_prob >= 0.6:
            risk_level = "high"
        elif instability_prob >= 0.4:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Identify contributing factors
        contributing_factors = self._identify_contributing_factors(
            test_metrics, model, features
        )

        result = PredictionResult(
            test_id=test_id,
            test_name=test_metrics.test_name,
            test_suite=test_metrics.test_suite,
            instability_probability=instability_prob,
            risk_level=risk_level,
            contributing_factors=contributing_factors,
            confidence=confidence,
            prediction_date=datetime.now(),
        )

        # Store prediction result
        self._store_prediction_result(result)

        return result

    def _simple_instability_prediction(
        self, test_id: str
    ) -> Optional[PredictionResult]:
        """Simple rule-based instability prediction when ML is not available."""
        test_metrics = metrics_collector.get_test_metrics(test_id)
        if not test_metrics:
            return None

        # Simple scoring based on metrics
        instability_score = 0.0
        contributing_factors = []

        # Low pass rate increases instability
        if test_metrics.pass_rate < 0.8:
            instability_score += (0.8 - test_metrics.pass_rate) * 0.5
            contributing_factors.append("Low pass rate")

        # High flakiness increases instability
        if test_metrics.flakiness_score > 0.3:
            instability_score += test_metrics.flakiness_score * 0.3
            contributing_factors.append("High flakiness")

        # Degrading trend increases instability
        if test_metrics.trend == "degrading":
            instability_score += 0.2
            contributing_factors.append("Degrading trend")

        # Low execution count increases uncertainty
        if test_metrics.execution_count < 20:
            instability_score += 0.1
            contributing_factors.append("Limited execution history")

        instability_prob = min(1.0, instability_score)

        # Determine risk level
        if instability_prob >= 0.6:
            risk_level = "high"
        elif instability_prob >= 0.4:
            risk_level = "medium"
        elif instability_prob >= 0.2:
            risk_level = "low"
        else:
            risk_level = "low"

        result = PredictionResult(
            test_id=test_id,
            test_name=test_metrics.test_name,
            test_suite=test_metrics.test_suite,
            instability_probability=instability_prob,
            risk_level=risk_level,
            contributing_factors=contributing_factors,
            confidence=0.7,  # Lower confidence for rule-based approach
            prediction_date=datetime.now(),
        )

        self._store_prediction_result(result)
        return result

    def _extract_prediction_features(
        self, test_metrics: TestMetrics
    ) -> Optional[List[float]]:
        """Extract features for prediction from test metrics."""
        try:
            features = [
                test_metrics.pass_rate,
                test_metrics.avg_duration,
                test_metrics.flakiness_score,
                1.0 if test_metrics.trend == "degrading" else 0.0,
                test_metrics.execution_count,
                (
                    datetime.now() - test_metrics.last_execution
                ).days,  # Days since last execution
            ]
            return features
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return None

    def _identify_contributing_factors(
        self, test_metrics: TestMetrics, model: Any, features: List[float]
    ) -> List[str]:
        """Identify factors contributing to instability prediction."""
        contributing_factors = []

        # Feature importance from the model
        if hasattr(model, "feature_importances_"):
            feature_names = [
                "pass_rate",
                "avg_duration",
                "flakiness_score",
                "trend",
                "execution_count",
                "days_since_last",
            ]

            importances = model.feature_importances_

            # Identify top contributing features
            top_indices = np.argsort(importances)[-3:]  # Top 3 features

            for idx in top_indices:
                if importances[idx] > 0.1:  # Significant contribution
                    feature_name = feature_names[idx]
                    if feature_name == "pass_rate" and test_metrics.pass_rate < 0.8:
                        contributing_factors.append("Low pass rate")
                    elif (
                        feature_name == "flakiness_score"
                        and test_metrics.flakiness_score > 0.3
                    ):
                        contributing_factors.append("High flakiness")
                    elif feature_name == "trend" and test_metrics.trend == "degrading":
                        contributing_factors.append("Degrading performance trend")
                    elif (
                        feature_name == "avg_duration"
                        and test_metrics.avg_duration > 30
                    ):
                        contributing_factors.append("Long execution time")
                    elif (
                        feature_name == "execution_count"
                        and test_metrics.execution_count < 20
                    ):
                        contributing_factors.append("Limited execution history")

        if not contributing_factors:
            contributing_factors = ["Multiple factors"]

        return contributing_factors

    def analyze_code_change_correlation(
        self, commit_hash: str, files_changed: List[str]
    ) -> CorrelationAnalysis:
        """Analyze correlation between code changes and test failures."""
        analysis_id = f"corr_{commit_hash}_{int(datetime.now().timestamp())}"

        # Get test executions around the commit time
        # This would require integration with git history
        # For now, we'll analyze recent failures

        affected_tests = []
        correlation_strength = 0.0
        failure_pattern = "unknown"

        # Get recent problematic tests
        problematic_tests = metrics_collector.get_problematic_tests()

        # Simple heuristic: tests in files related to changed files
        for test_metrics in problematic_tests:
            test_file_pattern = test_metrics.test_suite.replace("test_", "").replace(
                "_test", ""
            )

            for changed_file in files_changed:
                if (
                    test_file_pattern in changed_file
                    or changed_file.replace(".py", "") in test_file_pattern
                ):
                    affected_tests.append(test_metrics.test_id)
                    correlation_strength += 0.2  # Increase correlation

        correlation_strength = min(1.0, correlation_strength)

        if len(affected_tests) > 5:
            failure_pattern = "widespread_impact"
        elif len(affected_tests) > 2:
            failure_pattern = "targeted_impact"
        elif len(affected_tests) > 0:
            failure_pattern = "isolated_impact"
        else:
            failure_pattern = "no_impact"

        analysis = CorrelationAnalysis(
            analysis_id=analysis_id,
            time_period=(datetime.now() - timedelta(hours=24), datetime.now()),
            commit_hash=commit_hash,
            files_changed=files_changed,
            affected_tests=affected_tests,
            correlation_strength=correlation_strength,
            failure_pattern=failure_pattern,
            analysis_date=datetime.now(),
        )

        # Store analysis result
        self._store_correlation_analysis(analysis)

        return analysis

    def analyze_test_trends(self, test_id: str, days: int = 30) -> TrendAnalysis:
        """Analyze long-term trends for a specific test."""
        # Get historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        with sqlite3.connect(metrics_collector.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT status, duration, timestamp
                FROM test_executions
                WHERE test_id = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC
            """,
                (test_id, start_date.isoformat(), end_date.isoformat()),
            )

            executions = cursor.fetchall()

        if len(executions) < 10:
            # Not enough data for meaningful trend analysis
            return self._create_minimal_trend_analysis(test_id, start_date, end_date)

        # Calculate daily metrics
        daily_metrics = self._calculate_daily_metrics(executions)

        # Analyze trend direction and strength
        trend_direction, trend_strength = self._calculate_trend(daily_metrics)

        # Detect seasonal patterns (weekly, etc.)
        seasonal_patterns = self._detect_seasonal_patterns(daily_metrics)

        # Detect anomalies
        anomalies = self._detect_anomalies(daily_metrics)

        # Generate forecast
        forecast = self._generate_forecast(daily_metrics)

        test_metrics = metrics_collector.get_test_metrics(test_id)
        test_name = test_metrics.test_name if test_metrics else test_id

        analysis = TrendAnalysis(
            test_id=test_id,
            test_name=test_name,
            analysis_period=(start_date, end_date),
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            seasonal_patterns=seasonal_patterns,
            anomalies_detected=anomalies,
            forecast_next_week=forecast,
        )

        # Store trend analysis
        self._store_trend_analysis(analysis)

        return analysis

    def _calculate_daily_metrics(
        self, executions: List[Tuple]
    ) -> Dict[str, Dict[str, float]]:
        """Calculate daily aggregated metrics from executions."""
        daily_data = defaultdict(list)

        for execution in executions:
            date_key = datetime.fromisoformat(execution[2]).date().isoformat()
            daily_data[date_key].append(
                {
                    "status": execution[0],
                    "duration": execution[1],
                    "timestamp": execution[2],
                }
            )

        daily_metrics = {}
        for date_key, day_executions in daily_data.items():
            total_executions = len(day_executions)
            passed_executions = sum(
                1 for e in day_executions if e["status"] == "passed"
            )

            daily_metrics[date_key] = {
                "pass_rate": passed_executions / total_executions,
                "avg_duration": statistics.mean(
                    [e["duration"] for e in day_executions if e["duration"]]
                ),
                "execution_count": total_executions,
            }

        return daily_metrics

    def _calculate_trend(
        self, daily_metrics: Dict[str, Dict[str, float]]
    ) -> Tuple[str, float]:
        """Calculate trend direction and strength."""
        if len(daily_metrics) < 7:
            return "stable", 0.0

        dates = sorted(daily_metrics.keys())
        pass_rates = [daily_metrics[date]["pass_rate"] for date in dates]

        # Simple linear trend
        x = np.arange(len(pass_rates))
        if len(x) > 1:
            slope = np.polyfit(x, pass_rates, 1)[0]

            if slope > 0.01:
                direction = "improving"
                strength = min(1.0, abs(slope) * 10)
            elif slope < -0.01:
                direction = "degrading"
                strength = min(1.0, abs(slope) * 10)
            else:
                direction = "stable"
                strength = 0.0

            # Check for volatility
            variance = np.var(pass_rates)
            if variance > 0.1:
                direction = "volatile"
                strength = min(1.0, variance * 5)
        else:
            direction = "stable"
            strength = 0.0

        return direction, strength

    def _detect_seasonal_patterns(
        self, daily_metrics: Dict[str, Dict[str, float]]
    ) -> List[str]:
        """Detect seasonal patterns in test performance."""
        patterns = []

        if len(daily_metrics) < 14:
            return patterns

        # Group by day of week
        weekday_metrics = defaultdict(list)
        for date_key, metrics in daily_metrics.items():
            date_obj = datetime.fromisoformat(date_key)
            weekday = date_obj.strftime("%A")
            weekday_metrics[weekday].append(metrics["pass_rate"])

        # Check for weekday patterns
        weekday_avg = {}
        for weekday, pass_rates in weekday_metrics.items():
            if len(pass_rates) >= 2:
                weekday_avg[weekday] = statistics.mean(pass_rates)

        if len(weekday_avg) >= 5:
            overall_avg = statistics.mean(weekday_avg.values())

            # Find days significantly different from average
            for weekday, avg_pass_rate in weekday_avg.items():
                if abs(avg_pass_rate - overall_avg) > 0.1:
                    if avg_pass_rate < overall_avg:
                        patterns.append(f"Lower performance on {weekday}")
                    else:
                        patterns.append(f"Higher performance on {weekday}")

        return patterns

    def _detect_anomalies(
        self, daily_metrics: Dict[str, Dict[str, float]]
    ) -> List[datetime]:
        """Detect anomalous days in test performance."""
        anomalies = []

        if len(daily_metrics) < 10:
            return anomalies

        pass_rates = [metrics["pass_rate"] for metrics in daily_metrics.values()]
        mean_pass_rate = statistics.mean(pass_rates)

        if len(pass_rates) > 1:
            std_pass_rate = statistics.stdev(pass_rates)

            # Detect outliers (more than 2 standard deviations from mean)
            for date_key, metrics in daily_metrics.items():
                if abs(metrics["pass_rate"] - mean_pass_rate) > 2 * std_pass_rate:
                    anomalies.append(datetime.fromisoformat(date_key))

        return sorted(anomalies)

    def _generate_forecast(
        self, daily_metrics: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """Generate simple forecast for next week."""
        if len(daily_metrics) < 7:
            return {"pass_rate": 0.8, "confidence": 0.3}

        # Simple moving average forecast
        recent_dates = sorted(daily_metrics.keys())[-7:]  # Last 7 days
        recent_pass_rates = [daily_metrics[date]["pass_rate"] for date in recent_dates]

        forecast_pass_rate = statistics.mean(recent_pass_rates)

        # Calculate confidence based on recent stability
        if len(recent_pass_rates) > 1:
            recent_variance = statistics.variance(recent_pass_rates)
            confidence = max(0.1, 1.0 - recent_variance * 5)
        else:
            confidence = 0.5

        return {"pass_rate": forecast_pass_rate, "confidence": min(1.0, confidence)}

    def _create_minimal_trend_analysis(
        self, test_id: str, start_date: datetime, end_date: datetime
    ) -> TrendAnalysis:
        """Create minimal trend analysis when insufficient data."""
        test_metrics = metrics_collector.get_test_metrics(test_id)
        test_name = test_metrics.test_name if test_metrics else test_id

        return TrendAnalysis(
            test_id=test_id,
            test_name=test_name,
            analysis_period=(start_date, end_date),
            trend_direction="insufficient_data",
            trend_strength=0.0,
            seasonal_patterns=[],
            anomalies_detected=[],
            forecast_next_week={"pass_rate": 0.8, "confidence": 0.1},
        )

    def _store_prediction_result(self, result: PredictionResult):
        """Store prediction result in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO prediction_results
                (test_id, test_name, test_suite, instability_probability, risk_level,
                 contributing_factors, confidence, prediction_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    result.test_id,
                    result.test_name,
                    result.test_suite,
                    result.instability_probability,
                    result.risk_level,
                    json.dumps(result.contributing_factors),
                    result.confidence,
                    result.prediction_date.isoformat(),
                ),
            )

    def _store_correlation_analysis(self, analysis: CorrelationAnalysis):
        """Store correlation analysis in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO correlation_analyses
                (analysis_id, commit_hash, files_changed, affected_tests,
                 correlation_strength, failure_pattern, analysis_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    analysis.analysis_id,
                    analysis.commit_hash,
                    json.dumps(analysis.files_changed),
                    json.dumps(analysis.affected_tests),
                    analysis.correlation_strength,
                    analysis.failure_pattern,
                    analysis.analysis_date.isoformat(),
                ),
            )

    def _store_trend_analysis(self, analysis: TrendAnalysis):
        """Store trend analysis in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO trend_analyses
                (test_id, test_name, trend_direction, trend_strength,
                 seasonal_patterns, anomalies_detected, forecast_data, analysis_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    analysis.test_id,
                    analysis.test_name,
                    analysis.trend_direction,
                    analysis.trend_strength,
                    json.dumps(analysis.seasonal_patterns),
                    json.dumps([a.isoformat() for a in analysis.anomalies_detected]),
                    json.dumps(analysis.forecast_next_week),
                    datetime.now().isoformat(),
                ),
            )

    def generate_weekly_report(self) -> Dict[str, Any]:
        """Generate comprehensive weekly test analytics report."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        # Overall statistics
        summary = metrics_collector.get_dashboard_summary()

        # High-risk predictions
        high_risk_predictions = []
        all_tests = metrics_collector.get_all_test_metrics(limit=50)

        for test_metrics in all_tests:
            prediction = self.predict_test_instability(test_metrics.test_id)
            if prediction and prediction.risk_level in ["high", "critical"]:
                high_risk_predictions.append(asdict(prediction))

        # Recent trend analyses
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT test_id, test_name, trend_direction, trend_strength
                FROM trend_analyses
                WHERE analysis_date >= ?
                ORDER BY trend_strength DESC
                LIMIT 10
            """,
                (start_date.isoformat(),),
            )

            trend_results = cursor.fetchall()

        # Correlation analyses
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT commit_hash, correlation_strength, failure_pattern, affected_tests
                FROM correlation_analyses
                WHERE analysis_date >= ?
                ORDER BY correlation_strength DESC
                LIMIT 5
            """,
                (start_date.isoformat(),),
            )

            correlation_results = cursor.fetchall()

        report = {
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "summary": summary,
            "high_risk_predictions": high_risk_predictions[:10],
            "trend_analysis": [
                {
                    "test_id": row[0],
                    "test_name": row[1],
                    "trend_direction": row[2],
                    "trend_strength": row[3],
                }
                for row in trend_results
            ],
            "correlation_analysis": [
                {
                    "commit_hash": row[0],
                    "correlation_strength": row[1],
                    "failure_pattern": row[2],
                    "affected_tests_count": len(json.loads(row[3])),
                }
                for row in correlation_results
            ],
            "recommendations": self._generate_recommendations(
                high_risk_predictions, trend_results
            ),
            "generated_at": datetime.now().isoformat(),
        }

        # Store weekly report
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO weekly_reports (week_start, week_end, report_data)
                VALUES (?, ?, ?)
            """,
                (start_date.isoformat(), end_date.isoformat(), json.dumps(report)),
            )

        return report

    def _generate_recommendations(
        self, high_risk_predictions: List[Dict], trend_results: List[Tuple]
    ) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # Recommendations based on high-risk predictions
        if len(high_risk_predictions) > 5:
            recommendations.append(
                "High number of unstable tests detected. Consider implementing test stability sprint."
            )

        critical_tests = [
            p for p in high_risk_predictions if p["risk_level"] == "critical"
        ]
        if critical_tests:
            recommendations.append(
                f"Immediate attention required for {len(critical_tests)} critical tests."
            )

        # Recommendations based on trends
        degrading_tests = [t for t in trend_results if t[2] == "degrading"]
        if len(degrading_tests) > 3:
            recommendations.append(
                "Multiple tests showing degrading trends. Review recent code changes."
            )

        volatile_tests = [t for t in trend_results if t[2] == "volatile"]
        if volatile_tests:
            recommendations.append(
                "Volatile test behavior detected. Consider improving test isolation."
            )

        if not recommendations:
            recommendations.append("Test suite appears stable. Continue monitoring.")

        return recommendations


# Global analytics engine instance
analytics_engine = TestAnalyticsEngine()


def predict_instability(test_id: str) -> Optional[PredictionResult]:
    """Convenience function to predict test instability."""
    return analytics_engine.predict_test_instability(test_id)


def generate_weekly_analytics_report() -> Dict[str, Any]:
    """Generate weekly analytics report."""
    return analytics_engine.generate_weekly_report()


if __name__ == "__main__":
    # Example usage
    logger.info("Test Analytics Engine initialized")

    # Generate sample report
    report = generate_weekly_analytics_report()
    print(json.dumps(report, indent=2, default=str))
