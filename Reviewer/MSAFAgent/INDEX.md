# 📚 Agent Framework Code Reviewer - Documentation Index

Welcome to the Agent Framework Code Reviewer documentation! This index will help you find what you need.

## 🚀 Getting Started (5 minutes)

**New to the project?** Start here:

1. **[QUICKSTART.md](QUICKSTART.md)** - Setup and first review in 5 minutes
2. **[test_integration.py](test_integration.py)** - Run tests to verify setup
3. **[test_agent_framework.py](test_agent_framework.py)** - Interactive testing

## 📖 Core Documentation

### Architecture & Design

- **[README.md](README.md)** - Complete architecture overview
  - System components
  - Workflow diagrams
  - Feature descriptions
  - Comparison with LangGraph
  - Usage examples
- **[COMPARISON.md](COMPARISON.md)** - LangGraph vs Agent Framework
  - Side-by-side code comparison
  - Performance metrics
  - When to use each
  - Migration guide
- **[SUMMARY.md](SUMMARY.md)** - Executive summary
  - What was built
  - Key improvements
  - Statistics
  - Quick reference

### Implementation Files

- **[Agent_framework_agent.py](Agent_framework_agent.py)** - Main implementation
  - ReviewerHandler class
  - Executor implementations
  - Tool definitions
  - Workflow construction
- **[Models/BaseModels.py](Models/BaseModels.py)** - Base classes
  - Model class
  - BaseModelExecutor class

## 🧪 Testing & Examples

### Testing

- **[test_integration.py](test_integration.py)** - Integration test suite

  - Model tests
  - Pydantic validation
  - Git service tests
  - Workflow tests
  - **Run this first to verify setup!**

- **[test_agent_framework.py](test_agent_framework.py)** - Interactive testing
  - Real PR review
  - Mock data testing
  - User-friendly interface

### Examples

- **[example_custom_tools.py](example_custom_tools.py)** - Extensibility demo
  - Custom tool implementation
  - EnhancedReviewTools class
  - Test coverage checker
  - Dependency analyzer
  - Pattern finder

### Visualization

- **[visualize_workflow.py](visualize_workflow.py)** - Workflow visualization
  - Generate diagrams (SVG, PNG, PDF)
  - Print Mermaid code
  - Workflow description

## 🎓 Learning Path

### Beginner

1. Read [QUICKSTART.md](QUICKSTART.md)
2. Run `python test_integration.py`
3. Try mock test: `python test_agent_framework.py` → option 2
4. Review [README.md](README.md) architecture section

### Intermediate

1. Read [COMPARISON.md](COMPARISON.md) to understand design choices
2. Study [Agent_framework_agent.py](Agent_framework_agent.py) implementation
3. Try real PR review with your repo
4. Explore [example_custom_tools.py](example_custom_tools.py)

### Advanced

1. Read [SUMMARY.md](SUMMARY.md) for complete overview
2. Implement custom tools for your domain
3. Modify executors for custom workflows
4. Integrate with CI/CD pipeline

## 📋 Quick Reference

### Common Tasks

| Task                        | File/Command                                       |
| --------------------------- | -------------------------------------------------- |
| **First time setup**        | [QUICKSTART.md](QUICKSTART.md)                     |
| **Run tests**               | `python test_integration.py`                       |
| **Review a PR**             | `python test_agent_framework.py`                   |
| **Understand architecture** | [README.md](README.md)                             |
| **Compare with LangGraph**  | [COMPARISON.md](COMPARISON.md)                     |
| **Add custom tools**        | [example_custom_tools.py](example_custom_tools.py) |
| **Visualize workflow**      | `python visualize_workflow.py`                     |
| **Debug issues**            | [QUICKSTART.md](QUICKSTART.md) → Common Issues     |

### Key Concepts

| Concept               | Where to Learn                                                                  |
| --------------------- | ------------------------------------------------------------------------------- |
| **ReAct Pattern**     | [README.md](README.md) → Key Features                                           |
| **Executors**         | [Agent_framework_agent.py](Agent_framework_agent.py) → ReviewSingleDiffExecutor |
| **Tools**             | [Agent_framework_agent.py](Agent_framework_agent.py) → ReviewTools class        |
| **Structured Output** | [README.md](README.md) → Structured Output                                      |
| **Workflow Building** | [visualize_workflow.py](visualize_workflow.py)                                  |
| **State Management**  | [Agent_framework_agent.py](Agent_framework_agent.py) → ReviewState              |

## 🗂️ File Organization

```
MSAFAgent/
│
├── 📘 Documentation
│   ├── INDEX.md (this file)     - Documentation index
│   ├── README.md                - Complete architecture
│   ├── QUICKSTART.md            - 5-minute setup
│   ├── COMPARISON.md            - LangGraph comparison
│   └── SUMMARY.md               - Executive summary
│
├── 💻 Implementation
│   ├── Agent_framework_agent.py - Main code
│   └── Models/
│       └── BaseModels.py        - Base classes
│
├── 🧪 Testing
│   ├── test_integration.py      - Integration tests
│   └── test_agent_framework.py  - Interactive testing
│
├── 📊 Examples & Tools
│   ├── example_custom_tools.py  - Custom tools demo
│   └── visualize_workflow.py    - Workflow viz
│
└── 📦 Configuration
    └── requirements.txt         - Dependencies
```

## 🎯 Use Cases

### I want to...

- **Get started quickly** → [QUICKSTART.md](QUICKSTART.md)
- **Understand the architecture** → [README.md](README.md)
- **Compare with original** → [COMPARISON.md](COMPARISON.md)
- **See all features** → [SUMMARY.md](SUMMARY.md)
- **Run tests** → `python test_integration.py`
- **Review my PR** → `python test_agent_framework.py`
- **Add custom tools** → [example_custom_tools.py](example_custom_tools.py)
- **Visualize workflow** → `python visualize_workflow.py`
- **Troubleshoot** → [QUICKSTART.md](QUICKSTART.md) → Common Issues
- **Extend the system** → [example_custom_tools.py](example_custom_tools.py)

## 🔍 Key Classes & Functions

### Main Classes

```python
# Handler
ReviewerHandler              # Main orchestrator
  └── run(repo, pr_num)     # Execute review workflow

# Executors
ReviewSingleDiffExecutor     # Reviews all diffs
  └── handle(state, ctx)    # Main review logic

CompleteReviewExecutor       # Summarizes reviews
  └── handle(state, ctx)    # Generate summary

# Tools
ReviewTools                  # Base tools
  ├── get_file_content()    # Fetch file contents
  └── search_related_files() # Find related files

# Models (Pydantic)
ReviewComment                # Per-file review
ReviewSummary                # Overall summary
ReviewState                  # Workflow state

# Base Classes
Model                        # Agent + client wrapper
BaseModelExecutor            # Executor base class
```

## 📊 Metrics & Stats

| Metric             | Value     | Reference                                            |
| ------------------ | --------- | ---------------------------------------------------- |
| **Code Reduction** | 56%       | [SUMMARY.md](SUMMARY.md)                             |
| **Lines of Code**  | ~350      | [SUMMARY.md](SUMMARY.md)                             |
| **Test Coverage**  | 9/9 tests | [test_integration.py](test_integration.py)           |
| **Executors**      | 2         | [Agent_framework_agent.py](Agent_framework_agent.py) |
| **State Fields**   | 5         | [Agent_framework_agent.py](Agent_framework_agent.py) |
| **Base Tools**     | 2         | [Agent_framework_agent.py](Agent_framework_agent.py) |
| **Instructions**   | 3 files   | `../Agents/Instructions/`                            |

## 🔗 External Links

- **Agent Framework**: [Official Docs](https://github.com/microsoft/agent-framework)
- **Gemini API**: [Google AI Studio](https://makersuite.google.com/)
- **GitHub API**: [REST API Docs](https://docs.github.com/en/rest)
- **Pydantic**: [Documentation](https://docs.pydantic.dev/)
- **ReAct Paper**: [arxiv.org/abs/2210.03629](https://arxiv.org/abs/2210.03629)

## 💡 Tips

- **First time?** Always run `test_integration.py` first
- **Debugging?** Check logs in terminal output
- **Rate limited?** Use mock test or reduce MAX_PATCH_CHARS
- **Want to extend?** Start with [example_custom_tools.py](example_custom_tools.py)
- **Performance issues?** See [QUICKSTART.md](QUICKSTART.md) → Performance Tips

## 🆘 Getting Help

1. Check [QUICKSTART.md](QUICKSTART.md) → Common Issues
2. Review [README.md](README.md) → Troubleshooting
3. Run `python test_integration.py` to verify setup
4. Check environment variables (GEMINI_API_KEY, GIT_TOKEN)
5. Review error logs in terminal

## 📅 Version History

- **v1.0** - Initial implementation with Agent Framework
  - ReAct agent with tools
  - Linear workflow
  - Structured output
  - Full documentation

---

## Quick Links

| Document                       | Purpose          | Read Time |
| ------------------------------ | ---------------- | --------- |
| [QUICKSTART.md](QUICKSTART.md) | Get started      | 5 min     |
| [README.md](README.md)         | Architecture     | 15 min    |
| [COMPARISON.md](COMPARISON.md) | Design rationale | 10 min    |
| [SUMMARY.md](SUMMARY.md)       | Overview         | 5 min     |

**Ready to start?** → [QUICKSTART.md](QUICKSTART.md) 🚀
