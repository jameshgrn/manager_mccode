# Manager McCode 🤖

An ADHD-friendly productivity tracker that uses AI vision to help you understand and optimize your work patterns.

## Mission

Manager McCode serves as your attentive productivity assistant, designed specifically for people with ADHD. It:

- 📸 Captures your screen activity unobtrusively
- 🧠 Uses Gemini Vision AI to understand your work context
- 📊 Provides real-time insights about focus and task transitions
- 📝 Generates daily summaries of your productivity patterns

## Features

- **Intelligent Activity Tracking**: Takes periodic screenshots and uses Gemini 1.5 Vision API to analyze work patterns
- **ADHD-Aware Analysis**: Recognizes context switching, focus states, and task transitions
- **Privacy-First**: All data stays local in SQLite, with configurable retention
- **Real-Time Insights**: Shows 15-minute activity summaries in your terminal
- **Daily Reports**: Generates end-of-day summaries of productivity patterns

## Installation

1. Clone the repository
2. Install Poetry (Python package manager)
3. Install dependencies:
```bash
poetry install
```
4. Set up your environment variables:
```bash
cp .env.example .env
# Add your Gemini API key to .env
```

## Usage

Start tracking:
```bash
poetry run mccode start
```

View recent activity:
```bash
poetry run mccode inspect
```

Install as system service:
```bash
poetry run mccode install
```

## Architecture

### Core Services
- **ImageManager**: Screenshot capture and optimization
- **BatchProcessor**: Efficient batch processing with Gemini Vision
- **GeminiAnalyzer**: AI-powered activity analysis
- **TaskDetector**: Context and focus state detection
- **DatabaseManager**: Local data persistence
- **MetricsCollector**: Focus and productivity analytics
- **TerminalDisplay**: Real-time activity visualization

### Data Models
- **ScreenSummary**: Activity snapshots and analysis
- **FocusSession**: Focus state tracking
- **Activity**: Task and application tracking
- **Context**: Work environment analysis

## Improvement Checklist

### 1. Core Service Stability 🚧
- [x] Add graceful shutdown handling in `ServiceRunner`
- [x] Implement proper error recovery in batch processing
- [ ] Add health check endpoints for service monitoring
- [x] Implement proper cleanup of temporary files
- [ ] Add service state persistence across restarts

### 2. Configuration Management 🚧
- [ ] Consolidate settings between `config.py` and `settings.py`
- [x] Add configuration validation for all settings
- [ ] Implement environment-specific configs (dev/prod)
- [ ] Add dynamic config reloading
- [ ] Document all configuration options

### 3. Performance Optimization ✅
- [x] Implement screenshot compression optimization
  - [x] JPEG format for better compression
  - [x] Configurable quality settings
  - [x] Automatic image resizing
  - [x] Memory-efficient processing
- [x] Add batch processing queue management
- [x] Optimize database queries and indexing
- [x] Add caching for frequently accessed data
- [x] Implement resource usage monitoring

### 4. Data Management 🚧
- [ ] Add data export functionality
- [x] Implement data retention policies
- [ ] Add database backup/restore functionality
- [ ] Implement data migration tools
- [ ] Add data anonymization options

### 5. Error Handling & Logging 🚧
- [x] Improve error classification and handling
- [x] Add structured logging
- [ ] Implement log rotation
- [ ] Add error reporting metrics
- [ ] Implement debug mode logging

### 6. User Experience 🚧
- [x] Add real-time activity feedback
- [x] Implement customizable focus metrics
- [ ] Add detailed activity reports
- [ ] Improve notification system
- [ ] Add user preferences management

### 7. Testing & Quality 🚧
- [x] Add integration tests for core services
- [ ] Add integration tests for web interface
- [ ] Implement performance benchmarks
- [ ] Add stress testing scenarios
- [x] Add property-based testing

### 8. Documentation 📝
- [ ] Add API documentation
- [ ] Create user guide
- [ ] Add configuration reference
- [ ] Document troubleshooting steps
- [ ] Add development setup guide

### 9. Feature Implementation 🚧
- [ ] Complete web interface implementation
- [x] Add focus session analytics
- [x] Implement task categorization
- [x] Add productivity metrics
- [ ] Implement report generation

### 10. System Integration ✅
- [x] Add systemd service management
- [x] Implement macOS service integration
- [ ] Add Docker support
- [ ] Implement CI/CD pipeline
- [ ] Add monitoring integration

## Project Structure
```
manager_mccode/
├── cli/            # Command-line interface
├── config/         # Configuration management
├── models/         # Data models
├── services/       # Core business logic
│   ├── analyzer.py   # Gemini Vision integration
│   ├── batch.py      # Batch processing
│   ├── database.py   # Data persistence
│   ├── display.py    # Terminal UI
│   ├── image.py      # Screenshot management
│   ├── metrics.py    # Analytics
│   ├── runner.py     # Service lifecycle
│   └── task_detector.py  # Context detection
└── web/            # Web interface
```

## Configuration

Key settings in `.env`:
```bash
GEMINI_API_KEY=your_api_key_here
SCREENSHOT_INTERVAL_SECONDS=10
DEFAULT_BATCH_SIZE=12
DEFAULT_BATCH_INTERVAL_SECONDS=120
```

## Development

1. Set up development environment:
```bash
poetry install --with dev
```

2. Run tests:
```bash
poetry run pytest
```

## Contributing

Contributions welcome! Please check out our [contributing guidelines](CONTRIBUTING.md).

## License

MIT License - See [LICENSE](LICENSE) for details

