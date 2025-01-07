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

