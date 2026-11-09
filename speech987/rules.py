"""Versioned, explainable speech pattern rules.

Only patterns with safe_remove=True are candidates for deterministic deletion.
They MUST match a standalone, semantically empty lead-in at the *start of a line*
and leave meaningful text on the same line. All other rules are audit-only.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    pattern: str
    weight: int = 1
    safe_remove: bool = False
    language: str = "both"
    description: str = ""


def R(id: str, category: str, pattern: str, weight: int = 1,
      safe_remove: bool = False, language: str = "both") -> Rule:
    return Rule(id, category, pattern, weight, safe_remove, language)


# \b in Python regexes uses Unicode word boundaries; [ \t] must not eat newlines.
# End-of-line lookahead protects single-line statements consisting of only a lead-in.
RULES: tuple[Rule, ...] = (
    # Low-information stage directions that can be dropped without changing a claim.
    R("ru_stage_question", "theatrical_hook",
      r"(?im)^[ \t]*(?:и знаешь, что особенно важно|а знаешь, что самое интересное|а знаешь, что особенно любопытно|а теперь самое интересное|а теперь самое любопытное)\?[ \t]*(?=[^\n]*\S)",
      3, True, "ru"),
    R("ru_stage_statement", "theatrical_hook",
      r"(?im)^[ \t]*(?:и вот здесь начинается самое интересное|но дальше(?:\s*[-—]\s*|\s+)интереснее|и вот тут начинается главное)[.!:][ \t]*(?=[^\n]*\S)",
      2, True, "ru"),
    R("ru_honesty_leadin", "self_advertised_honesty",
      r"(?im)^[ \t]*(?:скажу честно|скажу прямо|буду с тобой предельно откровенен|не буду ходить вокруг да около|если честно|честно говоря)[,:—–][ \t]*(?=[^\n]*\S)",
      2, True, "ru"),
    R("ru_navigation_leadin", "navigation",
      r"(?im)^[ \t]*(?:давай разберёмся|давай разберемся|давай разложим всё по полочкам|давай посмотрим на это подробнее)[.:][ \t]*(?=[^\n]*\S)",
      1, True, "ru"),
    R("en_stage_leadin", "theatrical_hook",
      r"(?im)^[ \t]*(?:here(?:'|’)s the thing|here(?:'|’)s the kicker|and you know what(?:'|’)s interesting|but here(?:'|’)s where it gets interesting)[.:!?][ \t]*(?=[^\n]*\S)",
      3, True, "en"),
    R("en_honesty_leadin", "self_advertised_honesty",
      r"(?im)^[ \t]*(?:honestly|to be honest|let me be blunt|i(?:'|’)ll be honest|real talk)[,:—–][ \t]*(?=[^\n]*\S)",
      2, True, "en"),
    R("en_navigation_leadin", "navigation",
      r"(?im)^[ \t]*(?:let(?:'|’)s unpack this|let(?:'|’)s break this down)[.:][ \t]*(?=[^\n]*\S)",
      1, True, "en"),

    # Common phrases: detection does NOT imply automatic deletion.
    R("ru_thin_spot", "fake_insight",
      r"\b(?:ты (?:попала|попал|нащупала|нащупал) (?:в )?(?:очень )?(?:тонкое место|самую суть)|ты (?:затронула|затронул) (?:очень )?(?:тонкий|глубокий) (?:момент|вопрос))\b", 3, language="ru"),
    R("ru_deep_question", "fake_insight",
      r"\b(?:ты даже не представляешь, насколько|это гораздо глубже, чем кажется|ты подошла к самому сердцу проблемы|ты видишь то, чего другие не замечают)\b", 3, language="ru"),
    R("ru_insight_nuance", "fake_insight",
      r"\b(?:ты (?:очень )?точно (?:подметила|подметил|сформулировала|сформулировал)|ты уловила важный нюанс|тут ты (?:действительно )?копнула глубоко)\b", 2, language="ru"),
    R("en_insight", "fake_insight",
      r"\b(?:you(?:'|’)ve hit on something (?:deep|subtle)|you(?:'|’)re asking (?:the|a) (?:right|profound) question|that(?:'|’)s a surprisingly profound|you(?:'|’)ve put your finger on)\b", 3, language="en"),
    R("ru_hook_more", "theatrical_hook",
      r"\b(?:и вот здесь начинается самое интересное|и вот что особенно важно|но есть один нюанс|а теперь главный вопрос|и вот что действительно меняет картину|но вот в чём парадокс)\b", 2, language="ru"),
    R("en_hook_more", "theatrical_hook",
      r"\b(?:here(?:'|’)s the thing|here(?:'|’)s the kicker|but here(?:'|’)s where it gets interesting|and here(?:'|’)s the twist)\b", 2, language="en"),

    R("ru_negation_contrast", "rhetorical_antithesis",
      r"\b(?:это не просто\b[^\n.!?]{1,110}[.!?]\s*(?:это|а)\b|речь не (?:о|об)\b[^\n.!?]{1,100}[.!?]\s*речь\b)", 3, language="ru"),
    R("ru_not_but", "rhetorical_antithesis",
      r"\bне потому, что\b[^\n.!?]{1,100}[.!?]\s*а потому, что\b", 3, language="ru"),
    R("en_not_just", "rhetorical_antithesis",
      r"\b(?:it(?:'|’)s not just\b[^\n.!?]{1,100}[.!?]\s*it(?:'|’)s\b|this isn(?:'|’)t about\b[^\n.!?]{1,100}[.!?]\s*it(?:'|’)s about\b)", 3, language="en"),

    R("ru_reflexive_praise", "sycophancy",
      r"\b(?:ты абсолютно права|ты абсолютно прав|это невероятно зрелая позиция|это очень сильная мысль|ты задала блестящий вопрос|это говорит о твоей эмоциональной зрелости)\b", 3, language="ru"),
    R("ru_rare_flattery", "sycophancy",
      r"\b(?:мало кто способен|это редкий уровень осознанности|не каждый способен на подобное|у тебя редкая способность|это (?:действительно )?редкость)\b", 2, language="ru"),
    R("en_reflexive_praise", "sycophancy",
      r"\b(?:you(?:'|’)re absolutely right|you(?:'|’)ve asked a brilliant question|that(?:'|’)s a really insightful observation|you have a rare ability|and that(?:'|’)s rare)\b", 3, language="en"),

    R("ru_blanket_uncertainty", "unsupported_hedging",
      r"\b(?:я не могу утверждать(?: наверняка)?|нельзя однозначно сказать|это зависит от множества факторов|нет оснований с уверенностью утверждать|однозначного ответа (?:на этот вопрос )?не существует)\b", 1, language="ru"),
    R("ru_double_hedge", "unsupported_hedging",
      r"\b(?:возможно|вероятно),?\s+(?:это\s+)?(?:потенциально\s+)?может\s+(?:быть|указывать|свидетельствовать)\b", 2, language="ru"),
    R("en_hedge", "unsupported_hedging",
      r"\b(?:it depends on many factors|it(?:'|’)s difficult to say definitively|i can(?:'|’)t say for certain|potentially could perhaps)\b", 1, language="en"),

    R("ru_unasked_therapy", "unsolicited_therapy",
      r"\b(?:давай (?:немного )?притормозим|сделай глубокий вдох|давай сначала выдохнем|давай немного заземлимся|ты не сломана|ты не сломан|ты не сходишь с ума|твои чувства абсолютно валидны)\b", 3, language="ru"),
    R("ru_therapy_more", "unsolicited_therapy",
      r"\b(?:давай создадим безопасное пространство|ты имеешь полное право так чувствовать|я хочу бережно отнестись к твоим переживаниям|попробуй побыть с этим ощущением)\b", 2, language="ru"),
    R("en_unasked_therapy", "unsolicited_therapy",
      r"\b(?:take a deep breath|let(?:'|’)s take a step back|you(?:'|’)re not broken|your feelings are valid|let(?:'|’)s ground ourselves|hold space for that feeling)\b", 3, language="en"),

    R("ru_teacher_tone", "paternalistic_tone",
      r"\b(?:я хочу, чтобы ты правильно меня поняла|давай вернёмся к реальности|сейчас важно не путать две разные вещи|скажу мягко, но твёрдо|я намеренно замедлю объяснение|нам нужно установить здоровые рамки)\b", 2, language="ru"),
    R("en_teacher_tone", "paternalistic_tone",
      r"\b(?:let me gently correct you|i want you to understand this clearly|let(?:'|’)s bring this back to reality)\b", 2, language="en"),

    R("ru_emotional_performance", "performed_emotion",
      r"\b(?:и вот что меня по-настоящему трогает|мне очень откликается эта мысль|я не могу пройти мимо твоих слов|в твоих словах ощущается особая энергия|это действительно резонирует)\b", 2, language="ru"),
    R("en_emotional_performance", "performed_emotion",
      r"\b(?:that really resonates with me|this genuinely moves me|what strikes me most is)\b", 2, language="en"),

    R("ru_philosophical_closing", "pseudo_profundity",
      r"\b(?:и в этом вся суть|в этом заключается главный парадокс|вот что на самом деле имеет значение|и именно здесь раскрывается подлинный смысл|в конечном счёте всё сводится к одному)\b", 2, language="ru"),
    R("en_philosophical_closing", "pseudo_profundity",
      r"\b(?:and that(?:'|’)s what really matters|that(?:'|’)s the heart of it|the deeper truth is|and therein lies the paradox)\b", 2, language="en"),

    R("ru_corporate_padding", "corporate_padding",
      r"\b(?:открывает новые горизонты|меняет правила игры|уникальная экосистема|комплексное решение|качественно новый уровень|создаёт прочную основу для будущего)\b", 1, language="ru"),
    R("en_corporate_padding", "corporate_padding",
      r"\b(?:game[- ]changer|seamless integration|unlock its full potential|a robust and holistic approach|a rich tapestry of)\b", 1, language="en"),

    R("ru_conclusion", "unnecessary_wrapup",
      r"\b(?:подводя итог всему вышесказанному|главное, что нужно запомнить|в сухом остатке|если свести всё к одному предложению)\b", 1, language="ru"),
    R("en_conclusion", "unnecessary_wrapup",
      r"\b(?:in conclusion|to sum it all up|the key takeaway is)\b", 1, language="en"),
    R("ru_question_answer", "scripted_rhetorical_qna",
      r"\b(?:почему|в чём подвох|результат)\?\s*(?:потому что|всё просто|ответ|он)\b", 1, language="ru"),
    R("en_question_answer", "scripted_rhetorical_qna",
      r"\b(?:why|the result|the problem)\?\s*(?:because|simple|it(?:'|’)s)\b", 1, language="en"),

    R("ru_marketing_honesty", "self_advertised_honesty",
      r"\b(?:буду с тобой предельно откровенен|мой честный ответ|скажу прямо, без сглаживания углов|сейчас будет жёстко, но честно)\b", 2, language="ru"),
    R("en_marketing_honesty", "self_advertised_honesty",
      r"\b(?:to be completely honest|let me be absolutely clear|i(?:'|’)ll be brutally honest)\b", 2, language="en"),

    R("ru_fiction_eye", "fiction_cliche",
      r"\b(?:в его глазах мелькнуло что-то нечитаемое|мир сузился до одного мгновения|время словно остановилось|тишина повисла тяжёлым покрывалом|слова остались невысказанными)\b", 1, language="ru"),
    R("ru_fiction_air", "fiction_cliche",
      r"\b(?:воздух между ними словно сгустился|что-то внутри него дрогнуло|в этом жесте было больше, чем в тысяче слов)\b", 1, language="ru"),
    R("en_fiction_cliche", "fiction_cliche",
      r"\b(?:the air between them grew thick|something unreadable flashed in his eyes|time seemed to stand still)\b", 1, language="en"),

    R("ru_automatic_outro", "unnecessary_followup",
      r"\b(?:если хочешь, я могу дополнительно|могу также помочь тебе|можем пойти ещё дальше)\b", 1, language="ru"),
    R("en_automatic_outro", "unnecessary_followup",
      r"\b(?:if you(?:'|’)d like, i can also|let me know if you(?:'|’)d like me to)\b", 1, language="en"),

    R("ru_process_apology", "process_theatre",
      r"\b(?:приношу извинения за возникшую путаницу|благодарю за уточнение|в предыдущем ответе я допустил неточность|позволь мне переформулировать)\b", 1, language="ru"),
    R("en_process_apology", "process_theatre",
      r"\b(?:thank you for pointing that out|i apologize for any confusion|let me rephrase that more accurately)\b", 1, language="en"),
)
