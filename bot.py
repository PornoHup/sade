import logging
import random
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import openai
import config

openai.api_key = config.OPENAI_API_KEY

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

daily_words_list = ["Salam","Necəsən?","Yaxşıyam","Ev","Məktəb","Kitab","Qələm","Maşın","Dost","Sevgi"]
grammar_topics = ["Fars dilində feillərin cəm forması","Fars dilində sifətlərin istifadəsi","Fars dilində sual cümlələri"]

daily_tracker = {"words": [], "grammar": ""}

async def ask_openai(prompt):
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo",
                                            messages=[{"role": "user", "content": prompt}])
    return response['choices'][0]['message']['content']

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

    prompt = f"Bu sözlər və qrammatika mövzusu üçün 3 sual yarat. Hər sual üçün 4 cavab variantı ver. Düzgün cavabı qeyd et. Format:\nSual 1: ...\nVariantlar: A) ... B) ... C) ... D) ...\nDüzgün: ...\n..."
    quiz_text = await ask_openai(prompt)

    questions = re.findall(r"Sual \d+: (.+?)\nVariantlar: (.+?)\nDüzgün: (.+)", quiz_text, re.DOTALL)
    
    for q_text, options_text, correct in questions:
        options = [opt.strip() for opt in options_text.split(" ") if opt.strip()]
        if len(options) != 4:
            continue
        await context.bot.send_poll(
            chat_id=config.CHAT_ID,
            question=q_text,
            options=options,
            type='quiz',
            correct_option_id=["A","B","C","D"].index(correct.strip()[0])
        )

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

    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: app.create_task(send_daily_words(app.bot)), 'cron', hour=10, minute=0)
    scheduler.add_job(lambda: app.create_task(send_grammar_topic(app.bot)), 'cron', hour=14, minute=0)
    scheduler.add_job(lambda: app.create_task(send_daily_quiz(app.bot)), 'cron', hour=19, minute=0)
    scheduler.start()

    print("Bot işə düşdü 👍")
    app.run_polling()
