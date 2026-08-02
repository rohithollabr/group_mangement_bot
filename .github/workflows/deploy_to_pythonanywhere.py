import os
import requests
import shlex
import sys
import time
import zipfile


def zip_directory(path, zip_handler):
    """Zips the contents of a directory."""
    for root, _, files in os.walk(path):
        for file in files:
            # Create a relative path for files to keep the directory structure
            relative_path = os.path.relpath(os.path.join(root, file), os.path.join(path, '..'))
            zip_handler.write(os.path.join(root, file), arcname=relative_path)

def deploy():
    """
    Zips the project, uploads it to PythonAnywhere, runs a setup script there,
    and then restarts the always-on task.
    Expects environment variables for:
    - PYTHONANYWHERE_API_TOKEN
    - PYTHONANYWHERE_USERNAME
    - GITHUB_WORKSPACE (set by GitHub Actions)
    """
    api_token = os.getenv("PYTHONANYWHERE_API_TOKEN")
    username = os.getenv("PYTHONANYWHERE_USERNAME")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    workspace = os.getenv("GITHUB_WORKSPACE", ".") # Default to current dir if not in GH Actions

    if not all([api_token, username, bot_token]):
        print("Error: One or more required environment variables are not set.")
        print("Please set PYTHONANYWHERE_API_TOKEN, PYTHONANYWHERE_USERNAME, and TELEGRAM_BOT_TOKEN.")
        sys.exit(1)

    project_folder_name = "group_mangement_bot"
    bot_script_path = f"/home/{username}/{project_folder_name}/telegram_bot.py"
    zip_file_name = "source.zip"

    # --- 1. Zip the project directory ---
    print(f"Zipping project source from: {workspace}")
    zipf = zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED)
    zip_directory(workspace, zipf)
    zipf.close()
    print("Project zipped successfully.")

    # --- 2. Upload the zipped project ---
    upload_url = f"https://www.pythonanywhere.com/api/v0/user/{username}/files/path/home/{username}/{zip_file_name}"
    with open(zip_file_name, 'rb') as f:
        files = {'content': f}
        headers = {'Authorization': f'Token {api_token}'}
        print(f"Uploading {zip_file_name} to PythonAnywhere...")
        response = requests.post(upload_url, headers=headers, files=files)

    if response.status_code not in [200, 201]:
        print(f"Failed to upload zip file. Status: {response.status_code}, Response: {response.text}")
        sys.exit(1)
    print("Zip file uploaded successfully.")

    # --- 3. Run the setup script on PythonAnywhere via the Console API ---
    console_url = f"https://www.pythonanywhere.com/api/v0/user/{username}/consoles/"
    # This command will run the setup script using the same Python version as your bot
    # It assumes your virtualenv is in ~/.virtualenvs/
    python_version = "python3.10"
    setup_command = (
        f"export TELEGRAM_BOT_TOKEN={shlex.quote(bot_token)} && "
        f"{python_version} /home/{username}/{project_folder_name}/.github/workflows/setup_on_pa.py"
    )

    print("Starting a console on PythonAnywhere to run the setup script...")
    resp = requests.post(
        console_url,
        headers=headers,
        # Use shlex.quote to handle special characters in the token
        json={"executable": "bash", "arguments": f"-c '{setup_command}'"}
    )
    if resp.status_code != 201:
        print(f"Failed to create console. Status: {resp.status_code}, Response: {resp.text}")
        sys.exit(1)

    console_id = resp.json()['id']
    print(f"Console with ID {console_id} created. Waiting for setup to complete...")
    # Give it a moment to run. In a real-world scenario, you might poll the console output.
    time.sleep(60) # Wait for unzip and pip install to finish

    print("Deployment script finished.")
    print("Please go to your PythonAnywhere 'Tasks' page and reload your bot's task to apply the changes.")

if __name__ == "__main__":
    deploy()