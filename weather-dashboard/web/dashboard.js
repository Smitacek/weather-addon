// Weather & Solar Dashboard JavaScript

class WeatherDashboard {
    constructor() {
        this.wsUrl = `ws://${window.location.hostname}:8099/ws`;
        this.ws = null;
        this.reconnectInterval = 5000;
        this.data = {
            current: {},
            hourly: [],
            daily: [],
            solar: {}
        };
        this.init();
    }

    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.updateTime();
        setInterval(() => this.updateTime(), 60000);
    }

    connectWebSocket() {
        try {
            this.ws = new WebSocket(this.wsUrl);
            
            this.ws.onopen = () => {
                console.log('Connected to weather dashboard');
                this.updateConnectionStatus(true);
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleData(data);
                } catch (error) {
                    console.error('Error parsing message:', error);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus(false);
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.updateConnectionStatus(false);
                setTimeout(() => this.connectWebSocket(), this.reconnectInterval);
            };
        } catch (error) {
            console.error('Failed to connect:', error);
            setTimeout(() => this.connectWebSocket(), this.reconnectInterval);
        }
    }

    handleData(data) {
        if (data.type === 'weather_current') {
            this.updateCurrentWeather(data.payload);
        } else if (data.type === 'weather_hourly') {
            this.updateHourlyForecast(data.payload);
        } else if (data.type === 'weather_daily') {
            this.updateDailyForecast(data.payload);
        } else if (data.type === 'solar_data') {
            this.updateSolarData(data.payload);
        }
    }

    updateCurrentWeather(data) {
        // Update current temperature
        const tempElement = document.querySelector('.temperature');
        if (tempElement && data.temperature !== undefined) {
            tempElement.textContent = `${Math.round(data.temperature)}°C`;
        }

        // Update weather icon
        const iconElement = document.querySelector('.weather-icon');
        if (iconElement && data.weather_code !== undefined) {
            iconElement.textContent = this.getWeatherEmoji(data.weather_code);
        }

        // Update weather details
        const details = {
            'Feels Like': `${Math.round(data.apparent_temperature || data.temperature)}°C`,
            'Humidity': `${data.humidity || 0}%`,
            'Wind': `${Math.round(data.wind_speed || 0)} km/h`,
            'Pressure': `${Math.round(data.pressure || 1013)} hPa`
        };

        document.querySelectorAll('.detail-item').forEach(item => {
            const label = item.querySelector('.detail-label').textContent;
            const value = item.querySelector('.detail-value');
            if (details[label] && value) {
                value.textContent = details[label];
            }
        });
    }

    updateHourlyForecast(data) {
        const container = document.getElementById('hourlyForecast');
        if (!container || !data.time || !data.temperature) return;

        container.innerHTML = '';
        const now = new Date();
        const next24Hours = data.time.slice(0, 24);

        next24Hours.forEach((time, index) => {
            const hour = new Date(time);
            const temp = Math.round(data.temperature[index]);
            const weatherCode = data.weather_code ? data.weather_code[index] : 0;
            
            const hourItem = document.createElement('div');
            hourItem.className = 'hour-item';
            hourItem.innerHTML = `
                <div class="hour-time">${hour.getHours().toString().padStart(2, '0')}:00</div>
                <div class="hour-temp">${temp}°</div>
                <div class="hour-rain">${this.getWeatherEmoji(weatherCode)}</div>
            `;
            container.appendChild(hourItem);
        });
    }

    updateDailyForecast(data) {
        const container = document.getElementById('weekForecast');
        if (!container || !data.time) return;

        const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        container.innerHTML = '';

        data.time.slice(0, 7).forEach((date, index) => {
            const day = new Date(date);
            const dayName = days[day.getDay()];
            const maxTemp = Math.round(data.temperature_max[index]);
            const minTemp = Math.round(data.temperature_min[index]);
            const weatherCode = data.weather_code ? data.weather_code[index] : 0;

            const forecastDay = document.createElement('div');
            forecastDay.className = 'forecast-day';
            forecastDay.innerHTML = `
                <div class="forecast-date">${dayName}</div>
                <div class="forecast-icon">${this.getWeatherEmoji(weatherCode)}</div>
                <div class="forecast-temp">
                    <span class="forecast-temp-max">${maxTemp}°</span> / 
                    <span class="forecast-temp-min">${minTemp}°</span>
                </div>
            `;
            container.appendChild(forecastDay);
        });
    }

    updateSolarData(data) {
        // Update PV metrics
        if (data.current_power !== undefined) {
            const element = document.getElementById('pvPower');
            if (element) element.textContent = `${(data.current_power / 1000).toFixed(1)} kW`;
        }

        if (data.today_energy !== undefined) {
            const element = document.getElementById('pvToday');
            if (element) element.textContent = `${data.today_energy.toFixed(1)} kWh`;
        }

        if (data.forecast_today !== undefined) {
            const element = document.getElementById('pvForecast');
            if (element) element.textContent = `${data.forecast_today.toFixed(1)} kWh`;
        }

        // Update solar chart if we have hourly data
        if (data.hourly_production) {
            this.updateSolarChart(data.hourly_production);
        }
    }

    updateSolarChart(hourlyData) {
        const canvas = document.getElementById('productionChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width = canvas.offsetWidth;
        const height = canvas.height = canvas.offsetHeight - 30;

        // Clear canvas
        ctx.clearRect(0, 0, width, height);

        if (!hourlyData || hourlyData.length === 0) return;

        // Find max value for scaling
        const maxValue = Math.max(...hourlyData.map(d => d.power || 0));
        if (maxValue === 0) return;

        // Draw chart
        ctx.strokeStyle = '#667eea';
        ctx.lineWidth = 2;
        ctx.beginPath();

        const barWidth = width / hourlyData.length;
        
        hourlyData.forEach((data, index) => {
            const x = index * barWidth;
            const y = height - (data.power / maxValue) * (height - 10);
            
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });

        ctx.stroke();

        // Fill area under the curve
        ctx.lineTo(width, height);
        ctx.lineTo(0, height);
        ctx.closePath();
        ctx.fillStyle = 'rgba(102, 126, 234, 0.1)';
        ctx.fill();
    }

    getWeatherEmoji(code) {
        // WMO Weather codes to emoji mapping
        const weatherMap = {
            0: '☀️',  // Clear sky
            1: '🌤️',  // Mainly clear
            2: '⛅',  // Partly cloudy
            3: '☁️',  // Overcast
            45: '🌫️', // Foggy
            48: '🌫️', // Depositing rime fog
            51: '🌦️', // Light drizzle
            53: '🌦️', // Moderate drizzle
            55: '🌦️', // Dense drizzle
            61: '🌧️', // Slight rain
            63: '🌧️', // Moderate rain
            65: '🌧️', // Heavy rain
            71: '🌨️', // Slight snow
            73: '🌨️', // Moderate snow
            75: '🌨️', // Heavy snow
            77: '❄️',  // Snow grains
            80: '🌦️', // Slight rain showers
            81: '🌧️', // Moderate rain showers
            82: '⛈️', // Violent rain showers
            85: '🌨️', // Slight snow showers
            86: '🌨️', // Heavy snow showers
            95: '⛈️', // Thunderstorm
            96: '⛈️', // Thunderstorm with slight hail
            99: '⛈️'  // Thunderstorm with heavy hail
        };

        return weatherMap[code] || '🌤️';
    }

    updateConnectionStatus(isOnline) {
        const statusElement = document.getElementById('connectionStatus');
        if (statusElement) {
            statusElement.textContent = isOnline ? 'Online' : 'Offline';
            statusElement.className = `status ${isOnline ? 'online' : 'offline'}`;
        }
    }

    updateTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        // You can add a time display element if needed
    }

    setupEventListeners() {
        // Add any interactive elements here
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.ws.readyState !== WebSocket.OPEN) {
                this.connectWebSocket();
            }
        });
    }
}

// Initialize dashboard when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.dashboard = new WeatherDashboard();
    });
} else {
    window.dashboard = new WeatherDashboard();
}