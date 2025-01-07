// Chart configurations and data handling
const charts = {
    hourlyActivity: null,
    focusDistribution: null
};

// Initialize charts when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeCharts();
    setupDatePicker();
    loadDailyData(document.getElementById('dateSelect').value);
});

function initializeCharts() {
    // Hourly activity chart
    const hourlyCtx = document.getElementById('hourlyActivityChart').getContext('2d');
    charts.hourlyActivity = new Chart(hourlyCtx, {
        type: 'line',
        data: {
            labels: Array.from({length: 24}, (_, i) => `${i}:00`),
            datasets: [{
                label: 'Focus Score',
                data: [],
                borderColor: '#3498db',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Hourly Activity Pattern'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });

    // Focus distribution chart
    const focusCtx = document.getElementById('focusDistributionChart').getContext('2d');
    charts.focusDistribution = new Chart(focusCtx, {
        type: 'doughnut',
        data: {
            labels: ['Focused', 'Neutral', 'Scattered'],
            datasets: [{
                data: [],
                backgroundColor: ['#2ecc71', '#f1c40f', '#e74c3c']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Focus Distribution'
                }
            }
        }
    });
}

function setupDatePicker() {
    const datePicker = document.getElementById('dateSelect');
    datePicker.addEventListener('change', (e) => {
        loadDailyData(e.target.value);
    });
}

async function loadDailyData(date) {
    try {
        const response = await fetch(`/api/metrics/daily/${date}`);
        if (!response.ok) throw new Error('Failed to fetch metrics');
        
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.error('Error loading metrics:', error);
        showError('Failed to load metrics data');
    }
}

function updateDashboard(data) {
    // Update metric cards
    document.getElementById('focusScore').textContent = 
        (data.summary.focus_score || 0).toFixed(1);
    document.getElementById('activeHours').textContent = 
        (data.summary.active_hours || 0).toFixed(1);
    document.getElementById('contextSwitches').textContent = 
        data.summary.context_switches || 0;

    // Update hourly activity chart
    updateHourlyChart(data.hourly_patterns);

    // Update focus distribution chart
    updateFocusChart(data.focus_states);

    // Update activity list
    updateActivityList(data.activities);
}

function updateHourlyChart(hourlyData) {
    const hours = Array.from({length: 24}, (_, i) => i);
    const focusScores = hours.map(hour => hourlyData[hour]?.focus_score || 0);

    charts.hourlyActivity.data.datasets[0].data = focusScores;
    charts.hourlyActivity.update();
}

function updateFocusChart(focusData) {
    const data = [
        focusData.focused || 0,
        focusData.neutral || 0,
        focusData.scattered || 0
    ];

    charts.focusDistribution.data.datasets[0].data = data;
    charts.focusDistribution.update();
}

function updateActivityList(activities) {
    const container = document.getElementById('activityList');
    container.innerHTML = '';

    Object.entries(activities.categories || {}).forEach(([category, count]) => {
        const item = document.createElement('div');
        item.className = 'activity-item';
        item.innerHTML = `
            <span class="activity-name">${category}</span>
            <span class="activity-duration">${count}</span>
        `;
        container.appendChild(item);
    });
}

function showError(message) {
    // TODO: Implement error toast/notification
    console.error(message);
} 