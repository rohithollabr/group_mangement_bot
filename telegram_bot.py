import logging
import os
import json
from functools import wraps
from telegram import Update
from telegram import InlineQueryResultArticle, InputTextMessageContent, InlineQueryResultDocument, InlineQueryResultPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, InlineQueryHandler, PicklePersistence

# It's good practice to enable logging to see errors and bot activity.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Best Practice: Load Token from Environment Variable ---
# It's more secure to load your token from an environment variable
# than to hardcode it in your script.
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

def admin_only(func):
    """
    A decorator to restrict command usage to group administrators.
    """
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if update.effective_chat.type == 'private':
            await update.message.reply_text("This command can only be used in groups.")
            return

        administrators = await context.bot.get_chat_administrators(chat_id)
        admin_ids = {admin.user.id for admin in administrators}

        if user_id not in admin_ids:
            await update.message.reply_text("You must be an admin to use this command.")
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapped

async def get_user_from_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> (int, str):
    """
    Helper function to get a user's ID and name from a command.
    It can handle replies, @mentions, and user IDs.
    Returns a tuple of (user_id, user_name) or (None, None) if no user is found.
    """
    # Case 1: The command is a reply to a user's message
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        return user.id, user.mention_html()

    # Case 2: The command includes arguments (e.g., /kick @username or /kick 12345678)
    if context.args:
        # Check for text_mentions (when a user is tagged directly)
        if update.message.entities and len(update.message.entities) > 0:
            for entity in update.message.entities:
                if entity.type == 'text_mention' and entity.user:
                    return entity.user.id, entity.user.mention_html()
        
        arg = context.args[0]
        # Case 3: The argument is a username (e.g., @someuser)
        if arg.startswith('@'):
            username = arg[1:].lower()
            chat_id = str(update.effective_chat.id)
            # Access user_cache from context.chat_data
            user_cache = context.chat_data.get('user_cache', {})
            if username in user_cache:
                user_id = user_cache[username]
                return int(user_id), arg

        # Case 4: The argument is a user ID
        try:
            user_id = int(arg)
            # We don't have the user's name here, so we'll just use the ID.
            return user_id, f"user with ID {user_id}"
        except ValueError:
            pass # Not a user ID, we'll let the calling function handle the error message.

    # If no user is found
    return None, None

async def send_usage_error(update: Update, command: str):
    """Sends a standardized error message for command usage."""
    await update.message.reply_text(
        f"Invalid usage\. Please either reply to a user's message, mention them, or provide their user ID or @username\.\n"
        f"Example: `{command} 123456789`",
        parse_mode='MarkdownV2'
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    This function is a command handler. It's called when the user sends /start.
    It sends a welcome message to the user.
    """
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I am your new bot. Send me a message and I will echo it back.",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    This function is a command handler for the /help command.
    It sends a detailed list of all available commands.
    """
    help_text = """
Hello\! I'm a group management bot\. Here's what I can do:

**User Commands**
/start \- Greets you and starts the bot\.
/help \- Shows this help message\.
/rules \- Displays the group rules\.
/get `<notename>` \- Retrieves a saved note\. You can also use `#notename`\.

/savefile `<filename>` \- Reply to a file to save it for personal retrieval\.

**Admin\-Only Commands** `(reply, @mention, or provide a user ID/@username)`
/kick \- Kicks a user\. They can rejoin with an invite link\.
/ban \- Bans a user permanently\.
/mute \- Mutes a user, preventing them from speaking\.
/promote \- Promotes a user to an admin\.
/demote \- Removes a user's admin rights\.
/unban `<user_id>` \- Unbans a user, allowing them to rejoin\.
/save `<notename> <text>` \- Saves a note that can be retrieved later\.
/memberids \- Lists the user IDs of all cached members\.
/setrules `<rules text>` \- Sets the rules for the group\.
    """
    help_text += "\nTo search your saved files, go to any chat, type my username and a search query\."
    await update.message.reply_text(help_text, parse_mode='MarkdownV2')

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    This function is a message handler. It echoes any text message it receives.
    """
    logger.info(f"Received message from {update.effective_user.name}: {update.message.text}")
    await update.message.reply_text(update.message.text)

async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    This function is a handler for new members joining a group.
    It sends a welcome message to each new member.
    """
    new_members = update.message.new_chat_members
    for member in new_members:
        logger.info(f"{member.full_name} joined the chat {update.effective_chat.title}")
        await update.message.reply_text(
            f"Welcome to the group, {member.mention_html()}! We're glad to have you here."
        )

async def update_user_cache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A handler that silently updates the user cache on any message."""
    if not update.effective_user or not update.effective_user.username or not update.effective_chat:
        return

    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    username = update.effective_user.username.lower()

    # context.chat_data is a dictionary unique to each chat.
    # We'll store a 'user_cache' dictionary inside it.
    if 'user_cache' not in context.chat_data:
        context.chat_data['user_cache'] = {}

    context.chat_data['user_cache'][username] = user_id

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    This function is a command handler for the /rules command.
    It sends the group rules to the chat.
    """
    # context.chat_data is a dictionary that persists for each chat.
    # We get the 'rules' key from it.
    if 'rules' in context.chat_data and context.chat_data['rules']:
        rules_text = f"📜 **Group Rules** 📜\n\n{context.chat_data['rules']}"
        await update.message.reply_text(rules_text, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text(
            "No rules have been set for this group yet\. An admin can set them with `/setrules <rules text>`\.",
            parse_mode='MarkdownV2'
        )

@admin_only
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kicks a user from the group. The user can rejoin with an invite link."""
    user_id, user_name = await get_user_from_command(update, context)
    if not user_id:
        await send_usage_error(update, "/kick")
        return

    chat_id = update.effective_chat.id
    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        # Immediately unban them to allow rejoining via invite link. This is the "kick" logic.
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
        await update.message.reply_text(f"Kicked {user_name}.", parse_mode='HTML')
        logger.info(f"Admin {update.effective_user.name} kicked {user_name} from {update.effective_chat.title}")
    except Exception as e:
        await update.message.reply_text(f"Failed to kick user. Reason: {e}")
        logger.error(f"Error kicking user: {e}")

@admin_only
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bans a user from the group permanently."""
    user_id, user_name = await get_user_from_command(update, context)
    if not user_id:
        await send_usage_error(update, "/ban")
        return

    chat_id = update.effective_chat.id
    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        await update.message.reply_text(f"Banned {user_name}.", parse_mode='HTML')
        logger.info(f"Admin {update.effective_user.name} banned {user_name} from {update.effective_chat.title}")
    except Exception as e:
        await update.message.reply_text(f"Failed to ban user. Reason: {e}")
        logger.error(f"Error banning user: {e}")

@admin_only
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mutes a user, preventing them from sending messages."""
    user_id, user_name = await get_user_from_command(update, context)
    if not user_id:
        await send_usage_error(update, "/mute")
        return

    chat_id = update.effective_chat.id
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions={'can_send_messages': False}
        )
        await update.message.reply_text(f"Muted {user_name}.", parse_mode='HTML')
        logger.info(f"Admin {update.effective_user.name} muted {user_name} in {update.effective_chat.title}")
    except Exception as e:
        await update.message.reply_text(f"Failed to mute user. Reason: {e}")
        logger.error(f"Error muting user: {e}")

@admin_only
async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unmutes a user, allowing them to send messages again."""
    user_id, user_name = await get_user_from_command(update, context)
    if not user_id:
        await send_usage_error(update, "/unmute")
        return

    chat_id = update.effective_chat.id
    # To unmute, we grant them the default permissions for a non-admin.
    await context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions={'can_send_messages': True, 'can_send_media_messages': True, 'can_send_polls': True, 'can_send_other_messages': True, 'can_add_web_page_previews': True})
    await update.message.reply_text(f"Unmuted {user_name}.", parse_mode='HTML')

@admin_only
async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Promotes a user to an admin with a default set of rights."""
    user_id, user_name = await get_user_from_command(update, context)
    if not user_id:
        await send_usage_error(update, "/promote")
        return

    chat_id = update.effective_chat.id
    try:
        await context.bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            can_change_info=True,
            can_delete_messages=True,
            can_invite_users=True,
            can_restrict_members=True,
            can_pin_messages=True
        )
        await update.message.reply_text(f"Promoted {user_name} to admin!", parse_mode='HTML')
        logger.info(f"Admin {update.effective_user.name} promoted {user_name} in {update.effective_chat.title}")
    except Exception as e:
        await update.message.reply_text(f"Failed to promote user. Reason: {e}")
        logger.error(f"Error promoting user: {e}")

@admin_only
async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Demotes a user from admin to a regular member."""
    user_id, user_name = await get_user_from_command(update, context)
    if not user_id:
        await send_usage_error(update, "/demote")
        return

    chat_id = update.effective_chat.id
    try:
        # Setting all permissions to False demotes the admin.
        await context.bot.promote_chat_member(chat_id=chat_id, user_id=user_id, can_change_info=False, can_delete_messages=False, can_invite_users=False, can_restrict_members=False, can_pin_messages=False, can_promote_members=False)
        await update.message.reply_text(f"Demoted {user_name}.", parse_mode='HTML')
        logger.info(f"Admin {update.effective_user.name} demoted {user_name} in {update.effective_chat.title}")
    except Exception as e:
        await update.message.reply_text(f"Failed to demote user. Reason: {e}")
        logger.error(f"Error demoting user: {e}")


@admin_only
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unbans a user, allowing them to rejoin."""
    if not context.args:
        await update.message.reply_text("You need to provide a user ID to unban.")
        return

    try:
        user_id_to_unban = int(context.args[0])
        chat_id = update.effective_chat.id
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id_to_unban)
        await update.message.reply_text(f"User with ID {user_id_to_unban} has been unbanned.")
        logger.info(f"Admin {update.effective_user.name} unbanned user ID {user_id_to_unban} from {update.effective_chat.title}")
    except (ValueError, IndexError):
        await update.message.reply_text("Invalid user ID provided. Usage: /unban <user_id>")
    except Exception as e:
        await update.message.reply_text(f"Failed to unban user. Reason: {e}")
        logger.error(f"Error unbanning user: {e}")

@admin_only
async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets the rules for the current chat."""
    if not context.args:
        await update.message.reply_text("Usage: /setrules <your rules text here>")
        return

    new_rules = " ".join(context.args)
    context.chat_data['rules'] = new_rules # Store rules in the chat's persistent data
    await update.message.reply_text("Group rules have been updated!")

@admin_only
async def get_member_ids(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists the user IDs of all known members in the group from the cache."""
    user_cache = context.chat_data.get('user_cache', {})

    if not user_cache:
        await update.message.reply_text("The user cache for this group is empty. Users need to send a message for me to see them.")
        return

    message_lines = ["*Cached members in this group:*"]
    for username, user_id in user_cache.items():
        message_lines.append(f"- `{username}`: `{user_id}`")
    
    message = "\n".join(message_lines)
    
    # Telegram messages have a limit of 4096 characters.
    if len(message) > 4096:
        message = message[:4090] + "\n\.\.\." # Truncate
        
    await update.message.reply_text(message, parse_mode='MarkdownV2')

@admin_only
async def save_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saves a note. Usage: /save <notename> <text>"""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /save <notename> <text to save>")
        return

    note_name = context.args[0].lower()
    note_text = " ".join(context.args[1:])

    if 'notes' not in context.chat_data:
        context.chat_data['notes'] = {}

    context.chat_data['notes'][note_name] = note_text
    await update.message.reply_text(f"Note `#{note_name}` saved!", parse_mode='MarkdownV2')

async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gets a note. Usage: /get <notename> or #notename"""
    # Determine note name from command or text
    if update.message.text.startswith('/'):
        if not context.args:
            await update.message.reply_text("Usage: /get <notename>")
            return
        note_name = context.args[0].lower()
    else: # Triggered by #notename
        note_name = update.message.text[1:].lower()

    notes = context.chat_data.get('notes', {})

    if note_name in notes:
        await update.message.reply_text(notes[note_name])
    else:
        await update.message.reply_text(f"Note `#{note_name}` not found.", parse_mode='MarkdownV2')

async def save_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saves a file by replying to it. Usage: /savefile <filename>"""
    if not update.message.reply_to_message:
        await update.message.reply_text("Please reply to a file to save it.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /savefile <filename>")
        return

    file_name = context.args[0].lower()
    replied_message = update.message.reply_to_message

    file_id = None
    file_type = None

    if replied_message.document:
        file_id = replied_message.document.file_id
        file_type = 'document'
    elif replied_message.photo:
        file_id = replied_message.photo[-1].file_id # Get the highest resolution
        file_type = 'photo'
    else:
        await update.message.reply_text("That file type is not supported for saving.")
        return

    # Use context.user_data for per-user persistent storage
    if 'user_files' not in context.user_data:
        context.user_data['user_files'] = {}

    context.user_data['user_files'][file_name] = {"file_id": file_id, "type": file_type}

    await update.message.reply_text(f"File saved as `{file_name}`. You can find it inline by typing my username and `{file_name}`.", parse_mode='MarkdownV2')

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the inline query. This is fired when a user types @botusername <query>"""
    query = update.inline_query.query

    if not query:
        return

    results = []
    # Access user_data from the context provided by the InlineQueryHandler
    user_files = context.user_data.get('user_files', {})
    if user_files:
        for file_name, file_data in user_files.items():
            if query.lower() in file_name:
                file_id = file_data['file_id']
                file_type = file_data['type']
                
                if file_type == 'document':
                    results.append(
                        InlineQueryResultDocument(id=file_id, title=file_name, document_file_id=file_id)
                    )
                elif file_type == 'photo':
                    results.append(
                        InlineQueryResultPhoto(id=file_id, photo_file_id=file_id, thumb_url=file_id)
                    )

    if not results:
        results.append(
            InlineQueryResultArticle(id="notfound", title="No files found", input_message_content=InputTextMessageContent(f"No files found matching '{query}'"))
        )

    await update.inline_query.answer(results, cache_time=10)

def main() -> None:
    """
    This is the main function where the bot is set up and started.
    """
    # --- Set up Persistence ---
    # This will create a file named 'bot_persistence' to save data.
    persistence = PicklePersistence(filepath="bot_persistence")

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).persistence(persistence).build()

    # --- Register Handlers ---
    # A CommandHandler is used to respond to Telegram commands (e.g., /start).
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("rules", rules))

    # Admin commands
    application.add_handler(CommandHandler("kick", kick))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("mute", mute))
    application.add_handler(CommandHandler("promote", promote))
    application.add_handler(CommandHandler("demote", demote))
    application.add_handler(CommandHandler("unmute", unmute))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("memberids", get_member_ids))
    application.add_handler(CommandHandler("setrules", set_rules))

    # Notes feature
    application.add_handler(CommandHandler("save", save_note))
    application.add_handler(CommandHandler("get", get_note))

    # File saving feature
    application.add_handler(CommandHandler("savefile", save_file))

    # A MessageHandler is used to respond to regular text messages.
    # The `filters.TEXT & ~filters.COMMAND` part ensures it only handles text messages
    # that are not commands.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^#'), echo))

    # This handler runs on all messages to update our user cache. It has a low group number to run first.
    application.add_handler(MessageHandler(filters.TEXT | filters.COMMAND, update_user_cache), group=1)

    # This handler is for status updates, specifically for new members joining a chat.
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))

    # Handler for retrieving notes with #notename
    application.add_handler(MessageHandler(filters.Regex(r'^#\w+'), get_note))

    # Inline query handler
    application.add_handler(InlineQueryHandler(inline_query))


    # Start the Bot.
    # `run_polling` fetches new updates from Telegram and delivers them to the handlers.
    print("Bot is starting... Press Ctrl-C to stop.")
    application.run_polling()

if __name__ == "__main__":
    # This ensures the main() function is called only when the script is executed directly.
    if not TELEGRAM_BOT_TOKEN:
        print("Error: The TELEGRAM_BOT_TOKEN environment variable is not set. Please set it and try again.")
    else:
        main()
