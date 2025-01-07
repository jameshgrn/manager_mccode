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
- **Privacy-First**: All data stays local in DuckDB, with configurable retention
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
poetry run python -m manager_mccode
```

View recent activity:
```bash
poetry run python -m manager_mccode inspect
```

Install as system service:
```bash
poetry run python -m manager_mccode install
```

## Architecture

- **Core Services**:
  - `ImageManager`: Screenshot capture and optimization
  - `GeminiAnalyzer`: AI-powered activity analysis
  - `BatchProcessor`: Efficient batch processing of screenshots
  - `DatabaseManager`: Local data storage with DuckDB
  - `TerminalDisplay`: Real-time activity visualization

## Roadmap

- [ ] Web interface for activity insights
- [ ] Task detection and workflow analysis
- [ ] Focus metrics and productivity patterns
- [ ] Integration with task management tools
- [ ] Customizable attention state detection
- [ ] Export and visualization options

## Improvement Checklist

### 1. Core Service Stability
- [ ] Add graceful shutdown handling in `ServiceRunner`
- [ ] Implement proper error recovery in batch processing
- [ ] Add health check endpoints for service monitoring
- [ ] Implement proper cleanup of temporary files
- [ ] Add service state persistence across restarts

### 2. Configuration Management
- [ ] Consolidate settings between `config.py` and `settings.py`
- [ ] Add configuration validation for all settings
- [ ] Implement environment-specific configs (dev/prod)
- [ ] Add dynamic config reloading
- [ ] Document all configuration options

### 3. Performance Optimization
- [ ] Implement screenshot compression optimization
- [ ] Add batch processing queue management
- [ ] Optimize database queries and indexing
- [ ] Add caching for frequently accessed data
- [ ] Implement resource usage monitoring

### 4. Data Management
- [ ] Add data export functionality
- [ ] Implement data retention policies
- [ ] Add database backup/restore functionality
- [ ] Implement data migration tools
- [ ] Add data anonymization options

### 5. Error Handling & Logging
- [ ] Improve error classification and handling
- [ ] Add structured logging
- [ ] Implement log rotation
- [ ] Add error reporting metrics
- [ ] Implement debug mode logging

### 6. Security
- [ ] Add screenshot data encryption
- [ ] Implement secure configuration storage
- [ ] Add access control for web interface
- [ ] Implement API authentication
- [ ] Add security audit logging

### 7. User Experience
- [ ] Add progress indicators for long operations
- [ ] Improve CLI feedback and formatting
- [ ] Add interactive configuration wizard
- [ ] Implement user notifications
- [ ] Add command auto-completion

### 8. Testing & Quality
- [ ] Add integration tests for web interface
- [ ] Implement performance benchmarks
- [ ] Add stress testing scenarios
- [ ] Improve test coverage
- [ ] Add property-based testing

### 9. Documentation
- [ ] Add API documentation
- [ ] Create user guide
- [ ] Add configuration reference
- [ ] Document troubleshooting steps
- [ ] Add development setup guide

### 10. Feature Implementation
- [ ] Complete web interface implementation
- [ ] Add focus session analytics
- [ ] Implement task categorization
- [ ] Add productivity metrics
- [ ] Implement report generation

### 11. System Integration
- [ ] Add systemd service management
- [ ] Implement macOS service integration
- [ ] Add Docker support
- [ ] Implement CI/CD pipeline
- [ ] Add monitoring integration

## Contributing

Contributions welcome! Please check out our [contributing guidelines](CONTRIBUTING.md).

## License

MIT License - See [LICENSE](LICENSE) for details

## Configuration

Key settings in `.env`:
```bash
GEMINI_API_KEY=your_api_key_here
SCREENSHOT_INTERVAL_SECONDS=10  # Default screenshot interval
DEFAULT_BATCH_SIZE=12          # Number of screenshots to process together
DEFAULT_BATCH_INTERVAL_SECONDS=120  # How often to run batch processing
```

## Development Setup

1. Set up development environment:
```bash
poetry install --with dev
pre-commit install
```

2. Run tests:
```bash
poetry run pytest
```

3. Format code:
```bash
poetry run black .
poetry run isort .
```

## Project Structure

```
manager_mccode/
├── cli/            # Command-line interface tools
├── config/         # Configuration management
├── models/         # Data models and schemas
├── services/       # Core service modules
│   ├── analyzer.py   # Gemini Vision integration
│   ├── batch.py      # Batch processing
│   ├── database.py   # Data persistence
│   ├── display.py    # Terminal UI
│   └── image.py      # Screenshot management
├── web/            # Web interface (planned)
└── main.py         # Application entry point
```

