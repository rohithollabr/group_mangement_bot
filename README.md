# group_mangement_bot
A simple modular telegram bot still in devolopment.

## Features

- Group administration: Kick, ban, mute, promote, and demote users.
- Custom Commands: Set group rules, save and retrieve notes.
- File Management: Save and search for files per user.
- Welcome Messages: Greet new members who join the group.

## Setup and Running

### Local Development

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd group_mangement_bot
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up your environment variables:**
    Create a `.env` file by copying the example and add your Telegram Bot Token.
    ```bash
    cp .env.example .env
    # Now edit .env and add your token
    ```

4.  **Run the bot:**
    ```bash
    python telegram_bot.py
    ```
