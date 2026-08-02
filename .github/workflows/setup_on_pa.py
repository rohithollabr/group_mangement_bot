import os
import subprocess
import sys

def main():
    """
    This script is run on PythonAnywhere to set up the environment.
    It unzips the source, creates a virtualenv, and installs dependencies.
    """
    username = os.getenv("PYTHONANYWHERE_USERNAME")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not username:
        print("PYTHONANYWHERE_USERNAME environment variable not set.")
        sys.exit(1)

    project_folder_name = "group_mangement_bot"
    home_dir = f"/home/{username}"
    project_dir = f"{home_dir}/{project_folder_name}"
    zip_file = f"{home_dir}/source.zip"
    venv_dir = f"{home_dir}/.virtualenvs/telegram-bot-venv"
    
    print("--- Starting PythonAnywhere Setup ---")

    # Unzip the source code, overwriting existing files
    print(f"Unzipping {zip_file} to {home_dir}...")
    subprocess.run(["unzip", "-o", zip_file, "-d", home_dir], check=True)

    # Create or update the .env file with the bot token
    if bot_token:
        print(f"Creating .env file in {project_dir}...")
        with open(f"{project_dir}/.env", "w") as f:
            f.write(f"TELEGRAM_BOT_TOKEN={bot_token}\n")


    # Create virtualenv if it doesn't exist
    if not os.path.exists(venv_dir):
        print(f"Creating virtualenv in {venv_dir}...")
        subprocess.run(["mkvirtualenv", "--python=python3.10", venv_dir], check=True)

    # Install/update dependencies
    print("Installing dependencies from requirements.txt...")
    pip_executable = f"{venv_dir}/bin/pip"
    subprocess.run([pip_executable, "install", "-r", f"{project_dir}/requirements.txt"], check=True)

    print("--- Setup Complete ---")

if __name__ == "__main__":
    main()