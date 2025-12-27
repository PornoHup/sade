import logging
import random
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import openai
import config

# OpenAI API açarı
openai.api_key = config.OPENAI_API_KEY

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ---------------- Sözlər və qrammatika ----------------
daily_words_list = {
    "Salam": "سلام",
    "Necəsən?": "چطوری؟",
    "Yaxşıyam": "خوبم",
    "Ev": "خانه",
    "Məktəb": "مدرسه",
    "Kitab": "کتاب",
    "Qələm": "قلم",
    "Maşın": "ماشین",
    "Dost": "دوست",
    "Sevgi": "عشق"
}

grammar_topics = {
    "Fars dilində feillərin cəm forması": "صرف افعال به شکل جمع",
    "Fars dilində sifətlərin istifadəsi": "استفاده از صفت‌ها در فارسی",
    "Fars dilində sual cümlələri": "جملات پرسشی در فارسی"
}

daily_tracker = {"words": [], "grammar": ""}

# ---------------- OpenAI sorğusu ----------------
async def ask_openai(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response['choices'][0]['message']['content']

# ---------------- SCHEDULED MESSAGES ----------------
async def send_daily_words(context: ContextTypes.DEFAULT_TYPE):
    words = random.sample(list(daily_words_list.items()), 10)
    daily_tracker['words'] = words
    msg_lines = [f"{az} — {fa}" for az, fa in words]
    msg = "📚 Bu günün 10 yeni sözü:\n" + "\n".join(msg_lines)
    await context.bot.send_message(chat_id=config.CHAT_ID, text=msg)

async def send_grammar_topic(context: ContextTypes.DEFAULT_TYPE):
    az, fa = random.choice(list(grammar_topics.items()))
    daily_tracker['grammar'] = (az, fa)
    msg = f"📝 Günorta qrammatika mövzusu:\n{az}\n{fa}"
    await context.bot.send_message(chat_id=config.CHAT_ID, text=msg)

async def send_daily_quiz(context: ContextTypes.DEFAULT_TYPE):
    words = daily_tracker.get('words', [])
    grammar = daily_tracker.get('grammar', None)
    if not words or not grammar:
        return

    words_text = "\n".join([f"{az} — {fa}" for az, fa in words])
    grammar_text = f"{grammar[0]} — {grammar[1]}"

    prompt = f"Bu sözlər və qrammatika mövzusu üçün 3 sual yarat. Hər sual üçün 4 cavab variantı ver. Variantlar həm Az həm Fars dilində olsun. Düzgün cavabı qeyd et.\nSözlər:\n{words_text}\nQrammatika:\n{grammar_text}"
    quiz_text = await ask_openai(prompt)

    questions = re.findall(r"Sual \d+: (.+?)\nVariantlar: (.+?)\nDüzgün: (.+)", quiz_text, re.DOTALL)
    
    for q_text, options_text, correct in questions:
        options = [opt.strip() for opt in options_text.split(" ") if opt.strip()]
        if len(options) != 4:
            continue
        try:
            await context.bot.send_poll(
                chat_id=config.CHAT_ID,
                question=q_text,
                options=options,
                type='quiz',
                correct_option_id=["A","B","C","D"].index(correct.strip()[0])
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

    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: app.create_task(send_daily_words(app.bot)), 'cron', hour=10, minute=0)  # Səhər 10:00
    scheduler.add_job(lambda: app.create_task(send_grammar_topic(app.bot)), 'cron', hour=14, minute=0)   # Günorta 14:00
    scheduler.add_job(lambda: app.create_task(send_daily_quiz(app.bot)), 'cron', hour=19, minute=0)     # Axşam 19:00
    scheduler.start()

    print("Bot işə düşdü 👍")
    app.run_polling()
