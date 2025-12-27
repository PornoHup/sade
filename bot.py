import logging
import random
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import config

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Söz və qrammatika listləri
daily_words_list = ["Salam","Necəsən?","Yaxşıyam","Ev","Məktəb","Kitab","Qələm","Maşın","Dost","Sevgi"]
grammar_topics = ["Fars dilində feillərin cəm forması","Fars dilində sifətlərin istifadəsi","Fars dilində sual cümlələri"]

daily_tracker = {"words": [], "grammar": ""}

# ---------------- OpenAI (Test Rejimi) ----------------
async def ask_openai(prompt):
    # Test üçün sadəcə promptu qaytarır
    return f"[TEST] Sorğu: {prompt}"

# ---------------- SCHEDULED MESSAGES ----------------
async def send_daily_words(context: ContextTypes.DEFAULT_TYPE):
    words = random.sample(daily_words_list, 10)
    daily_tracker['words'] = words
    msg = "📚 Bu günün 10 yeni sözü:\n" + "\n".join(words)
    await context.bot.send_message(chat_id=config.CHAT_ID, text=msg)

async def send_grammar_topic(context: ContextTypes.DEFAULT_TYPE):
    topic = random.choice(grammar_topics)
    daily_tracker['grammar'] = topic
    msg = f"📝 Günorta qrammatika mövzusu:\n{topic}"
    await context.bot.send_message(chat_id=config.CHAT_ID, text=msg)

async def send_daily_quiz(context: ContextTypes.DEFAULT_TYPE):
    words = daily_tracker.get('words', [])
    grammar = daily_tracker.get('grammar', "")
    if not words or not grammar:
        return

    # TEST sualları (4 variantlı)
    questions = [
        ("Salam sözünün mənası nədir?", ["Hello","Bye","Yes","No"], 0),
        ("Fars dilində sual cümləsi necə başlayır?", ["Aya","Che","Man","To"], 1),
        ("Ev sözünün sinonimi hansıdır?", ["House","Car","School","Book"], 0)
    ]
    
    for q_text, options, correct_id in questions:
        try:
            await context.bot.send_poll(
                chat_id=config.CHAT_ID,
                question=q_text,
                options=options,
                type='quiz',
                correct_option_id=correct_id
            )
        except Exception as e:
            logging.error(f"Poll göndərilmədi: {e}")

# ---------------- COMMANDS & MENTION ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salam! Mən Az ↔ Fa AI köməkçisiyəm. Mənə mention edin və sual verin.")

async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if f"@{context.bot.username}" in update.message.text:
        user_text = update.message.text.replace(f"@{context.bot.username}", "").strip()
        if not user_text:
            await update.message.reply_text("Sualınızı yazın, mən cavab verim.")
            return
        
        correct_prompt = f"Səhv yazılmış mətni düzəlt və düzgün Az dili versiyasını göstər: {user_text}"
        correction = await ask_openai(correct_prompt)

        fa_prompt = f"{user_text} cümləsini Fars dilinə tərcümə et və izah et."
        fa_answer = await ask_openai(fa_prompt)

        await update.message.reply_text(f"✅ Düzəliş: {correction}\n\n📝 Farsca izah: {fa_answer}")

# ---------------- MAIN ----------------
if __name__ == '__main__':
    app = ApplicationBuilder().token(config.TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mention))

    # Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: app.create_task(send_daily_words(app.bot)), 'cron', hour=10, minute=0)   # Səhər 10 yeni söz
    scheduler.add_job(lambda: app.create_task(send_grammar_topic(app.bot)), 'cron', hour=14, minute=0) # Günorta qrammatika
    scheduler.add_job(lambda: app.create_task(send_daily_quiz(app.bot)), 'cron', hour=19, minute=0)    # Axşam quiz
    scheduler.start()

    print("Bot işə düşdü 👍")
    app.run_polling()
