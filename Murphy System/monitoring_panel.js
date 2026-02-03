/**
 * Murphy System - Monitoring Panel
 * Displays system health, performance metrics, anomalies, and optimization recommendations
 */

class MonitoringPanel {
    constructor() {
        this.healthData = null;
        this.metricsData = [];
        this.anomaliesData = [];
        this.recommendationsData = [];
        this.alertsData = [];
        this.refreshInterval = null;
        this.init();
    }

    init() {
        console.log('Initializing Monitoring Panel...');
        this.loadInitialData();
        this.startAutoRefresh();
    }

    async loadInitialData() {
        try {
            await Promise.all([
                this.loadHealth(),
                this.loadMetrics(),
                this.loadAnomalies(),
                this.loadRecommendations(),
                this.loadAlerts()
            ]);
            this.render();
        } catch (error) {
            console.error('Error loading monitoring data:', error);
            this.showError('Failed to load monitoring data');
        }
    }

    async loadHealth() {
        try {
            const response = await fetch('http://localhost:3002/api/monitoring/health');
            if (!response.ok) throw new Error('Failed to load health data');
            this.healthData = await response.json();
        } catch (error) {
            console.error('Error loading health data:', error);
            this.healthData = null;
        }
    }

    async loadMetrics() {
        try {
            const response = await fetch('http://localhost:3002/api/monitoring/metrics?limit=50');
            if (!response.ok) throw new Error('Failed to load metrics');
            const data = await response.json();
            this.metricsData = data.metrics || [];
        } catch (error) {
            console.error('Error loading metrics:', error);
            this.metricsData = [];
        }
    }

    async loadAnomalies() {
        try {
            const response = await fetch('http://localhost:3002/api/monitoring/anomalies');
            if (!response.ok) throw new Error('Failed to load anomalies');
            const data = await response.json();
            this.anomaliesData = data.anomalies || [];
        } catch (error) {
            console.error('Error loading anomalies:', error);
            this.anomaliesData = [];
        }
    }

    async loadRecommendations() {
        try {
            const response = await fetch('http://localhost:3002/api/monitoring/recommendations');
            if (!response.ok) throw new Error('Failed to load recommendations');
            const data = await response.json();
            this.recommendationsData = data.recommendations || [];
        } catch (error) {
            console.error('Error loading recommendations:', error);
            this.recommendationsData = [];
        }
    }

    async loadAlerts() {
        try {
            const response = await fetch('http://localhost:3002/api/monitoring/alerts');
            if (!response.ok) throw new Error('Failed to load alerts');
            const data = await response.json();
            this.alertsData = data.alerts || [];
        } catch (error) {
            console.error('Error loading alerts:', error);
            this.alertsData = [];
        }
    }

    startAutoRefresh() {
        // Refresh every 15 seconds
        this.refreshInterval = setInterval(() => {
            this.loadInitialData();
        }, 15000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    render() {
        this.renderHealthOverview();
        this.renderComponentStatus();
        this.renderMetrics();
        this.renderAnomalies();
        this.renderRecommendations();
        this.renderAlerts();
    }

    renderHealthOverview() {
        const container = document.getElementById('monitoring-health-overview');
        if (!container || !this.healthData) return;

        const overall = this.healthData.overall;
        const healthClass = overall.status;
        const healthColor = this.getHealthColor(overall.status);

        container.innerHTML = `
            <div class="health-score-container">
                <div class="health-score ${healthClass}">
                    <span class="score-value">${overall.score}</span>
                    <span class="score-label">Health Score</span>
                </div>
                <div class="health-status">
                    <h3 class="${healthClass}">${overall.message}</h3>
                    <p>${overall.components.total} components monitored</p>
                </div>
            </div>
            <div class="health-breakdown">
                <div class="health-breakdown-item healthy">
                    <span class="count">${overall.components.healthy}</span>
                    <span class="label">Healthy</span>
                </div>
                <div class="health-breakdown-item degraded">
                    <span class="count">${overall.components.degraded}</span>
                    <span class="label">Degraded</span>
                </div>
                <div class="health-breakdown-item unhealthy">
                    <span class="count">${overall.components.unhealthy}</span>
                    <span class="label">Unhealthy</span>
                </div>
            </div>
        `;
    }

    renderComponentStatus() {
        const container = document.getElementById('monitoring-component-status');
        if (!container || !this.healthData) return;

        container.innerHTML = Object.entries(this.healthData.components).map(([name, component]) => {
            const statusClass = component.status;
            const statusIcon = this.getStatusIcon(component.status);
            
            return `
                <div class="component-item ${statusClass}">
                    <div class="component-header">
                        <span class="component-icon">${statusIcon}</span>
                        <div class="component-info">
                            <h4 class="component-name">${this.formatComponentName(name)}</h4>
                            <span class="component-status">${component.status}</span>
                        </div>
                    </div>
                    <p class="component-message">${component.message}</p>
                    ${this.renderComponentDetails(component.details)}
                </div>
            `;
        }).join('');
    }

    renderComponentDetails(details) {
        if (!details || Object.keys(details).length === 0) return '';

        return `
            <div class="component-details">
                ${Object.entries(details).map(([key, value]) => `
                    <div class="detail-item">
                        <span class="detail-key">${this.formatKey(key)}:</span>
                        <span class="detail-value">${this.formatValue(value)}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    renderMetrics() {
        const container = document.getElementById('monitoring-metrics');
        if (!container) return;

        // Group metrics by name
        const groupedMetrics = {};
        this.metricsData.forEach(metric => {
            if (!groupedMetrics[metric.name]) {
                groupedMetrics[metric.name] = [];
            }
            groupedMetrics[metric.name].push(metric);
        });

        container.innerHTML = Object.entries(groupedMetrics).map(([name, metrics]) => {
            const latest = metrics[metrics.length - 1];
            const values = metrics.map(m => m.value);
            const avg = values.reduce((a, b) => a + b, 0) / values.length;
            const min = Math.min(...values);
            const max = Math.max(...values);

            return `
                <div class="metric-card">
                    <div class="metric-header">
                        <h4 class="metric-name">${this.formatMetricName(name)}</h4>
                        <span class="metric-value">${latest.value.toFixed(2)} ${latest.unit}</span>
                    </div>
                    <div class="metric-stats">
                        <span class="stat">Avg: ${avg.toFixed(2)}</span>
                        <span class="stat">Min: ${min.toFixed(2)}</span>
                        <span class="stat">Max: ${max.toFixed(2)}</span>
                    </div>
                    <div class="metric-chart">
                        ${this.renderMiniChart(values)}
                    </div>
                </div>
            `;
        }).join('');
    }

    renderMiniChart(values) {
        if (values.length < 2) return '<span class="no-chart">Insufficient data</span>';

        const max = Math.max(...values);
        const min = Math.min(...values);
        const range = max - min || 1;

        const bars = values.slice(-20).map((value, index) => {
            const height = ((value - min) / range) * 100;
            return `<div class="chart-bar" style="height: ${height}%" title="${value.toFixed(2)}"></div>`;
        }).join('');

        return `<div class="mini-chart">${bars}</div>`;
    }

    renderAnomalies() {
        const container = document.getElementById('monitoring-anomalies');
        if (!container) return;

        if (this.anomaliesData.length === 0) {
            container.innerHTML = '<div class="no-data">No anomalies detected</div>';
            return;
        }

        container.innerHTML = this.anomaliesData.slice(0, 20).map(anomaly => `
            <div class="anomaly-item ${anomaly.severity}">
                <div class="anomaly-header">
                    <span class="anomaly-type">${anomaly.type}</span>
                    <span class="anomaly-severity ${anomaly.severity}">${anomaly.severity}</span>
                </div>
                <div class="anomaly-content">
                    <h4 class="anomaly-title">${anomaly.metric_name}</h4>
                    <p class="anomaly-description">${anomaly.description}</p>
                </div>
                <div class="anomaly-footer">
                    <span class="anomaly-value">Value: ${anomaly.value.toFixed(2)}</span>
                    <span class="anomaly-time">${this.formatTime(anomaly.timestamp)}</span>
                </div>
            </div>
        `).join('');
    }

    renderRecommendations() {
        const container = document.getElementById('monitoring-recommendations');
        if (!container) return;

        if (this.recommendationsData.length === 0) {
            container.innerHTML = '<div class="no-data">No recommendations available</div>';
            return;
        }

        container.innerHTML = this.recommendationsData.slice(0, 10).map(rec => `
            <div class="recommendation-item ${rec.priority}">
                <div class="recommendation-header">
                    <span class="recommendation-category">${rec.category}</span>
                    <span class="recommendation-priority ${rec.priority}">${rec.priority}</span>
                </div>
                <div class="recommendation-content">
                    <h4 class="recommendation-title">${rec.title}</h4>
                    <p class="recommendation-description">${rec.description}</p>
                    <p class="recommendation-impact">Expected Impact: ${rec.expected_impact}</p>
                </div>
                <div class="recommendation-actions">
                    <button class="btn btn-sm btn-primary" onclick="monitoringPanel.implementRecommendation('${rec.id}')">
                        ✓ Implement
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="monitoringPanel.dismissRecommendation('${rec.id}')">
                        Dismiss
                    </button>
                </div>
            </div>
        `).join('');
    }

    renderAlerts() {
        const container = document.getElementById('monitoring-alerts');
        if (!container) return;

        if (this.alertsData.length === 0) {
            container.innerHTML = '<div class="no-data">No active alerts</div>';
            return;
        }

        container.innerHTML = this.alertsData.map(alert => `
            <div class="alert-item ${alert.severity}">
                <div class="alert-icon">${this.getSeverityIcon(alert.severity)}</div>
                <div class="alert-content">
                    <h4 class="alert-title">${alert.metric_name}</h4>
                    <p class="alert-description">${alert.description}</p>
                    <span class="alert-time">${this.formatTime(alert.timestamp)}</span>
                </div>
                <div class="alert-actions">
                    <button class="btn btn-sm btn-warning" onclick="monitoringPanel.dismissAlert('${alert.id}')">
                        Dismiss
                    </button>
                </div>
            </div>
        `).join('');
    }

    async runAnalysis() {
        try {
            const response = await fetch('http://localhost:3002/api/monitoring/analyze', {
                method: 'POST'
            });
            if (!response.ok) throw new Error('Analysis failed');
            
            const result = await response.json();
            this.showSuccess(`Analysis complete: ${result.anomalies_detected} anomalies, ${result.recommendations_generated} recommendations`);
            
            // Reload data
            await this.loadInitialData();
        } catch (error) {
            console.error('Error running analysis:', error);
            this.showError('Failed to run analysis');
        }
    }

    async dismissAlert(alertId) {
        try {
            const response = await fetch(`http://localhost:3002/api/monitoring/alerts/${alertId}/dismiss`, {
                method: 'POST'
            });
            if (!response.ok) throw new Error('Failed to dismiss alert');
            
            await this.loadAlerts();
            this.render();
            this.showSuccess('Alert dismissed');
        } catch (error) {
            console.error('Error dismissing alert:', error);
            this.showError('Failed to dismiss alert');
        }
    }

    async implementRecommendation(recId) {
        try {
            const response = await fetch(`http://localhost:3002/api/monitoring/recommendations/${recId}/implement`, {
                method: 'POST'
            });
            if (!response.ok) throw new Error('Failed to implement recommendation');
            
            await this.loadRecommendations();
            this.render();
            this.showSuccess('Recommendation implemented');
        } catch (error) {
            console.error('Error implementing recommendation:', error);
            this.showError('Failed to implement recommendation');
        }
    }

    async dismissRecommendation(recId) {
        try {
            const response = await fetch(`http://localhost:3002/api/monitoring/recommendations/${recId}/dismiss`, {
                method: 'POST'
            });
            if (!response.ok) throw new Error('Failed to dismiss recommendation');
            
            await this.loadRecommendations();
            this.render();
            this.showSuccess('Recommendation dismissed');
        } catch (error) {
            console.error('Error dismissing recommendation:', error);
            this.showError('Failed to dismiss recommendation');
        }
    }

    // Utility methods
    getHealthColor(status) {
        const colors = {
            'healthy': '#28a745',
            'degraded': '#ffc107',
            'unhealthy': '#dc3545',
            'unknown': '#6c757d'
        };
        return colors[status] || '#6c757d';
    }

    getStatusIcon(status) {
        const icons = {
            'healthy': '✓',
            'degraded': '⚠',
            'unhealthy': '✗',
            'unknown': '?'
        };
        return icons[status] || '?';
    }

    getSeverityIcon(severity) {
        const icons = {
            'low': '⚡',
            'medium': '⚠',
            'high': '🔴',
            'critical': '🚨'
        };
        return icons[severity] || '⚡';
    }

    formatComponentName(name) {
        return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    formatMetricName(name) {
        return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    formatKey(key) {
        return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    formatValue(value) {
        if (typeof value === 'object') {
            return JSON.stringify(value);
        }
        if (typeof value === 'number' && value > 1000) {
            return (value / 1000).toFixed(2) + 'k';
        }
        return String(value);
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return date.toLocaleDateString();
    }

    // Notification methods
    showSuccess(message) {
        if (window.addTerminalLog) {
            window.addTerminalLog(`✓ ${message}`, 'success');
        }
    }

    showError(message) {
        if (window.addTerminalLog) {
            window.addTerminalLog(`✗ ${message}`, 'error');
        }
    }

    showInfo(message) {
        if (window.addTerminalLog) {
            window.addTerminalLog(`ℹ ${message}`, 'info');
        }
    }
}

// Global instance
let monitoringPanel = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    monitoringPanel = new MonitoringPanel();
});