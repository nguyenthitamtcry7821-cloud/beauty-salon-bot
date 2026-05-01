# fix_portfolio.py — патч: заменяет сломанный блок портфолио корректным UTF-8 кодом

OLD = open("main.py", "r", encoding="utf-8").read()

# Ищем начало и конец блока
START_MARKER = "# ============================================================\n# ПОРТФОЛИО\n# ============================================================"
END_MARKER   = "# ============================================================\n# ПЕРЕНОС / ОТМЕНА (USER SIDE)"

i_start = OLD.find(START_MARKER)
i_end   = OLD.find(END_MARKER)

if i_start == -1:
    print("PORTFOLIO BLOCK NOT FOUND — вставляем перед ПЕРЕНОС")
    i_start = i_end  # вставим прямо перед

NEW_BLOCK = '''# ============================================================
# ПОРТФОЛИО
# ============================================================
@bot.message_handler(func=lambda m: m.text == "\U0001f31f \u041f\u043e\u0440\u0442\u0444\u043e\u043b\u0438\u043e")
def cmd_portfolio(message):
    """\u041e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0435\u0442 \u043a\u0440\u0430\u0441\u0438\u0432\u044b\u0439 \u0430\u043b\u044c\u0431\u043e\u043c \u0440\u0430\u0431\u043e\u0442 \u0441\u0430\u043b\u043e\u043d\u0430."""
    cid = message.chat.id

    # \u0422\u0435\u043a\u0441\u0442-\u043f\u0440\u0435\u0437\u0435\u043d\u0442\u0430\u0446\u0438\u044f
    bot.send_message(
        cid,
        "\U0001f3a8 *\u041d\u0430\u0448\u0435 \u043f\u043e\u0440\u0442\u0444\u043e\u043b\u0438\u043e*\n\n"
        "\u041c\u044b \u0433\u043e\u0440\u0434\u0438\u043c\u0441\u044f \u043a\u0430\u0436\u0434\u043e\u0439 \u0440\u0430\u0431\u043e\u0442\u043e\u0439, \u043a\u043e\u0442\u043e\u0440\u0430\u044f \u0432\u044b\u0445\u043e\u0434\u0438\u0442 \u0438\u0437 \u043d\u0430\u0448\u0438\u0445 \u0440\u0443\u043a. "
        "\u041a\u0430\u0436\u0434\u044b\u0439 \u0432\u0438\u0437\u0438\u0442 \u2014 \u044d\u0442\u043e \u0432\u043d\u0438\u043c\u0430\u043d\u0438\u0435 \u043a \u0434\u0435\u0442\u0430\u043b\u044f\u043c, "
        "\u0438\u043d\u0434\u0438\u0432\u0438\u0434\u0443\u0430\u043b\u044c\u043d\u044b\u0439 \u043f\u043e\u0434\u0445\u043e\u0434 \u0438 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442, "
        "\u043a\u043e\u0442\u043e\u0440\u044b\u0439 \u0433\u043e\u0432\u043e\u0440\u0438\u0442 \u0441\u0430\u043c \u0437\u0430 \u0441\u0435\u0431\u044f.\n\n"
        "\U0001f487\u200d\u2640\ufe0f *\u0412\u043e\u043b\u043e\u0441\u044b* \u2014 \u0431\u0430\u043b\u0430\u044f\u0436, \u043e\u043a\u0440\u0430\u0448\u0438\u0432\u0430\u043d\u0438\u0435, \u0443\u043a\u043b\u0430\u0434\u043a\u0438\n"
        "\U0001f485 *\u041c\u0430\u043d\u0438\u043a\u044e\u0440* \u2014 \u043d\u0430\u0439\u043b-\u0430\u0440\u0442, \u0430\u043f\u043f\u0430\u0440\u0430\u0442\u043d\u044b\u0435 \u043f\u043e\u043a\u0440\u044b\u0442\u0438\u044f\n"
        "\u2728 *\u041a\u043e\u0441\u043c\u0435\u0442\u043e\u043b\u043e\u0433\u0438\u044f* \u2014 \u0447\u0438\u0441\u0442\u043a\u0430, \u043f\u0438\u043b\u0438\u043d\u0433, \u0443\u0445\u043e\u0434 \u0437\u0430 \u043a\u043e\u0436\u0435\u0439\n\n"
        "_\u0421\u043c\u043e\u0442\u0440\u0438\u0442\u0435 \u043d\u0430\u0448\u0438 \u0440\u0430\u0431\u043e\u0442\u044b \u043d\u0438\u0436\u0435 \u2b07\ufe0f_",
        parse_mode="Markdown"
    )

    # MediaGroup \u2014 \u0430\u043b\u044c\u0431\u043e\u043c \u0438\u0437 3 \u0444\u043e\u0442\u043e Unsplash
    PORTFOLIO_PHOTOS = [
        (
            "https://images.unsplash.com/photo-1604654894610-df63bc536371?w=800",
            "\U0001f485 *\u041d\u0430\u0439\u043b-\u0430\u0440\u0442* \u2014 \u0440\u043e\u0437\u043e\u0432\u043e-\u0437\u043e\u043b\u043e\u0442\u043e\u0439 \u0434\u0438\u0437\u0430\u0439\u043d. \u041c\u0430\u0441\u0442\u0435\u0440: \u041e\u043b\u044c\u0433\u0430"
        ),
        (
            "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=800",
            "\U0001f487\u200d\u2640\ufe0f *\u0411\u0430\u043b\u0430\u044f\u0436* \u2014 \u043f\u043b\u0430\u0432\u043d\u044b\u0439 \u043f\u0435\u0440\u0435\u0445\u043e\u0434 \u0446\u0432\u0435\u0442\u0430. \u041c\u0430\u0441\u0442\u0435\u0440: \u0410\u043d\u043d\u0430"
        ),
        (
            "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?w=800",
            "\u2728 *\u041a\u043e\u0441\u043c\u0435\u0442\u043e\u043b\u043e\u0433\u0438\u044f* \u2014 \u0441\u0438\u044f\u044e\u0449\u0430\u044f \u043a\u043e\u0436\u0430 \u043f\u043e\u0441\u043b\u0435 \u043f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u044b. \u041c\u0430\u0441\u0442\u0435\u0440: \u0415\u043b\u0435\u043d\u0430"
        ),
    ]
    media = []
    for i, (url, caption) in enumerate(PORTFOLIO_PHOTOS):
        media.append(
            types.InputMediaPhoto(
                media=url,
                caption=caption if i == 0 else "",
                parse_mode="Markdown"
            )
        )
    try:
        bot.send_media_group(cid, media)
    except Exception as e:
        logger.error(f"\u041f\u043e\u0440\u0442\u0444\u043e\u043b\u0438\u043e: \u043e\u0448\u0438\u0431\u043a\u0430 MediaGroup: {e}")
        bot.send_message(
            cid,
            "\u0424\u043e\u0442\u043e \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e. "
            "\u0417\u0430\u043f\u0438\u0448\u0438\u0442\u0435 \u043d\u0430\u043c \u2014 \u043c\u044b \u043f\u043e\u043a\u0430\u0436\u0435\u043c \u0432\u0441\u0451 \u043b\u0438\u0447\u043d\u043e! \u2728"
        )

'''

# Заменяем (или вставляем) блок
if OLD.find(START_MARKER) != -1:
    NEW = OLD[:i_start] + NEW_BLOCK + OLD[i_end:]
else:
    NEW = OLD[:i_start] + NEW_BLOCK + OLD[i_end:]

open("main.py", "w", encoding="utf-8").write(NEW)
print("OK: portfolio block replaced")
print(f"  old size: {len(OLD)}, new size: {len(NEW)}")
