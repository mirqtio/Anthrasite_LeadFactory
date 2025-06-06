"""
Advanced Cost Analytics Engine
==============================

This module provides sophisticated cost analysis, trend forecasting, and optimization
recommendations for the LeadFactory system. It extends the basic cost tracking with
machine learning-inspired analytics and business intelligence capabilities.

Features:
- Advanced trend analysis with seasonality detection
- Predictive cost forecasting with confidence intervals
- Anomaly detection using statistical methods
- ROI analysis with attribution modeling
- Cost optimization recommendations with impact estimation
- Budget variance analysis and early warning systems
"""

import json
import math
import sqlite3
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import numpy as np
    from scipy import stats

    ADVANCED_ANALYTICS_AVAILABLE = True
except ImportError:
    ADVANCED_ANALYTICS_AVAILABLE = False
    np = None
    stats = None

from leadfactory.cost.cost_tracking import cost_tracker
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class CostAnalyticsEngine:
    """Advanced cost analytics and forecasting engine."""

    def __init__(self):
        """Initialize the cost analytics engine."""
        self.logger = get_logger(f"{__name__}.CostAnalyticsEngine")

        if not ADVANCED_ANALYTICS_AVAILABLE:
            self.logger.warning(
                "Advanced analytics dependencies not available. Using fallback implementations."
            )

        self.logger.info("Cost analytics engine initialized")

    def analyze_cost_trends(
        self,
        service_type: Optional[str] = None,
        days_back: int = 90,
        forecast_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive trend analysis with advanced statistical methods.

        Args:
            service_type: Optional service filter
            days_back: Number of historical days to analyze
            forecast_days: Number of days to forecast

        Returns:
            Comprehensive trend analysis
        """
        self.logger.info(
            f"Starting trend analysis for {days_back} days back, {forecast_days} days forecast"
        )

        try:
            # Get historical data
            historical_data = self._get_historical_cost_data(service_type, days_back)

            if len(historical_data) < 7:
                return {
                    "error": "Insufficient data for trend analysis",
                    "data_points": len(historical_data),
                }

            # Extract time series data
            dates = [
                datetime.strptime(item["date"], "%Y-%m-%d") for item in historical_data
            ]
            costs = [item["cost"] for item in historical_data]

            # Perform trend decomposition
            trend_components = self._decompose_trend(costs)

            # Detect seasonality
            seasonality = self._detect_seasonality(costs, dates)

            # Generate forecasts
            forecasts = self._generate_advanced_forecast(costs, dates, forecast_days)

            # Detect anomalies
            anomalies = self._detect_advanced_anomalies(historical_data, costs)

            # Calculate trend strength and direction
            trend_metrics = self._calculate_trend_metrics(costs, dates)

            # Identify change points
            change_points = self._detect_change_points(costs, dates)

            # Calculate volatility metrics
            volatility_analysis = self._analyze_volatility(costs)

            analysis = {
                "service_type": service_type,
                "analysis_period": {
                    "start_date": dates[0].strftime("%Y-%m-%d"),
                    "end_date": dates[-1].strftime("%Y-%m-%d"),
                    "days_analyzed": len(historical_data),
                },
                "trend_components": trend_components,
                "seasonality": seasonality,
                "trend_metrics": trend_metrics,
                "forecasts": forecasts,
                "anomalies": anomalies,
                "change_points": change_points,
                "volatility_analysis": volatility_analysis,
                "summary": {
                    "overall_trend": trend_metrics["direction"],
                    "trend_strength": trend_metrics["strength"],
                    "forecast_confidence": forecasts["confidence_level"],
                    "anomaly_count": len(anomalies),
                    "seasonality_detected": seasonality["has_seasonality"],
                },
                "generated_at": datetime.now().isoformat(),
            }

            self.logger.info(f"Trend analysis completed: {analysis['summary']}")
            return analysis

        except Exception as e:
            self.logger.error(f"Error in trend analysis: {e}")
            raise

    def _get_historical_cost_data(
        self, service_type: Optional[str], days_back: int
    ) -> List[Dict[str, Any]]:
        """Get historical cost data for analysis."""
        try:
            conn = sqlite3.connect(cost_tracker.db_path)
            cursor = conn.cursor()

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            where_clauses = ["DATE(timestamp) >= ? AND DATE(timestamp) <= ?"]
            params = [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]

            if service_type:
                where_clauses.append("service = ?")
                params.append(service_type)

            where_clause = " AND ".join(where_clauses)

            cursor.execute(
                f"""
                SELECT
                    DATE(timestamp) as date,
                    SUM(amount) as cost,
                    COUNT(*) as transaction_count,
                    AVG(amount) as avg_transaction_cost
                FROM costs
                WHERE {where_clause}
                GROUP BY DATE(timestamp)
                ORDER BY date
            """,
                params,
            )

            results = cursor.fetchall()
            conn.close()

            return [
                {
                    "date": date_str,
                    "cost": float(cost),
                    "transaction_count": count,
                    "avg_transaction_cost": float(avg_cost),
                }
                for date_str, cost, count, avg_cost in results
            ]

        except Exception as e:
            self.logger.error(f"Error getting historical data: {e}")
            raise

    def _decompose_trend(self, costs: List[float]) -> Dict[str, Any]:
        """Decompose time series into trend, seasonal, and residual components."""
        if len(costs) < 14:
            return {"error": "Insufficient data for decomposition"}

        try:
            # Simple moving average for trend
            window_size = min(7, len(costs) // 3)
            trend = []

            for i in range(len(costs)):
                start_idx = max(0, i - window_size // 2)
                end_idx = min(len(costs), i + window_size // 2 + 1)
                trend.append(statistics.mean(costs[start_idx:end_idx]))

            # Calculate detrended data
            detrended = [costs[i] - trend[i] for i in range(len(costs))]

            # Estimate seasonal component (weekly pattern)
            seasonal = []
            if len(costs) >= 14:  # At least 2 weeks
                for i in range(len(costs)):
                    day_of_week = i % 7
                    same_day_values = [
                        detrended[j] for j in range(day_of_week, len(detrended), 7)
                    ]
                    seasonal.append(statistics.mean(same_day_values))
            else:
                seasonal = [0] * len(costs)

            # Calculate residuals
            residuals = [detrended[i] - seasonal[i] for i in range(len(costs))]

            # Calculate component strengths
            total_variance = statistics.variance(costs) if len(costs) > 1 else 0
            trend_variance = statistics.variance(trend) if len(trend) > 1 else 0
            seasonal_variance = (
                statistics.variance(seasonal) if len(seasonal) > 1 else 0
            )
            residual_variance = (
                statistics.variance(residuals) if len(residuals) > 1 else 0
            )

            return {
                "trend": trend,
                "seasonal": seasonal,
                "residuals": residuals,
                "variance_explained": {
                    "trend": (
                        (trend_variance / total_variance * 100)
                        if total_variance > 0
                        else 0
                    ),
                    "seasonal": (
                        (seasonal_variance / total_variance * 100)
                        if total_variance > 0
                        else 0
                    ),
                    "residual": (
                        (residual_variance / total_variance * 100)
                        if total_variance > 0
                        else 0
                    ),
                },
                "decomposition_quality": (
                    1 - (residual_variance / total_variance)
                    if total_variance > 0
                    else 0
                ),
            }

        except Exception as e:
            self.logger.error(f"Error in trend decomposition: {e}")
            return {"error": str(e)}

    def _detect_seasonality(
        self, costs: List[float], dates: List[datetime]
    ) -> Dict[str, Any]:
        """Detect seasonal patterns in cost data."""
        if len(costs) < 14:
            return {"has_seasonality": False, "reason": "Insufficient data"}

        try:
            # Test for weekly seasonality
            weekly_pattern = {}
            for i, date in enumerate(dates):
                day_of_week = date.weekday()
                if day_of_week not in weekly_pattern:
                    weekly_pattern[day_of_week] = []
                weekly_pattern[day_of_week].append(costs[i])

            # Calculate day-of-week averages
            daily_averages = {}
            for day, values in weekly_pattern.items():
                if len(values) >= 2:
                    daily_averages[day] = statistics.mean(values)

            # Test for significant weekly variation
            if len(daily_averages) >= 7:
                avg_costs = list(daily_averages.values())
                weekly_variance = statistics.variance(avg_costs)
                overall_mean = statistics.mean(costs)
                coefficient_of_variation = (
                    (weekly_variance**0.5) / overall_mean if overall_mean > 0 else 0
                )

                has_weekly_seasonality = coefficient_of_variation > 0.1  # 10% threshold
            else:
                has_weekly_seasonality = False

            # Test for monthly patterns (if enough data)
            monthly_pattern = {}
            if len(dates) >= 60:  # At least 2 months
                for i, date in enumerate(dates):
                    day_of_month = date.day
                    if day_of_month not in monthly_pattern:
                        monthly_pattern[day_of_month] = []
                    monthly_pattern[day_of_month].append(costs[i])

                monthly_averages = {}
                for day, values in monthly_pattern.items():
                    if len(values) >= 2:
                        monthly_averages[day] = statistics.mean(values)

                if len(monthly_averages) >= 15:  # At least half the month
                    avg_monthly_costs = list(monthly_averages.values())
                    monthly_variance = statistics.variance(avg_monthly_costs)
                    monthly_cv = (
                        (monthly_variance**0.5) / overall_mean
                        if overall_mean > 0
                        else 0
                    )
                    has_monthly_seasonality = monthly_cv > 0.15
                else:
                    has_monthly_seasonality = False
            else:
                has_monthly_seasonality = False

            return {
                "has_seasonality": has_weekly_seasonality or has_monthly_seasonality,
                "weekly_seasonality": {
                    "detected": has_weekly_seasonality,
                    "daily_averages": {
                        [
                            "Monday",
                            "Tuesday",
                            "Wednesday",
                            "Thursday",
                            "Friday",
                            "Saturday",
                            "Sunday",
                        ][day]: avg
                        for day, avg in daily_averages.items()
                    },
                    "coefficient_of_variation": (
                        coefficient_of_variation
                        if "coefficient_of_variation" in locals()
                        else 0
                    ),
                },
                "monthly_seasonality": {
                    "detected": has_monthly_seasonality,
                    "coefficient_of_variation": (
                        monthly_cv if "monthly_cv" in locals() else 0
                    ),
                },
                "peak_days": (
                    [
                        day
                        for day, avg in daily_averages.items()
                        if avg > overall_mean * 1.2
                    ]
                    if daily_averages
                    else []
                ),
                "low_days": (
                    [
                        day
                        for day, avg in daily_averages.items()
                        if avg < overall_mean * 0.8
                    ]
                    if daily_averages
                    else []
                ),
            }

        except Exception as e:
            self.logger.error(f"Error detecting seasonality: {e}")
            return {"has_seasonality": False, "error": str(e)}

    def _generate_advanced_forecast(
        self, costs: List[float], dates: List[datetime], forecast_days: int
    ) -> Dict[str, Any]:
        """Generate advanced forecast with confidence intervals."""
        if len(costs) < 7:
            return {"error": "Insufficient data for forecasting"}

        try:
            # Multiple forecasting methods
            forecasts = {}

            # 1. Linear trend forecast
            linear_forecast = self._linear_trend_forecast(costs, dates, forecast_days)
            forecasts["linear_trend"] = linear_forecast

            # 2. Exponential smoothing forecast
            exp_forecast = self._exponential_smoothing_forecast(costs, forecast_days)
            forecasts["exponential_smoothing"] = exp_forecast

            # 3. Moving average forecast
            ma_forecast = self._moving_average_forecast(costs, forecast_days)
            forecasts["moving_average"] = ma_forecast

            # 4. Seasonal naive forecast (if seasonality detected)
            if len(costs) >= 14:
                seasonal_forecast = self._seasonal_naive_forecast(costs, forecast_days)
                forecasts["seasonal_naive"] = seasonal_forecast

            # Ensemble forecast (weighted average)
            ensemble_forecast = self._create_ensemble_forecast(forecasts, forecast_days)

            # Calculate prediction intervals
            prediction_intervals = self._calculate_prediction_intervals(
                costs, ensemble_forecast["values"]
            )

            return {
                "forecast_days": forecast_days,
                "methods_used": list(forecasts.keys()),
                "individual_forecasts": forecasts,
                "ensemble_forecast": ensemble_forecast,
                "prediction_intervals": prediction_intervals,
                "confidence_level": self._calculate_forecast_confidence(
                    costs, forecasts
                ),
                "forecast_start_date": (dates[-1] + timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                ),
                "forecast_end_date": (
                    dates[-1] + timedelta(days=forecast_days)
                ).strftime("%Y-%m-%d"),
            }

        except Exception as e:
            self.logger.error(f"Error generating forecast: {e}")
            return {"error": str(e)}

    def _linear_trend_forecast(
        self, costs: List[float], dates: List[datetime], forecast_days: int
    ) -> Dict[str, Any]:
        """Generate linear trend forecast."""
        try:
            # Convert dates to numeric values
            base_date = dates[0]
            x = [(date - base_date).days for date in dates]
            y = costs

            # Calculate linear regression
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(xi**2 for xi in x)

            # Avoid division by zero
            denominator = n * sum_x2 - sum_x**2
            if abs(denominator) < 1e-10:
                return {
                    "error": "Cannot calculate linear trend - insufficient variance in dates"
                }

            slope = (n * sum_xy - sum_x * sum_y) / denominator
            intercept = (sum_y - slope * sum_x) / n

            # Generate forecast
            last_x = x[-1]
            forecast_values = []
            forecast_dates = []

            for i in range(1, forecast_days + 1):
                forecast_x = last_x + i
                forecast_value = slope * forecast_x + intercept
                forecast_values.append(max(0, forecast_value))  # Ensure non-negative
                forecast_dates.append(
                    (dates[-1] + timedelta(days=i)).strftime("%Y-%m-%d")
                )

            # Calculate R-squared
            y_mean = statistics.mean(y)
            ss_tot = sum((yi - y_mean) ** 2 for yi in y)
            ss_res = sum((y[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            return {
                "method": "linear_trend",
                "slope": slope,
                "intercept": intercept,
                "r_squared": r_squared,
                "forecast_values": forecast_values,
                "forecast_dates": forecast_dates,
            }

        except Exception as e:
            self.logger.error(f"Error in linear trend forecast: {e}")
            return {"error": str(e)}

    def _exponential_smoothing_forecast(
        self, costs: List[float], forecast_days: int
    ) -> Dict[str, Any]:
        """Generate exponential smoothing forecast."""
        try:
            alpha = 0.3  # Smoothing parameter

            # Calculate smoothed values
            smoothed = [costs[0]]
            for i in range(1, len(costs)):
                smoothed_value = alpha * costs[i] + (1 - alpha) * smoothed[-1]
                smoothed.append(smoothed_value)

            # Generate forecast
            last_smoothed = smoothed[-1]
            forecast_values = [max(0, last_smoothed)] * forecast_days
            forecast_dates = [
                (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(1, forecast_days + 1)
            ]

            # Calculate mean absolute error
            mae = statistics.mean(
                abs(costs[i] - smoothed[i]) for i in range(len(costs))
            )

            return {
                "method": "exponential_smoothing",
                "alpha": alpha,
                "mae": mae,
                "forecast_values": forecast_values,
                "forecast_dates": forecast_dates,
            }

        except Exception as e:
            self.logger.error(f"Error in exponential smoothing forecast: {e}")
            return {"error": str(e)}

    def _moving_average_forecast(
        self, costs: List[float], forecast_days: int
    ) -> Dict[str, Any]:
        """Generate moving average forecast."""
        try:
            window_size = min(7, len(costs) // 2)

            # Calculate moving average
            recent_values = costs[-window_size:]
            moving_avg = statistics.mean(recent_values)

            # Generate forecast (flat forecast)
            forecast_values = [max(0, moving_avg)] * forecast_days
            forecast_dates = [
                (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(1, forecast_days + 1)
            ]

            # Calculate standard deviation of recent values
            std_dev = statistics.stdev(recent_values) if len(recent_values) > 1 else 0

            return {
                "method": "moving_average",
                "window_size": window_size,
                "moving_average": moving_avg,
                "std_dev": std_dev,
                "forecast_values": forecast_values,
                "forecast_dates": forecast_dates,
            }

        except Exception as e:
            self.logger.error(f"Error in moving average forecast: {e}")
            return {"error": str(e)}

    def _seasonal_naive_forecast(
        self, costs: List[float], forecast_days: int
    ) -> Dict[str, Any]:
        """Generate seasonal naive forecast (repeat last week/month pattern)."""
        try:
            # Use weekly seasonality (7-day pattern)
            season_length = 7

            if len(costs) < season_length:
                return {"error": "Insufficient data for seasonal forecast"}

            # Get last complete season
            last_season = costs[-season_length:]

            # Generate forecast by repeating the pattern
            forecast_values = []
            forecast_dates = []

            for i in range(forecast_days):
                seasonal_index = i % season_length
                forecast_value = max(0, last_season[seasonal_index])
                forecast_values.append(forecast_value)
                forecast_dates.append(
                    (datetime.now() + timedelta(days=i + 1)).strftime("%Y-%m-%d")
                )

            return {
                "method": "seasonal_naive",
                "season_length": season_length,
                "seasonal_pattern": last_season,
                "forecast_values": forecast_values,
                "forecast_dates": forecast_dates,
            }

        except Exception as e:
            self.logger.error(f"Error in seasonal naive forecast: {e}")
            return {"error": str(e)}

    def _create_ensemble_forecast(
        self, forecasts: Dict[str, Any], forecast_days: int
    ) -> Dict[str, Any]:
        """Create ensemble forecast from multiple methods."""
        try:
            valid_forecasts = {
                k: v for k, v in forecasts.items() if "forecast_values" in v
            }

            if not valid_forecasts:
                return {"error": "No valid forecasts available for ensemble"}

            # Weight forecasts based on their reliability/quality
            weights = {}
            for method, forecast in valid_forecasts.items():
                if method == "linear_trend":
                    weights[method] = forecast.get("r_squared", 0.5)
                elif method == "exponential_smoothing":
                    weights[method] = 1.0 / (1.0 + forecast.get("mae", 1.0))
                elif method == "moving_average":
                    weights[method] = 0.8  # Moderate weight
                elif method == "seasonal_naive":
                    weights[method] = 0.7  # Lower weight for naive method
                else:
                    weights[method] = 0.5  # Default weight

            # Normalize weights
            total_weight = sum(weights.values())
            if total_weight > 0:
                weights = {k: v / total_weight for k, v in weights.items()}
            else:
                # Equal weights fallback
                weights = {
                    k: 1.0 / len(valid_forecasts) for k in valid_forecasts.keys()
                }

            # Calculate weighted ensemble
            ensemble_values = []
            forecast_dates = []

            for i in range(forecast_days):
                weighted_sum = 0
                for method, forecast in valid_forecasts.items():
                    if i < len(forecast["forecast_values"]):
                        weighted_sum += weights[method] * forecast["forecast_values"][i]

                ensemble_values.append(max(0, weighted_sum))

                # Use dates from first valid forecast
                if i < len(list(valid_forecasts.values())[0]["forecast_dates"]):
                    forecast_dates.append(
                        list(valid_forecasts.values())[0]["forecast_dates"][i]
                    )

            return {
                "method": "ensemble",
                "component_methods": list(valid_forecasts.keys()),
                "weights": weights,
                "values": ensemble_values,
                "dates": forecast_dates,
            }

        except Exception as e:
            self.logger.error(f"Error creating ensemble forecast: {e}")
            return {"error": str(e)}

    def _calculate_prediction_intervals(
        self, historical_costs: List[float], forecast_values: List[float]
    ) -> Dict[str, Any]:
        """Calculate prediction intervals for forecast."""
        try:
            if len(historical_costs) < 3:
                return {
                    "error": "Insufficient historical data for prediction intervals"
                }

            # Calculate historical forecast errors (using simple persistence model)
            errors = []
            for i in range(1, len(historical_costs)):
                error = abs(historical_costs[i] - historical_costs[i - 1])
                errors.append(error)

            # Calculate standard error
            if len(errors) > 1:
                std_error = statistics.stdev(errors)
            else:
                std_error = statistics.stdev(historical_costs) * 0.1  # Fallback

            # Calculate prediction intervals (assuming normal distribution)
            confidence_levels = [80, 90, 95]
            z_scores = [1.28, 1.64, 1.96]  # For 80%, 90%, 95% confidence

            intervals = {}
            for conf_level, z_score in zip(confidence_levels, z_scores):
                lower_bounds = []
                upper_bounds = []

                for i, forecast_value in enumerate(forecast_values):
                    # Increase uncertainty with forecast horizon
                    horizon_factor = 1 + (i * 0.1)  # 10% increase per period
                    margin = z_score * std_error * horizon_factor

                    lower_bounds.append(max(0, forecast_value - margin))
                    upper_bounds.append(forecast_value + margin)

                intervals[f"{conf_level}%"] = {
                    "lower_bounds": lower_bounds,
                    "upper_bounds": upper_bounds,
                }

            return {
                "standard_error": std_error,
                "intervals": intervals,
                "methodology": "normal_distribution_assumption",
            }

        except Exception as e:
            self.logger.error(f"Error calculating prediction intervals: {e}")
            return {"error": str(e)}

    def _calculate_forecast_confidence(
        self, historical_costs: List[float], forecasts: Dict[str, Any]
    ) -> float:
        """Calculate overall confidence level for forecasts."""
        try:
            if len(historical_costs) < 7:
                return 0.3  # Low confidence with little data

            confidence_factors = []

            # Factor 1: Data quantity
            data_factor = min(
                1.0, len(historical_costs) / 30
            )  # Max confidence at 30+ days
            confidence_factors.append(data_factor)

            # Factor 2: Data stability (low volatility = higher confidence)
            if len(historical_costs) > 1:
                volatility = statistics.stdev(historical_costs) / statistics.mean(
                    historical_costs
                )
                stability_factor = max(0.1, 1.0 - min(1.0, volatility))
                confidence_factors.append(stability_factor)

            # Factor 3: Forecast agreement (similar forecasts = higher confidence)
            valid_forecasts = [f for f in forecasts.values() if "forecast_values" in f]
            if len(valid_forecasts) > 1:
                # Calculate variance among first forecast values
                first_forecasts = [
                    f["forecast_values"][0]
                    for f in valid_forecasts
                    if f["forecast_values"]
                ]
                if len(first_forecasts) > 1 and statistics.mean(first_forecasts) > 0:
                    forecast_cv = statistics.stdev(first_forecasts) / statistics.mean(
                        first_forecasts
                    )
                    agreement_factor = max(0.1, 1.0 - min(1.0, forecast_cv))
                    confidence_factors.append(agreement_factor)

            # Factor 4: Trend clarity
            if len(historical_costs) >= 5:
                # Calculate correlation with time
                x = list(range(len(historical_costs)))
                y = historical_costs
                correlation = self._calculate_correlation(x, y)
                trend_factor = min(1.0, abs(correlation))
                confidence_factors.append(trend_factor)

            # Overall confidence is the average of factors
            overall_confidence = (
                statistics.mean(confidence_factors) if confidence_factors else 0.5
            )

            return min(
                0.95, max(0.1, overall_confidence)
            )  # Bounded between 10% and 95%

        except Exception as e:
            self.logger.error(f"Error calculating forecast confidence: {e}")
            return 0.5  # Default moderate confidence

    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        try:
            if len(x) != len(y) or len(x) < 2:
                return 0.0

            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(xi**2 for xi in x)
            sum_y2 = sum(yi**2 for yi in y)

            numerator = n * sum_xy - sum_x * sum_y
            denominator = ((n * sum_x2 - sum_x**2) * (n * sum_y2 - sum_y**2)) ** 0.5

            if abs(denominator) < 1e-10:
                return 0.0

            return numerator / denominator

        except Exception as e:
            self.logger.error(f"Error calculating correlation: {e}")
            return 0.0

    def _detect_advanced_anomalies(
        self, historical_data: List[Dict[str, Any]], costs: List[float]
    ) -> List[Dict[str, Any]]:
        """Detect anomalies using multiple statistical methods."""
        if len(costs) < 7:
            return []

        try:
            anomalies = []

            # Method 1: Z-score based detection
            z_score_anomalies = self._detect_zscore_anomalies(historical_data, costs)
            anomalies.extend(z_score_anomalies)

            # Method 2: Interquartile range (IQR) based detection
            iqr_anomalies = self._detect_iqr_anomalies(historical_data, costs)
            anomalies.extend(iqr_anomalies)

            # Method 3: Moving average based detection
            ma_anomalies = self._detect_moving_average_anomalies(historical_data, costs)
            anomalies.extend(ma_anomalies)

            # Method 4: Seasonal decomposition based detection
            if len(costs) >= 14:
                seasonal_anomalies = self._detect_seasonal_anomalies(
                    historical_data, costs
                )
                anomalies.extend(seasonal_anomalies)

            # Remove duplicates and sort by severity
            unique_anomalies = {}
            for anomaly in anomalies:
                key = anomaly["date"]
                if (
                    key not in unique_anomalies
                    or anomaly["severity"] > unique_anomalies[key]["severity"]
                ):
                    unique_anomalies[key] = anomaly

            # Sort by severity and return top anomalies
            sorted_anomalies = sorted(
                unique_anomalies.values(), key=lambda x: x["severity"], reverse=True
            )
            return sorted_anomalies[:20]  # Top 20 anomalies

        except Exception as e:
            self.logger.error(f"Error detecting anomalies: {e}")
            return []

    def _detect_zscore_anomalies(
        self, historical_data: List[Dict[str, Any]], costs: List[float]
    ) -> List[Dict[str, Any]]:
        """Detect anomalies using Z-score method."""
        anomalies = []

        if len(costs) < 3:
            return anomalies

        try:
            mean_cost = statistics.mean(costs)
            std_cost = statistics.stdev(costs) if len(costs) > 1 else 0

            if std_cost == 0:
                return anomalies

            threshold = 2.5  # Z-score threshold

            for i, item in enumerate(historical_data):
                z_score = abs(item["cost"] - mean_cost) / std_cost

                if z_score > threshold:
                    anomaly_type = "high" if item["cost"] > mean_cost else "low"
                    anomalies.append(
                        {
                            "date": item["date"],
                            "cost": item["cost"],
                            "expected_cost": mean_cost,
                            "z_score": z_score,
                            "severity": min(5, int(z_score / threshold * 3)),
                            "type": anomaly_type,
                            "method": "z_score",
                            "description": f"Cost was {z_score:.1f} standard deviations from mean",
                        }
                    )

            return anomalies

        except Exception as e:
            self.logger.error(f"Error in Z-score anomaly detection: {e}")
            return []

    def _detect_iqr_anomalies(
        self, historical_data: List[Dict[str, Any]], costs: List[float]
    ) -> List[Dict[str, Any]]:
        """Detect anomalies using Interquartile Range (IQR) method."""
        anomalies = []

        if len(costs) < 4:
            return anomalies

        try:
            sorted_costs = sorted(costs)
            n = len(sorted_costs)

            # Calculate quartiles
            q1_idx = n // 4
            q3_idx = 3 * n // 4
            q1 = sorted_costs[q1_idx]
            q3 = sorted_costs[q3_idx]
            iqr = q3 - q1

            if iqr == 0:
                return anomalies

            # Calculate bounds
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            for item in historical_data:
                if item["cost"] < lower_bound or item["cost"] > upper_bound:
                    anomaly_type = "high" if item["cost"] > upper_bound else "low"
                    deviation = abs(
                        item["cost"] - (q3 if anomaly_type == "high" else q1)
                    )
                    severity = min(5, int(deviation / iqr) + 1)

                    anomalies.append(
                        {
                            "date": item["date"],
                            "cost": item["cost"],
                            "q1": q1,
                            "q3": q3,
                            "iqr": iqr,
                            "severity": severity,
                            "type": anomaly_type,
                            "method": "iqr",
                            "description": f"Cost outside IQR bounds ({lower_bound:.2f}, {upper_bound:.2f})",
                        }
                    )

            return anomalies

        except Exception as e:
            self.logger.error(f"Error in IQR anomaly detection: {e}")
            return []

    def _detect_moving_average_anomalies(
        self, historical_data: List[Dict[str, Any]], costs: List[float]
    ) -> List[Dict[str, Any]]:
        """Detect anomalies using moving average deviation."""
        anomalies = []

        if len(costs) < 5:
            return anomalies

        try:
            window_size = min(7, len(costs) // 3)
            threshold_multiplier = 2.0

            for i in range(window_size, len(costs)):
                # Calculate moving average for window
                window_costs = costs[i - window_size : i]
                moving_avg = statistics.mean(window_costs)
                moving_std = (
                    statistics.stdev(window_costs) if len(window_costs) > 1 else 0
                )

                if moving_std > 0:
                    current_cost = costs[i]
                    deviation = abs(current_cost - moving_avg)
                    threshold = threshold_multiplier * moving_std

                    if deviation > threshold:
                        anomaly_type = "high" if current_cost > moving_avg else "low"
                        severity = min(5, int(deviation / moving_std))

                        anomalies.append(
                            {
                                "date": historical_data[i]["date"],
                                "cost": current_cost,
                                "moving_average": moving_avg,
                                "deviation": deviation,
                                "threshold": threshold,
                                "severity": severity,
                                "type": anomaly_type,
                                "method": "moving_average",
                                "description": f"Cost deviated {deviation:.2f} from {window_size}-day moving average",
                            }
                        )

            return anomalies

        except Exception as e:
            self.logger.error(f"Error in moving average anomaly detection: {e}")
            return []

    def _detect_seasonal_anomalies(
        self, historical_data: List[Dict[str, Any]], costs: List[float]
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in seasonal patterns."""
        anomalies = []

        if len(costs) < 14:
            return anomalies

        try:
            # Group by day of week
            weekday_costs = [[] for _ in range(7)]

            for i, item in enumerate(historical_data):
                date = datetime.strptime(item["date"], "%Y-%m-%d")
                weekday = date.weekday()
                weekday_costs[weekday].append(item["cost"])

            # Calculate expected costs and thresholds for each weekday
            weekday_stats = {}
            for weekday in range(7):
                if len(weekday_costs[weekday]) >= 2:
                    mean_cost = statistics.mean(weekday_costs[weekday])
                    std_cost = statistics.stdev(weekday_costs[weekday])
                    weekday_stats[weekday] = {
                        "mean": mean_cost,
                        "std": std_cost,
                        "threshold": 2.0 * std_cost,
                    }

            # Check for seasonal anomalies
            for item in historical_data:
                date = datetime.strptime(item["date"], "%Y-%m-%d")
                weekday = date.weekday()

                if weekday in weekday_stats:
                    stats = weekday_stats[weekday]
                    deviation = abs(item["cost"] - stats["mean"])

                    if deviation > stats["threshold"] and stats["std"] > 0:
                        anomaly_type = "high" if item["cost"] > stats["mean"] else "low"
                        severity = min(5, int(deviation / stats["std"]))

                        weekday_names = [
                            "Monday",
                            "Tuesday",
                            "Wednesday",
                            "Thursday",
                            "Friday",
                            "Saturday",
                            "Sunday",
                        ]

                        anomalies.append(
                            {
                                "date": item["date"],
                                "cost": item["cost"],
                                "expected_cost": stats["mean"],
                                "weekday": weekday_names[weekday],
                                "deviation": deviation,
                                "severity": severity,
                                "type": anomaly_type,
                                "method": "seasonal",
                                "description": f"Unusual cost for {weekday_names[weekday]}: {deviation:.2f} above normal",
                            }
                        )

            return anomalies

        except Exception as e:
            self.logger.error(f"Error in seasonal anomaly detection: {e}")
            return []

    def _calculate_trend_metrics(
        self, costs: List[float], dates: List[datetime]
    ) -> Dict[str, Any]:
        """Calculate comprehensive trend metrics."""
        if len(costs) < 3:
            return {"error": "Insufficient data for trend metrics"}

        try:
            # Basic statistics
            total_cost = sum(costs)
            avg_cost = statistics.mean(costs)
            min_cost = min(costs)
            max_cost = max(costs)

            # Trend direction and strength
            x = list(range(len(costs)))
            correlation = self._calculate_correlation(x, costs)

            # Determine trend direction
            if correlation > 0.1:
                direction = "increasing"
            elif correlation < -0.1:
                direction = "decreasing"
            else:
                direction = "stable"

            # Trend strength (absolute correlation)
            strength = abs(correlation)

            # Rate of change
            if len(costs) >= 2:
                total_change = costs[-1] - costs[0]
                time_span = (dates[-1] - dates[0]).days
                daily_change_rate = total_change / time_span if time_span > 0 else 0

                # Percentage change
                pct_change = (total_change / costs[0] * 100) if costs[0] > 0 else 0
            else:
                daily_change_rate = 0
                pct_change = 0

            # Volatility metrics
            if len(costs) > 1:
                volatility = statistics.stdev(costs)
                coefficient_of_variation = volatility / avg_cost if avg_cost > 0 else 0
            else:
                volatility = 0
                coefficient_of_variation = 0

            # Acceleration (second derivative)
            if len(costs) >= 3:
                # Calculate first differences
                first_diffs = [costs[i + 1] - costs[i] for i in range(len(costs) - 1)]
                # Calculate second differences (acceleration)
                second_diffs = [
                    first_diffs[i + 1] - first_diffs[i]
                    for i in range(len(first_diffs) - 1)
                ]
                avg_acceleration = statistics.mean(second_diffs) if second_diffs else 0
            else:
                avg_acceleration = 0

            # Recent vs historical comparison
            if len(costs) >= 6:
                recent_period = costs[-3:]  # Last 3 values
                historical_period = costs[:-3]  # All but last 3

                recent_avg = statistics.mean(recent_period)
                historical_avg = statistics.mean(historical_period)

                recent_vs_historical = (
                    ((recent_avg - historical_avg) / historical_avg * 100)
                    if historical_avg > 0
                    else 0
                )
            else:
                recent_vs_historical = 0

            return {
                "direction": direction,
                "strength": strength,
                "correlation": correlation,
                "total_cost": total_cost,
                "average_cost": avg_cost,
                "min_cost": min_cost,
                "max_cost": max_cost,
                "daily_change_rate": daily_change_rate,
                "percentage_change": pct_change,
                "volatility": volatility,
                "coefficient_of_variation": coefficient_of_variation,
                "acceleration": avg_acceleration,
                "recent_vs_historical_pct": recent_vs_historical,
                "data_points": len(costs),
                "time_span_days": (dates[-1] - dates[0]).days,
            }

        except Exception as e:
            self.logger.error(f"Error calculating trend metrics: {e}")
            return {"error": str(e)}

    def _detect_change_points(
        self, costs: List[float], dates: List[datetime]
    ) -> List[Dict[str, Any]]:
        """Detect significant change points in the cost time series."""
        if len(costs) < 10:
            return []

        try:
            change_points = []
            window_size = max(3, len(costs) // 10)  # Adaptive window size
            threshold = 1.5  # Standard deviations for significance

            for i in range(window_size, len(costs) - window_size):
                # Compare before and after windows
                before_window = costs[i - window_size : i]
                after_window = costs[i : i + window_size]

                if len(before_window) > 1 and len(after_window) > 1:
                    before_mean = statistics.mean(before_window)
                    after_mean = statistics.mean(after_window)

                    # Calculate pooled standard deviation
                    before_var = statistics.variance(before_window)
                    after_var = statistics.variance(after_window)
                    pooled_std = ((before_var + after_var) / 2) ** 0.5

                    if pooled_std > 0:
                        # Calculate t-statistic (simplified)
                        mean_diff = abs(after_mean - before_mean)
                        t_stat = mean_diff / (pooled_std * (2 / window_size) ** 0.5)

                        if t_stat > threshold:
                            change_type = (
                                "increase" if after_mean > before_mean else "decrease"
                            )
                            magnitude = abs(after_mean - before_mean)
                            relative_magnitude = (
                                magnitude / before_mean * 100 if before_mean > 0 else 0
                            )

                            change_points.append(
                                {
                                    "date": dates[i].strftime("%Y-%m-%d"),
                                    "index": i,
                                    "type": change_type,
                                    "before_mean": before_mean,
                                    "after_mean": after_mean,
                                    "magnitude": magnitude,
                                    "relative_magnitude_pct": relative_magnitude,
                                    "significance": t_stat,
                                    "description": f"Significant {change_type} of {relative_magnitude:.1f}%",
                                }
                            )

            # Sort by significance and return top change points
            change_points.sort(key=lambda x: x["significance"], reverse=True)
            return change_points[:10]  # Top 10 change points

        except Exception as e:
            self.logger.error(f"Error detecting change points: {e}")
            return []

    def _analyze_volatility(self, costs: List[float]) -> Dict[str, Any]:
        """Analyze cost volatility patterns."""
        if len(costs) < 3:
            return {"error": "Insufficient data for volatility analysis"}

        try:
            # Basic volatility metrics
            avg_cost = statistics.mean(costs)
            std_dev = statistics.stdev(costs) if len(costs) > 1 else 0
            coefficient_of_variation = std_dev / avg_cost if avg_cost > 0 else 0

            # Rolling volatility (if enough data)
            rolling_volatilities = []
            window_size = min(7, len(costs) // 3)

            if window_size >= 3:
                for i in range(window_size, len(costs) + 1):
                    window_costs = costs[i - window_size : i]
                    if len(window_costs) > 1:
                        window_volatility = statistics.stdev(window_costs)
                        rolling_volatilities.append(window_volatility)

            # Volatility trend
            if len(rolling_volatilities) >= 3:
                x = list(range(len(rolling_volatilities)))
                volatility_trend = self._calculate_correlation(x, rolling_volatilities)

                if volatility_trend > 0.2:
                    volatility_trend_desc = "increasing"
                elif volatility_trend < -0.2:
                    volatility_trend_desc = "decreasing"
                else:
                    volatility_trend_desc = "stable"
            else:
                volatility_trend = 0
                volatility_trend_desc = "unknown"

            # High volatility periods
            if rolling_volatilities:
                avg_volatility = statistics.mean(rolling_volatilities)
                high_volatility_threshold = avg_volatility * 1.5
                high_volatility_periods = len(
                    [v for v in rolling_volatilities if v > high_volatility_threshold]
                )
            else:
                high_volatility_periods = 0

            # Volatility classification
            if coefficient_of_variation < 0.1:
                volatility_level = "low"
            elif coefficient_of_variation < 0.3:
                volatility_level = "moderate"
            elif coefficient_of_variation < 0.5:
                volatility_level = "high"
            else:
                volatility_level = "very_high"

            return {
                "standard_deviation": std_dev,
                "coefficient_of_variation": coefficient_of_variation,
                "volatility_level": volatility_level,
                "rolling_volatilities": rolling_volatilities,
                "average_rolling_volatility": (
                    statistics.mean(rolling_volatilities) if rolling_volatilities else 0
                ),
                "volatility_trend": volatility_trend,
                "volatility_trend_description": volatility_trend_desc,
                "high_volatility_periods": high_volatility_periods,
                "total_periods": len(rolling_volatilities),
                "min_cost": min(costs),
                "max_cost": max(costs),
                "cost_range": max(costs) - min(costs),
            }

        except Exception as e:
            self.logger.error(f"Error analyzing volatility: {e}")
            return {"error": str(e)}

    def generate_cost_optimization_recommendations(
        self, analysis_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate actionable cost optimization recommendations based on analysis."""
        try:
            recommendations = []
            priority_scores = []

            # Extract key metrics from analysis
            trend_metrics = analysis_results.get("trend_metrics", {})
            volatility_analysis = analysis_results.get("volatility_analysis", {})
            anomalies = analysis_results.get("anomalies", [])
            forecasts = analysis_results.get("forecasts", {})

            # Recommendation 1: Volatility management
            volatility_level = volatility_analysis.get("volatility_level", "unknown")
            if volatility_level in ["high", "very_high"]:
                cv = volatility_analysis.get("coefficient_of_variation", 0)
                recommendation = {
                    "type": "volatility_management",
                    "priority": "high",
                    "title": "Implement Cost Smoothing Strategies",
                    "description": f"Cost volatility is {volatility_level} (CV: {cv:.2f})",
                    "actions": [
                        "Implement request batching to reduce transaction frequency",
                        "Use cost averaging strategies for API calls",
                        "Set up automated alerts for cost spikes",
                        "Consider reserved pricing for predictable workloads",
                    ],
                    "estimated_savings": trend_metrics.get("average_cost", 0)
                    * 0.15,  # 15% potential savings
                    "impact": "Reduce cost unpredictability and enable better budgeting",
                }
                recommendations.append(recommendation)
                priority_scores.append(3)

            # Recommendation 2: Trend-based optimization
            trend_direction = trend_metrics.get("direction", "stable")
            growth_rate = trend_metrics.get("percentage_change", 0)

            if trend_direction == "increasing" and growth_rate > 20:
                recommendation = {
                    "type": "growth_control",
                    "priority": "high",
                    "title": "Control Rapid Cost Growth",
                    "description": f"Costs are increasing at {growth_rate:.1f}% rate",
                    "actions": [
                        "Review and optimize high-frequency API calls",
                        "Implement rate limiting and throttling",
                        "Analyze cost per transaction efficiency",
                        "Consider alternative service providers or pricing tiers",
                    ],
                    "estimated_savings": trend_metrics.get("total_cost", 0)
                    * 0.25,  # 25% potential savings
                    "impact": "Prevent budget overruns and improve cost efficiency",
                }
                recommendations.append(recommendation)
                priority_scores.append(3)

            # Recommendation 3: Anomaly-based optimization
            high_severity_anomalies = [
                a for a in anomalies if a.get("severity", 0) >= 4
            ]
            if len(high_severity_anomalies) > 3:
                avg_anomaly_cost = statistics.mean(
                    [a.get("cost", 0) for a in high_severity_anomalies]
                )
                recommendation = {
                    "type": "anomaly_prevention",
                    "priority": "medium",
                    "title": "Prevent Cost Anomalies",
                    "description": f"Detected {len(high_severity_anomalies)} high-severity cost anomalies",
                    "actions": [
                        "Implement real-time cost monitoring and alerts",
                        "Set up automatic circuit breakers for high-cost operations",
                        "Review unusual usage patterns on anomaly dates",
                        "Implement pre-approval workflows for high-cost operations",
                    ],
                    "estimated_savings": avg_anomaly_cost
                    * len(high_severity_anomalies)
                    * 0.5,  # 50% anomaly prevention
                    "impact": "Prevent unexpected cost spikes and improve predictability",
                }
                recommendations.append(recommendation)
                priority_scores.append(2)

            # Recommendation 4: Forecast-based planning
            ensemble_forecast = forecasts.get("ensemble_forecast", {})
            if ensemble_forecast and "values" in ensemble_forecast:
                projected_cost = sum(ensemble_forecast["values"])
                current_monthly_avg = trend_metrics.get("average_cost", 0) * 30

                if projected_cost > current_monthly_avg * 1.2:  # 20% increase projected
                    recommendation = {
                        "type": "budget_planning",
                        "priority": "medium",
                        "title": "Adjust Budget Planning",
                        "description": f"Forecast shows {((projected_cost / current_monthly_avg - 1) * 100):.1f}% cost increase",
                        "actions": [
                            "Increase monthly budget allocation",
                            "Negotiate better pricing with service providers",
                            "Implement cost caps and automatic scaling limits",
                            "Plan for seasonal cost variations",
                        ],
                        "estimated_savings": 0,  # This is more about planning
                        "impact": "Prevent budget shortfalls and enable proactive cost management",
                    }
                    recommendations.append(recommendation)
                    priority_scores.append(2)

            # Recommendation 5: Service-specific optimization
            service_recommendations = self._generate_service_specific_recommendations(
                analysis_results
            )
            recommendations.extend(service_recommendations)
            priority_scores.extend(
                [1] * len(service_recommendations)
            )  # Lower priority for service-specific

            # Sort recommendations by priority
            sorted_recommendations = [
                rec
                for _, rec in sorted(
                    zip(priority_scores, recommendations),
                    key=lambda x: x[0],
                    reverse=True,
                )
            ]

            # Calculate total potential savings
            total_savings = sum(
                rec.get("estimated_savings", 0) for rec in recommendations
            )

            return {
                "total_recommendations": len(recommendations),
                "total_estimated_savings": total_savings,
                "recommendations": sorted_recommendations[
                    :10
                ],  # Top 10 recommendations
                "priority_distribution": {
                    "high": len([p for p in priority_scores if p == 3]),
                    "medium": len([p for p in priority_scores if p == 2]),
                    "low": len([p for p in priority_scores if p == 1]),
                },
                "analysis_summary": {
                    "trend_direction": trend_direction,
                    "volatility_level": volatility_level,
                    "anomaly_count": len(anomalies),
                    "forecast_confidence": forecasts.get("confidence_level", 0),
                },
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(f"Error generating optimization recommendations: {e}")
            return {"error": str(e)}

    def _generate_service_specific_recommendations(
        self, analysis_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate service-specific optimization recommendations."""
        recommendations = []

        try:
            # This would be enhanced with service-specific analysis
            # For now, provide generic service optimization recommendations

            common_services = ["openai", "semrush", "gpu", "screenshotone"]

            for service in common_services:
                if service == "openai":
                    recommendations.append(
                        {
                            "type": "service_optimization",
                            "service": service,
                            "priority": "low",
                            "title": f"Optimize {service.title()} Usage",
                            "description": "Optimize AI model usage and prompting",
                            "actions": [
                                "Use more efficient models where appropriate",
                                "Implement prompt caching",
                                "Optimize token usage in prompts",
                                "Consider batch processing for similar requests",
                            ],
                            "estimated_savings": 0,  # Would need service-specific analysis
                            "impact": "Reduce AI processing costs while maintaining quality",
                        }
                    )
                elif service == "semrush":
                    recommendations.append(
                        {
                            "type": "service_optimization",
                            "service": service,
                            "priority": "low",
                            "title": f"Optimize {service.title()} API Usage",
                            "description": "Optimize SEO data retrieval patterns",
                            "actions": [
                                "Cache frequently requested data",
                                "Implement intelligent data freshness checks",
                                "Use bulk API endpoints where available",
                                "Optimize query parameters to reduce cost",
                            ],
                            "estimated_savings": 0,
                            "impact": "Reduce SEO data costs through efficient querying",
                        }
                    )

            return recommendations

        except Exception as e:
            self.logger.error(f"Error generating service-specific recommendations: {e}")
            return []


# Create global instance
cost_analytics_engine = CostAnalyticsEngine()
