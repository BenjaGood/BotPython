import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler, CallbackQueryHandler
from google.cloud import firestore
from google.oauth2 import service_account

# Ruta a tu archivo de credenciales
cred_path = "/Users/benjamingutierrezmendoza/Documents/OracleAlternativeProject/devmatebot-75628-firebase-adminsdk-bhucy-caefc62eb3.json"

# Verifica que la ruta es correcta
if not os.path.exists(cred_path):
    raise FileNotFoundError(f"El archivo de credenciales no se encontró en {cred_path}")

# Inicializa las credenciales
credentials = service_account.Credentials.from_service_account_file(cred_path)

# Inicializa el cliente de Firestore con las credenciales
db = firestore.Client(credentials=credentials)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define states for the conversation
TASK_DESCRIPTION, TASK_DUE_DATE, TASK_PRIORITY, REMOVE_TASK = range(4)

async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    logger.info(f"User {user.first_name} started the conversation.")
    
    main_menu_keyboard = [
        [InlineKeyboardButton("📋 Review My Tasks", callback_data='review_tasks')],
        [InlineKeyboardButton("➕ Add New Task", callback_data='add_task')],
        [InlineKeyboardButton("🗑 Remove a Task", callback_data='remove_task')],
        [InlineKeyboardButton("👥 View Team Tasks", callback_data='view_team_tasks')],
        [InlineKeyboardButton("❓ Help", callback_data='help')],
        [InlineKeyboardButton("🔔 Configure Notifications", callback_data='configure_notifications')],
    ]
    
    reply_markup = InlineKeyboardMarkup(main_menu_keyboard)
    
    await update.message.reply_text(
        '👋 Welcome to Oracle DevMate Bot! Please choose an option:',
        reply_markup=reply_markup
    )

async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'review_tasks':
        await review_tasks(update, context)
    elif query.data == 'add_task':
        await add_task_start(update, context)
    elif query.data == 'remove_task':
        await remove_task_start(update, context)
    elif query.data == 'view_team_tasks':
        await view_team_tasks(update, context)
    elif query.data == 'help':
        await help_command(update, context)
    elif query.data == 'configure_notifications':
        await configure_notifications(update, context)

async def review_tasks(update: Update, context: CallbackContext) -> None:
    user_id = str(update.callback_query.from_user.id)
    try:
        user_tasks = await get_tasks_from_firestore(user_id)
    except Exception as e:
        logger.error(f"Error retrieving tasks from Firestore: {e}")
        await update.callback_query.edit_message_text('⚠️ Error retrieving tasks. Please try again later.')
        return
    
    if not user_tasks:
        await update.callback_query.edit_message_text('📭 You have no tasks assigned.')
        return
    
    task_list = "📝 **Here are your current tasks:**\n\n"
    for i, task in enumerate(user_tasks):
        task_list += f"{i + 1}. {task['description']} - Due on {task['due_date']} - {task['priority']} Priority\n"

    await update.callback_query.edit_message_text(task_list)

async def add_task_start(update: Update, context: CallbackContext) -> int:
    await update.callback_query.edit_message_text('✏️ Please provide the task description.')
    return TASK_DESCRIPTION

async def task_description(update: Update, context: CallbackContext) -> int:
    context.user_data['description'] = update.message.text
    await update.message.reply_text('📅 Please provide the task due date (YYYY-MM-DD).')
    return TASK_DUE_DATE

async def task_due_date(update: Update, context: CallbackContext) -> int:
    context.user_data['due_date'] = update.message.text
    await update.message.reply_text('📊 Please provide the task priority (High, Medium, Low).')
    return TASK_PRIORITY

async def task_priority(update: Update, context: CallbackContext) -> int:
    user_id = str(update.message.from_user.id)
    context.user_data['priority'] = update.message.text
    
    new_task = {
        'description': context.user_data['description'],
        'due_date': context.user_data['due_date'],
        'priority': context.user_data['priority'],
    }
    
    try:
        await add_task_to_firestore(user_id, new_task)
        await update.message.reply_text('✅ Task added successfully!')
    except Exception as e:
        logger.error(f"Error adding task to Firestore: {e}")
        await update.message.reply_text('⚠️ Error adding task. Please try again later.')
    
    return ConversationHandler.END

async def remove_task_start(update: Update, context: CallbackContext) -> int:
    user_id = str(update.callback_query.from_user.id)
    try:
        user_tasks = await get_tasks_from_firestore(user_id)
    except Exception as e:
        logger.error(f"Error retrieving tasks from Firestore: {e}")
        await update.callback_query.edit_message_text('⚠️ Error retrieving tasks. Please try again later.')
        return ConversationHandler.END
    
    if not user_tasks:
        await update.callback_query.edit_message_text('📭 You have no tasks to remove.')
        return ConversationHandler.END
    
    task_list = "🗑️ **Please provide the number of the task you want to remove:**\n\n"
    for i, task in enumerate(user_tasks):
        task_list += f"{i + 1}. {task['description']} - Due on {task['due_date']} - {task['priority']} Priority\n"
    
    await update.callback_query.edit_message_text(task_list)
    return REMOVE_TASK

async def remove_task(update: Update, context: CallbackContext) -> int:
    user_id = str(update.message.from_user.id)
    task_number = int(update.message.text) - 1
    try:
        user_tasks = await get_tasks_from_firestore(user_id)
    except Exception as e:
        logger.error(f"Error retrieving tasks from Firestore: {e}")
        await update.message.reply_text('⚠️ Error retrieving tasks. Please try again later.')
        return
    
    if 0 <= task_number < len(user_tasks):
        removed_task = user_tasks.pop(task_number)
        try:
            await remove_task_from_firestore(user_id, removed_task['description'])
            await update.message.reply_text(f"🗑️ Task '{removed_task['description']}' removed successfully!")
        except Exception as e:
            logger.error(f"Error removing task from Firestore: {e}")
            await update.message.reply_text('⚠️ Error removing task. Please try again later.')
    else:
        await update.message.reply_text('❌ Invalid task number. Please try again.')
    
    return ConversationHandler.END

async def view_team_tasks(update: Update, context: CallbackContext) -> None:
    try:
        team_tasks = await get_team_tasks_from_firestore()
    except Exception as e:
        logger.error(f"Error retrieving team tasks from Firestore: {e}")
        await update.callback_query.edit_message_text('⚠️ Error retrieving team tasks. Please try again later.')
        return
    
    if not team_tasks:
        await update.callback_query.edit_message_text('📭 No team tasks available.')
        return
    
    team_task_list = "👥 **Team Tasks Overview:**\n\n"
    for user_id, user_tasks in team_tasks.items():
        team_task_list += f"**User {user_id}:**\n"
        for task in user_tasks:
            team_task_list += f"- {task['description']} - Due on {task['due_date']} - {task['priority']} Priority\n"
    
    await update.callback_query.edit_message_text(team_task_list)

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
    🆘 **Help Section** 🆘

    **Commands:**
    📋 Review My Tasks: View your current tasks.
    ➕ Add New Task: Add a new task to your list.
    🗑 Remove a Task: Remove a task from your list.
    👥 View Team Tasks: Managers can view tasks assigned to all team members.
    🔔 Configure Notifications: Customize your notification preferences.
    """
    await update.callback_query.edit_message_text(help_text)

async def configure_notifications(update: Update, context: CallbackContext) -> None:
    notifications_text = """
    🔔 **Configure Notifications:**

    - 📅 Task Reminders: Receive reminders about upcoming deadlines.
    - 📊 Task Updates: Get notified when there are updates to your tasks.
    - 👥 Team Activity: Managers can get notifications about team activities.
    """
    await update.callback_query.edit_message_text(notifications_text)

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('❌ Action cancelled.')
    return ConversationHandler.END

async def add_task_to_firestore(user_id: str, task: dict) -> None:
    doc_ref = db.collection('tasks').document(user_id).collection('user_tasks').document(task['description'])
    doc_ref.set(task)

async def get_tasks_from_firestore(user_id: str) -> list:
    tasks_ref = db.collection('tasks').document(user_id).collection('user_tasks')
    tasks_snapshot = tasks_ref.stream()
    return [task.to_dict() for task in tasks_snapshot]

async def remove_task_from_firestore(user_id: str, task_description: str) -> None:
    task_ref = db.collection('tasks').document(user_id).collection('user_tasks').document(task_description)
    task_ref.delete()

async def get_team_tasks_from_firestore() -> dict:
    team_tasks = {}
    users_ref = db.collection('tasks').stream()
    for user in users_ref:
        user_id = user.id
        user_tasks = await get_tasks_from_firestore(user_id)
        team_tasks[user_id] = user_tasks
    return team_tasks

def main() -> None:
    """Start the bot."""
    # Reemplaza 'YOUR_TELEGRAM_BOT_TOKEN' con el token real de tu bot
    application = Application.builder().token("7092434413:AAH6bOI6o0WkDhSUhl14SVobjBjUeJQjE9U").build()
    
    # Add conversation handler with the states TASK_DESCRIPTION, TASK_DUE_DATE, TASK_PRIORITY
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_task_start, pattern='^add_task$')],
        states={
            TASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_description)],
            TASK_DUE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_due_date)],
            TASK_PRIORITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_priority)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    remove_task_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(remove_task_start, pattern='^remove_task$')],
        states={
            REMOVE_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_task)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(remove_task_handler)
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling()

if __name__ == '__main__':
    main()
