"""botmigrate — move AI agent bots between Grok Bot and Hermes Agent.

from botmigrate import convert, sync, load_bot

convert("research-bot.json", "./research-bot")           # Grok → Hermes
sync("./research-bot", "~/.hermes/profiles/research-bot", apply=True)
"""

__version__ = "0.1.0"

from botmigrate.convert import ConvertResult, convert
from botmigrate.formats import FormatKind
from botmigrate.ir.models import PortableBot
from botmigrate.load import detect, load_bot
from botmigrate.sync import SyncResult, sync

__all__ = [
    "ConvertResult",
    "FormatKind",
    "PortableBot",
    "SyncResult",
    "__version__",
    "convert",
    "detect",
    "load_bot",
    "sync",
]
