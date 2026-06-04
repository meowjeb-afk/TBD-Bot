# TBD-Bot (Trauma Beanies Dictionary) 🫘📖

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/library-discord.py-v2.0%2B-purple.svg)](https://discordpy.readthedocs.io/en/stable/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Welcome to **TBD-Bot**, a highly customized, multi-functional Discord bot built with Python. Originally created to dynamically generate and document a shared "dictionary" of unique words, inside jokes, and custom definitions for a close-knit community, TBD-Bot has grown into a modular assistant packed with interactive features.

Using dynamic image generation, TBD-Bot transforms standard text commands into sleek, visual dictionary cards and interactive modules directly inside your Discord server.

---

## ✨ Features

### 📖 1. The Trauma Beanies Dictionary
The core feature of the bot. It acts as a living archive for your community's custom vocabulary.
* **Dynamic Card Generation:** Turns text definitions into beautifully rendered graphical cards complete with phonetic spellings, parts of speech, and example sentences.
* **Seamless Management:** Easy commands to look up, add, or browse your server's unique slang database.

### 🧩 2. Interactive Modules (Cogs)
Built using a modular structure, TBD-Bot includes several distinct features to bring life to your server:
* **🐾 Virtual Pet State Tracking:** Keep track of a collective virtual server companion's mood and status.
* **⚖️ Community Karma:** A fun, interactive system to give or track community points/karma among server members.
* **🔮 Tarot Draws & Affirmations:** Pull daily cards with beautiful tarot illustrations or call up positive daily affirmations.
* **🎲 Dice Physics:** Utility commands for rolling dice, perfect for tabletop gaming elements or simple random chance decisions.
* **⏰ Task Scheduling:** An automated background scheduler to keep things running smoothly.

---

## 🛠️ Project Architecture

The repository is built with scalability and clean separation of concerns in mind:

```text
├── assets/                  # Fonts, mascot sprites, and tarot illustrations
├── cogs/                    # Modular feature extensions (Cogs)
│   ├── dictionary.py        # Core vocabulary logic
│   ├── pet.py               # Virtual pet state logic
│   ├── karma.py             # Community karma tracking
│   ├── tarot.py             # Tarot & affirmations module
│   ├── dice.py              # Randomization and dice rolling
│   └── scheduler.py         # Automated background tasks
├── discord_bot.py           # Central bootloader and orchestrator
├── image_generator.py       # Specialized canvas/rendering engines
├── .gitignore               # Keeps your secrets (tokens, DBs) safe
└── requirements.txt         # Project dependencies

