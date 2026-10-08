# Standard Library
import asyncio
from unittest.mock import MagicMock, patch

# Django
from django.test import TestCase

# Demolizzen
from demolizzen.core.bot import Demolizzen


class BotStartupTest(TestCase):
    @patch(
        "demolizzen.core.openapi.OpenAPI"
    )  # Mock the OpenAPI class to avoid real HTTP calls
    @patch(
        "aiohttp.ClientSession"
    )  # Mock the aiohttp ClientSession to avoid real HTTP calls
    @patch(
        "demolizzen.core.bot.config.BOT_TOKEN", "test_env_token"
    )  # Mock the BOT_TOKEN to a fake value
    @patch("demolizzen.core.bot.config.BOT_PERMISSIONS", 0)
    @patch(
        "discord.ext.commands.Bot.start", autospec=True
    )  # Mock the start method to prevent actual bot startup
    def test_bot_startup(self, mock_start, mock_aiohttp, mock_esi):
        """Test that the bot starts up correctly and calls the start method with the token."""
        mock_esi.return_value = MagicMock()
        mock_aiohttp.return_value = MagicMock()
        Demolizzen()
        mock_start.assert_called_once()
