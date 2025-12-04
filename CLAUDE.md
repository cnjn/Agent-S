# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Agent S** is an open-source framework for creating GUI agents that autonomously interact with computers through an Agent-Computer Interface. The latest version is **Agent S3** (v0.3.1), which achieves state-of-the-art performance on OSWorld (69.9%) and generalizes to WindowsAgentArena and AndroidWorld.

The core package is `gui_agents`, with main implementations in:
- `gui_agents/s1/` - Original Agent S1 (ICLR 2025)
- `gui_agents/s2/` - Compositional framework (COLM 2025)
- `gui_agents/s2_5/` - Simplified version
- `gui_agents/s3/` - **Current focus**: simpler, faster, more flexible

## Development Commands

### Installation
```bash
# Install from PyPI
pip install gui-agents

# Development installation (editable)
pip install -e .

# Install with dev dependencies (black formatter)
pip install -e .[dev]
```

### Linting
```bash
# Check formatting with black
black --check gui_agents

# Format code
black gui_agents
```

### CLI Usage
The primary entry point is `agent_s` (installed via console_scripts). Basic invocation:
```bash
agent_s \
    --provider openai \
    --model gpt-5-2025-08-07 \
    --ground_provider huggingface \
    --ground_url http://localhost:8080 \
    --ground_model ui-tars-1.5-7b \
    --grounding_width 1920 \
    --grounding_height 1080
```

Key required parameters:
- `--ground_provider`, `--ground_url`, `--ground_model`: Grounding model endpoint (e.g., UI-TARS-1.5-7B)
- `--grounding_width`, `--grounding_height`: Output coordinate resolution (1920x1080 for UI-TARS-1.5-7B)

Optional flags:
- `--enable_local_env`: Enable local Python/Bash code execution (**security warning**)
- `--enable_reflection`: Enable reflection agent (default: True)
- `--max_trajectory_length`: Maximum image turns to keep (default: 8)

### SDK Usage
```python
from gui_agents.s3.agents.agent_s import AgentS3
from gui_agents.s3.agents.grounding import OSWorldACI
from gui_agents.s3.utils.local_env import LocalEnv

# Configure engines
engine_params = {
    "engine_type": "openai",
    "model": "gpt-5-2025-08-07",
}
engine_params_for_grounding = {
    "engine_type": "huggingface",
    "model": "ui-tars-1.5-7b",
    "base_url": "http://localhost:8080",
    "grounding_width": 1920,
    "grounding_height": 1080,
}

grounding_agent = OSWorldACI(
    env=local_env,
    platform="linux",
    engine_params_for_generation=engine_params,
    engine_params_for_grounding=engine_params_for_grounding,
)
agent = AgentS3(engine_params, grounding_agent, platform="linux")
```

## Architecture (Agent S3)

### Core Components (`gui_agents/s3/`)

#### Agents (`agents/`)
- `agent_s.py`: Main `AgentS3` class orchestrates worker, reflection, and grounding.
- `grounding.py`: `OSWorldACI` implements Agent-Computer Interface (ACI) for UI interaction.
- `worker.py`: Worker agent that performs actions.
- `code_agent.py`: Code execution agent (optional, requires `--enable_local_env`).

#### Behavior Best-of-N (`bbon/`)
- `behavior_narrator.py`: Generates textual descriptions of trajectory differences.
- `comparative_judge.py`: Compares multiple rollouts to select the best trajectory.

#### Core Engine (`core/`)
- `engine.py`: LLM engine implementations for OpenAI, Anthropic, Gemini, Azure, vLLM, Open Router.
- `mllm.py`: `LMMAgent` wraps LLMs with multimodal message handling.

#### Memory (`memory/`)
- `procedural_memory.py`: Learns from past experiences to improve future performance.

#### Utilities (`utils/`)
- `local_env.py`: Local coding environment for Python/Bash execution.
- `common_utils.py`, `formatters.py`: Shared helpers.

### Key Architectural Patterns

1. **Multimodal LLM Integration**: Supports multiple providers via engine parameters.
2. **Platform Abstraction**: Uses `pyautogui` for cross-platform screenshots, `pywinauto` (Windows), `pyobjc` (macOS) for UI control.
3. **Grounding Model**: UI-TARS models translate natural language instructions to UI coordinates.
4. **Reflection Loop**: Agent can reflect on its actions and adjust strategy.
5. **Trajectory Management**: Maintains limited history of image turns (`max_trajectory_length`).

## Configuration

### API Keys
Set environment variables:
```bash
export OPENAI_API_KEY=<key>
export ANTHROPIC_API_KEY=<key>
export HF_TOKEN=<key>  # For UI-TARS models
```

### Grounding Models
- **UI-TARS-1.5-7B**: Recommended, use `--grounding_width 1920 --grounding_height 1080`
- **UI-TARS-72B**: Use `--grounding_width 1000 --grounding_height 1000`

Host on Hugging Face Inference Endpoints or local vLLM/TGI server.

### Model Support
See `models.md` for detailed provider configurations (OpenAI, Anthropic, Gemini, Azure OpenAI, vLLM, Open Router).

## Evaluation

### OSWorld Integration
Deployment instructions in `osworld_setup/s3/OSWorld.md`. Key steps:
1. Copy run files from `osworld_setup/s3/` to OSWorld directory.
2. Switch AWS AMI if using cloud evaluation.
3. Use `generate_facts.py` and `run_judge.py` for Behavior Best-of-N evaluation.

### Evaluation Sets
- `evaluation_sets/test_all.json`, `test_small_new.json`: Test tasks.

## Testing

No traditional unit tests are present. Evaluation is performed through:
1. **OSWorld benchmark**: Follow `osworld_setup/s3/OSWorld.md` for deployment.
2. **WindowsAgentArena**: See `WAA_setup.md` for Windows-specific evaluation.
3. **Behavior Best-of-N**: Use scripts in `osworld_setup/s3/bbon/` to compare multiple rollouts.

For local validation, run the CLI with a simple instruction and monitor agent behavior.

## Platform-Specific Notes

### Windows
- Requires `pywinauto` and `pywin32` (automatically installed via platform-specific dependencies).
- Use `platform="windows"` in SDK.

### macOS
- Requires `pyobjc` for UI automation.
- Use `platform="darwin"` in SDK.

### Linux
- Relies on `pyautogui` and X11/Wayland compatibility.
- Use `platform="linux"` in SDK.

## Security Considerations

1. **Local Coding Environment**: `--enable_local_env` executes arbitrary Python/Bash code. Use only in trusted environments.
2. **GUI Control**: Agent can perform any UI interaction; monitor its actions.
3. **API Costs**: Using commercial LLMs (GPT-5, Claude) incurs costs; set usage limits.

## Common Development Tasks

### Adding a New LLM Provider
1. Extend `gui_agents/s3/core/engine.py` with new engine class.
2. Add provider to `engine_type` validation.
3. Update `models.md` documentation.

### Modifying Grounding Logic
Edit `gui_agents/s3/agents/grounding.py` `OSWorldACI` class methods:
- `_process_observation()`: Screenshot preprocessing.
- `_call_grounding_model()`: Interaction with UI-TARS endpoint.
- `_parse_grounding_response()`: Coordinate extraction.

### Adjusting Reflection Behavior
Modify `gui_agents/s3/agents/agent_s.py` `AgentS3._reflect()` method and reflection prompts.

## File References

- `gui_agents/s3/cli_app.py:228`: CLI entry point `main()` with argument parsing.
- `gui_agents/s3/agents/agent_s.py`: Core agent logic.
- `gui_agents/s3/agents/grounding.py`: UI interaction implementation.
- `setup.py:36`: Console script entry point definition.