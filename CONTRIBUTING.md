# Contributing to Dynamic Network Model

Thank you for your interest in contributing to the Sisyphean Power & Light Dynamic Network Model! This project aims to provide a realistic, open-source distribution utility dataset for ML/AI development in the power systems domain.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Getting Started](#getting-started)
- [Contribution Workflow](#contribution-workflow)
- [Contribution Guidelines](#contribution-guidelines)
- [Style Guidelines](#style-guidelines)
- [Community](#community)

## Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow. Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before contributing.

## How Can I Contribute?

### Types of Contributions We Welcome

1. **Data Quality Improvements**
   - Fix errors in synthetic datasets
   - Improve realism of load profiles, outage patterns, or asset data
   - Add missing metadata or documentation

2. **New Datasets or Scenarios**
   - Additional DER penetration scenarios
   - New feeder topologies
   - Extended time-series data
   - Additional failure modes or weather events

3. **Analysis Notebooks**
   - New use case examples (load forecasting, outage prediction, etc.)
   - Improved ML models or techniques
   - Visualization and exploratory analysis
   - Documentation of methodology

4. **Code Improvements**
   - Bug fixes in existing notebooks
   - Performance optimizations
   - Better error handling
   - Improved data validation scripts

5. **Documentation**
   - Improve README or guides
   - Add data dictionaries
   - Expand use case descriptions
   - Fix typos or clarify explanations

6. **Testing & Validation**
   - Data integrity checks
   - Unit tests for processing scripts
   - Validation against IEEE standards
   - Cross-check calculations

## Getting Started

### Prerequisites

- Git installed on your machine
- Python 3.8+ (for running notebooks)
- Familiarity with power systems engineering OR machine learning (ideally both!)

### Initial Setup

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/Dynamic-Network-Model.git
   cd Dynamic-Network-Model
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/SGridworks/Dynamic-Network-Model.git
   ```
4. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt  # If available
   ```

## Contribution Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

Use descriptive branch names:
- `feature/add-voltage-analysis-notebook`
- `fix/outage-data-timestamps`
- `docs/improve-readme`
- `data/add-ev-charging-scenario`

### 2. Make Your Changes

- Write clear, concise code with comments
- Follow existing code style and conventions
- Test your changes thoroughly
- Update documentation as needed

### 3. Commit Your Changes

```bash
git add .
git commit -m "Add detailed description of your changes"
```

**Good commit messages:**
- "Add LSTM load forecasting notebook with example"
- "Fix timestamp formatting in outage_events.csv"
- "Update README with new DER scenario documentation"

**Bad commit messages:**
- "Update"
- "Fix stuff"
- "WIP"

### 4. Push to Your Fork

```bash
git push origin feature/your-feature-name
```

### 5. Open a Pull Request

1. Go to the [Dynamic Network Model repository](https://github.com/SGridworks/Dynamic-Network-Model)
2. Click "Pull Requests" → "New Pull Request"
3. Select your fork and branch
4. Fill out the PR template with:
   - Clear description of changes
   - Motivation/context
   - Testing performed
   - Screenshots (if applicable)

### 6. Address Review Feedback

- Respond to comments and questions
- Make requested changes
- Push updates to your branch (PR will auto-update)
- Request re-review when ready

## Contribution Guidelines

### Data Contributions

- **Maintain synthetic nature**: All data must be fictional/synthetic, not real utility data
- **Document sources**: Cite methodology, benchmarks, or standards used
- **Preserve realism**: Changes should reflect real-world distribution systems
- **File formats**: Use Parquet for large time-series, CSV for smaller datasets
- **Validate schema**: Ensure new data matches existing column names and types

### Code Contributions

- **Jupyter notebooks**:
  - Clear markdown cells explaining methodology
  - Code cells with comments for complex logic
  - Include sample outputs (don't clear output before committing)
  - Add requirements at the top (imports needed)

- **Python scripts**:
  - Follow PEP 8 style guide
  - Include docstrings for functions
  - Add type hints where helpful
  - Handle errors gracefully

### Documentation

- Use clear, concise language
- Include examples where helpful
- Update table of contents if adding sections
- Spell-check before submitting

### What NOT to Contribute

- Real utility data (CEII violations)
- Large binary files without approval (>10MB)
- Proprietary software or licensed code
- Spam, promotional content, or off-topic material

## Style Guidelines

### Python Code Style

- Follow [PEP 8](https://pep8.org/)
- Use meaningful variable names (e.g., `feeder_load` not `fl`)
- Keep functions focused and under 50 lines when possible
- Add comments for non-obvious logic

### Data File Naming

- Use lowercase with underscores: `substation_load_hourly.parquet`
- Include units in column names: `temperature_f`, `load_kw`
- Use ISO 8601 for timestamps: `2025-01-15 14:30:00`

### Documentation Style

- Use Markdown formatting
- Include code examples in triple backticks with language specified
- Link to related sections or external resources
- Keep line length under 120 characters

## Testing Your Changes

Before submitting:

1. **Run the code**: Ensure notebooks execute without errors
2. **Check data integrity**: Validate CSV/Parquet files load correctly
3. **Verify documentation**: Preview Markdown rendering
4. **Test edge cases**: Consider boundary conditions

## Community

### Getting Help

- **Questions**: Open a [GitHub Discussion](https://github.com/SGridworks/Dynamic-Network-Model/discussions)
- **Bugs**: Open a [GitHub Issue](https://github.com/SGridworks/Dynamic-Network-Model/issues)
- **Email**: Contact [adam@sgridworks.com](mailto:adam@sgridworks.com)

### Recognition

Contributors will be acknowledged in:
- Release notes
- README contributors section
- Git commit history

Significant contributions may be featured on the Sisyphean Gridworks website.

## Questions?

Don't hesitate to ask! We're here to help:
- Open a GitHub Discussion for general questions
- Comment on the relevant Issue or PR
- Email adam@sgridworks.com

Thank you for contributing to making grid analytics more accessible! 🔌⚡
