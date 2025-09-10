# Contributing to This Project

Thank you for considering contributing to our project! Here are some guidelines to help you get started.

## Getting Started

1. **Fork the repository**: Click the "Fork" button at the top right of the repository page.

1. **Clone your fork**: Clone your forked repository to your local machine.

   ```sh
   git clone https://github.com/geuthur/demolizzen.git
   ```

1. **Set up the upstream remote**: Add the original repository as a remote to keep your fork up to date.

   ```sh
   git remote add upstream https://github.com/geuthur/demolizzen.git
   ```

1. **Set up Py-Cord Development Environment**

   To develop and test your change, you need a development environment based on [py-cord](https://docs.pycord.dev/en/stable/) on your local machine.
   Ensure you can use pre-commit checks in this environment.

## Pre-commit Hooks

We use pre-commit hooks to ensure code quality and consistency. Please make sure you have pre-commit installed and set up.

1. **Install pre-commit**: If you don't have pre-commit installed, you can install it using pip.

   ```sh
   pip install pre-commit
   ```

1. **Install the hooks**: Run the following command to install the pre-commit hooks.

   ```sh
   pre-commit install
   ```

1. **Use Pre Commit**

   Check all files

   ```sh
   pre-commit run --all-files
   ```

   If you want only one of the hooks like `pylint`

   ```sh
   pre-commit run pylint
   ```

## Branching und Contributing via Pull Requests

Before creating a pull request, make sure that you have forked the repository and are working on your fork. This ensures that your changes are isolated and do not affect the original repository until they are reviewed and merged.

The `master` branch should always be kept up to date to avoid conflicts. This means that all changes integrated into the `master` branch should be thoroughly reviewed and tested before being merged. Regular updates and synchronizations with the `master` branch help to identify and resolve potential conflicts early.

Before creating a new feature, an issue should always be opened first. This serves to start a discussion about the planned feature and ensure that all team members are informed about the planned changes. Through discussion, potential problems and improvements can be identified and considered early. This promotes a collaborative working approach and contributes to the quality and consistency of the project.

## Tests

We use several testing tools and frameworks to ensure the quality and reliability of our codebase. For Discord/py-cord bots, the following types of tests can serve as templates:

- **Unit tests for commands and cogs:** Test individual functions and commands, e.g., whether a command is called correctly and returns the expected response. Use mocking for Discord objects (User, Message, Context).
- **Event handler tests:** Simulate events like on_message, on_member_join, etc., and check if the handlers respond correctly.
- **Integration tests (optional):** Start the bot in a test environment and simulate real Discord interactions (e.g., with discord.ext.test or pytest-discord).
- **Coverage tests:** Check how much of your code is covered by tests.

Typical tools:

- pytest
- unittest
- pytest-mock or asynctest for async/mocking

The tests in this project serve as templates and can be adapted for your own py-cord commands and events.

Example of a simple command test (using pytest and unittest.mock):

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from demolizzen.cogs.general import GeneralCog


@pytest.mark.asyncio
async def test_ping_command():
    ctx = MagicMock()
    cog = GeneralCog(None)
    await cog.ping(ctx)
    ctx.send.assert_called_with("Pong!")
```

Below is a list of the main tools we use:

- [coverage](https://coverage.readthedocs.io/en/latest/#)
