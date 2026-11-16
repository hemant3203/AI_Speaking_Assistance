"""The daily challenge: one topic a day, the same for everyone, spoken for 3 or 5 minutes for bonus XP."""
import hashlib
import random
from dataclasses import dataclass
from datetime import date
from typing import Any

# A take counts when the speaker fills most of the time. Insisting on every second would fail people
# who finish their point a little early, which is good speaking, not a reason to lose the bonus.
MIN_SHARE_OF_TARGET = 0.8


@dataclass(frozen=True)
class ChallengeLength:
    """One way to take on the challenge, and what completing it pays."""

    seconds: int
    xp: int
    sparks: int

    @property
    def min_seconds(self) -> int:
        """The speaking time that completes the challenge."""
        return round(self.seconds * MIN_SHARE_OF_TARGET)


LENGTHS = {length.seconds: length for length in (ChallengeLength(180, 40, 10), ChallengeLength(300, 70, 15))}


@dataclass(frozen=True)
class Challenge:
    """One day's challenge topic, in both languages."""

    mode: str
    topic: str
    topic_hi: str

    def topic_for(self, language: str) -> str:
        """Return the topic in the language the speaker will use."""
        return self.topic_hi if language == "hi" else self.topic


CHALLENGES = [
    Challenge(
        "impromptu",
        "If you could add one new festival to the calendar, what would it celebrate?",
        "अगर आप कैलेंडर में एक नया त्योहार जोड़ सकें, तो वह किस बात का जश्न होगा?",
    ),
    Challenge(
        "storytelling",
        "Tell the story of a time you got completely lost",
        "उस समय की कहानी सुनाइए जब आप पूरी तरह रास्ता भटक गए थे",
    ),
    Challenge(
        "persuasion",
        "Convince us that everyone should learn a second language",
        "हमें समझाइए कि हर किसी को एक दूसरी भाषा क्यों सीखनी चाहिए",
    ),
    Challenge(
        "presentation",
        "Explain how your favourite dish is made, step by step",
        "अपना पसंदीदा खाना बनाने का तरीका कदम-दर-कदम समझाइए",
    ),
    Challenge(
        "interview",
        "Tell me about a mistake you made and what you learned from it",
        "अपनी किसी गलती के बारे में बताइए और उससे आपने क्या सीखा",
    ),
    Challenge(
        "impromptu",
        "The most underrated invention in everyday life",
        "रोज़मर्रा की ज़िंदगी का सबसे कम सराहा गया आविष्कार",
    ),
    Challenge(
        "storytelling",
        "Describe the best day of your last holiday",
        "अपनी पिछली छुट्टियों के सबसे अच्छे दिन का वर्णन कीजिए",
    ),
    Challenge(
        "persuasion",
        "Argue for or against starting school one hour later",
        "स्कूल एक घंटा देर से शुरू होने के पक्ष या विपक्ष में अपनी बात रखिए",
    ),
    Challenge(
        "presentation",
        "Teach us a skill you know well",
        "कोई ऐसा हुनर सिखाइए जो आप अच्छी तरह जानते हैं",
    ),
    Challenge(
        "interview",
        "Why should someone hire you for your dream job?",
        "आपकी सपनों की नौकरी के लिए कोई आपको क्यों चुने?",
    ),
    Challenge(
        "impromptu",
        "What would your perfect weekend look like?",
        "आपका एकदम सही वीकेंड कैसा होगा?",
    ),
    Challenge(
        "storytelling",
        "A person who changed the way you think",
        "एक इंसान जिसने आपके सोचने का तरीका बदल दिया",
    ),
    Challenge(
        "persuasion",
        "Convince a friend to put their phone away for a whole day",
        "किसी दोस्त को पूरे एक दिन फ़ोन से दूर रहने के लिए मनाइए",
    ),
    Challenge(
        "presentation",
        "Introduce your hometown to a group of tourists",
        "पर्यटकों के एक समूह को अपने शहर से परिचित कराइए",
    ),
    Challenge(
        "interview",
        "Describe a time your team disagreed and how you handled it",
        "ऐसे समय के बारे में बताइए जब आपकी टीम में मतभेद था और आपने उसे कैसे सँभाला",
    ),
    Challenge(
        "impromptu",
        "Is it better to be a big fish in a small pond or a small fish in a big pond?",
        "छोटे तालाब की बड़ी मछली बनना बेहतर है या बड़े तालाब की छोटी मछली?",
    ),
    Challenge(
        "storytelling",
        "The first time you did something that scared you",
        "पहली बार जब आपने कुछ ऐसा किया जिससे आपको डर लगता था",
    ),
    Challenge(
        "persuasion",
        "Make the case for reading more books",
        "ज़्यादा किताबें पढ़ने के पक्ष में अपनी बात रखिए",
    ),
    Challenge(
        "presentation",
        "Explain how to save money as a student",
        "एक छात्र के रूप में पैसे बचाने का तरीका समझाइए",
    ),
    Challenge(
        "interview",
        "Where do you see yourself in five years?",
        "पाँच साल बाद आप खुद को कहाँ देखते हैं?",
    ),
    Challenge(
        "impromptu",
        "If animals could talk, which one would be the rudest?",
        "अगर जानवर बोल पाते, तो सबसे बदतमीज़ कौन सा होता?",
    ),
    Challenge(
        "storytelling",
        "A festival or celebration you will never forget",
        "एक त्योहार या जश्न जिसे आप कभी नहीं भूलेंगे",
    ),
    Challenge(
        "persuasion",
        "Convince us to try your favourite hobby",
        "हमें अपना पसंदीदा शौक आज़माने के लिए मनाइए",
    ),
    Challenge(
        "presentation",
        "Walk us through how you plan a busy day",
        "बताइए कि आप एक व्यस्त दिन की योजना कैसे बनाते हैं",
    ),
    Challenge(
        "interview",
        "What is your greatest strength, and when did it make a difference?",
        "आपकी सबसे बड़ी ताकत क्या है, और उसने कब फ़र्क डाला?",
    ),
    Challenge(
        "impromptu",
        "The best advice you could give a new college student",
        "कॉलेज के नए छात्र को आप सबसे अच्छी सलाह क्या देंगे?",
    ),
    Challenge(
        "storytelling",
        "Tell us about a meal that brought people together",
        "एक ऐसे खाने के बारे में बताइए जिसने लोगों को एक साथ ला दिया",
    ),
    Challenge(
        "persuasion",
        "Should public transport be free?",
        "क्या सार्वजनिक परिवहन मुफ़्त होना चाहिए?",
    ),
    Challenge(
        "presentation",
        "Explain something you read in the news this week to a ten-year-old",
        "इस हफ़्ते की किसी खबर को दस साल के बच्चे को समझाइए",
    ),
    Challenge(
        "interview",
        "Tell me about a goal you achieved and how you got there",
        "अपने किसी हासिल किए लक्ष्य के बारे में बताइए और आप वहाँ तक कैसे पहुँचे",
    ),
]

_EPOCH = date(2026, 1, 1)


def challenge_for(day: date) -> Challenge:
    """Return a day's challenge.

    Days walk through a shuffled copy of the list, and each pass is shuffled differently, so a topic
    never repeats until every other one has had its day. sha256 keeps the order the same across restarts.
    """
    index = (day - _EPOCH).days
    cycle, position = divmod(index, len(CHALLENGES))
    order = list(range(len(CHALLENGES)))
    random.Random(hashlib.sha256(f"challenge-cycle:{cycle}".encode()).digest()).shuffle(order)
    return CHALLENGES[order[position]]


def dedupe_key(day: date) -> str:
    """The ledger key that pays out a day's challenge exactly once."""
    return f"challenge:{day.isoformat()}"


def challenge_view(
    day: date, mode_name: str, session_id: str | None, score: int | None, completed: bool, total_completed: int
) -> dict[str, Any]:
    """Return the day's challenge as the profile shows it."""
    challenge = challenge_for(day)
    return {
        "date": day.isoformat(),
        "mode": challenge.mode,
        "mode_name": mode_name,
        "topic": challenge.topic,
        "topic_hi": challenge.topic_hi,
        "options": [
            {"target_seconds": length.seconds, "min_seconds": length.min_seconds, "xp": length.xp, "sparks": length.sparks}
            for length in LENGTHS.values()
        ],
        "completed": completed,
        "session_id": session_id,
        "score": score,
        "total_completed": total_completed,
    }
