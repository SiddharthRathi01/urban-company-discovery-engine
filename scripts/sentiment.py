"""Text-first sentiment labelling for review text (Positive / Negative / Neutral / Mixed / Uncertain).

Method (documented in the workbook README):
 1. VADER lexicon extended with home-services domain terms scores each sentence/clause of title+text.
 2. Mixed  = at least one clearly positive AND one clearly negative sentence/clause.
 3. Positive / Negative = overall text polarity beyond a threshold with no strong opposing clause.
 4. Neutral = no clear polarity (questions, enquiries, factual statements).
 5. Star rating is used ONLY as a tie-breaker when the text itself carries no polarity (method says 'rating tie-break').
 6. Uncertain = text mostly non-English/Hinglish (lexicon unreliable) or text polarity strongly contradicts the rating.
"""
import re
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_an = SentimentIntensityAnalyzer()
_an.lexicon.update({
    # negative service-failure vocabulary VADER lacks or under-weights
    "noshow": -2.5, "scam": -3.0, "scammed": -3.0, "fraud": -3.0, "fraudulent": -3.0, "cheat": -2.8, "cheated": -2.8, "cheating": -2.8,
    "overcharge": -2.2, "overcharged": -2.2, "overcharging": -2.2, "overpriced": -2.0, "expensive": -1.2, "costly": -1.2, "exorbitant": -2.4,
    "pathetic": -3.0, "worst": -3.2, "rude": -2.4, "arrogant": -2.2, "unprofessional": -2.6, "unreliable": -2.4, "unresponsive": -2.2,
    "damaged": -2.2, "damage": -1.8, "broke": -1.8, "broken": -1.8, "ruined": -2.6, "delay": -1.4, "delayed": -1.6, "late": -1.2,
    "cancelled": -1.6, "canceled": -1.6, "cancels": -1.4, "cancelling": -1.4, "cancellation": -1.0, "reschedule": -0.8, "rescheduled": -1.0,
    "refund": -0.6, "waste": -2.0, "wasted": -2.0, "useless": -2.6, "horrible": -3.0, "terrible": -3.0, "disappointed": -2.4,
    "disappointing": -2.4, "unhappy": -2.0, "dissatisfied": -2.2, "harassment": -2.8, "harassed": -2.6, "misbehaved": -2.4, "misbehavior": -2.4,
    "unhelpful": -2.2, "incompetent": -2.6, "negligent": -2.4, "leaking": -1.4, "faulty": -2.0, "defective": -2.2, "unresolved": -2.0,
    "poor": -2.2, "bad": -2.4, "never": -0.8, "didn't": -0.4, "didnt": -0.4, "not": -0.3,
    # positive service vocabulary
    "punctual": 2.2, "polite": 2.0, "courteous": 2.2, "professional": 1.6, "thorough": 1.8, "neat": 1.6, "clean": 1.0, "cleaned": 1.0,
    "satisfied": 2.2, "satisfactory": 1.8, "recommend": 2.0, "recommended": 2.0, "excellent": 3.0, "amazing": 3.0, "awesome": 3.0,
    "helpful": 2.2, "prompt": 1.8, "promptly": 1.8, "efficient": 2.0, "reliable": 2.2, "convenient": 2.0, "hassle-free": 2.2, "smooth": 1.8,
    "seamless": 2.2, "affordable": 1.8, "wonderful": 3.0, "fantastic": 3.0, "brilliant": 2.8, "superb": 3.0, "lovely": 2.4, "delighted": 2.8,
    "hardworking": 2.0, "skilled": 2.0, "trained": 1.2, "trustworthy": 2.2, "genuine": 1.6, "friendly": 2.0, "responsive": 2.0, "quick": 1.4, "quickly": 1.4,
})
NEG_NO_SHOW = re.compile(r"(?:did(?:n't| not)|never|not|yet to|hasn't|haven't|hasn’t|didn’t)\s+(?:turn(?:ed)?\s*up|show(?:ed)?\s*up|come|came|arrive[d]?|reach(?:ed)?|visit(?:ed)?|call(?:ed)?|respond(?:ed)?|reply|replied|attend(?:ed)?)|no[- ]show|didn[’']t (?:turn|show)|never came|not (?:come|came|arrived)", re.I)
NEG_PHRASES = re.compile(r"(?:can[’']?t|cannot|unable to|not able to|couldn[’']?t|no way to|impossible to|difficult to)\s+(?:talk|speak|contact|reach|connect|book|get|cancel|find|change|use|login|log)|no (?:number|option|helpline|customer care|human|slot|way)|not (?:showing|working|opening|loading|available|serviceable)|doesn[’']?t work|isn[’']?t working|not (?:satisf|happy|good|worth|professional|well|clean|working|resolved|refunded|received|available|helpful|up to)|money (?:was )?(?:deducted|debited|taken)|(?:no|not getting) (?:refund|response|reply|help|support|slot|slots)|still (?:waiting|pending|not)|waste of (?:time|money)|too (?:high|costly|expensive|much)|not recommend|never again|don[’']t (?:book|use|go|waste|recommend)|do not (?:book|use|go|recommend)|stay away|avoid", re.I)
POS_PHRASES = re.compile(r"(?:highly |would |will |definitely )?recommend(?:ed)?|very good|really good|great (?:service|job|work|experience|app)|well done|on time|on-time|good (?:service|work|job|experience|app|quality)|satisfied with|happy with|thank(?:s| you)|best (?:service|app|experience)|love (?:it|the|this)|value for money|worth (?:it|the)", re.I)
CONTRAST = re.compile(r"\b(?:but|however|although|though|except|yet|unfortunately|only issue|only problem|one (?:issue|problem|complaint)|apart from|otherwise|still)\b", re.I)
QUESTION = re.compile(r"\?|\b(?:how (?:do|can|to)|is there|do you|does (?:it|anyone|urban)|can (?:i|you|we|someone)|any(?:one)? (?:know|recommend|suggest)|which is better|should i|looking for|need(?:ed)? (?:a|an|to)|want(?:ed)? to know|please (?:call|contact|help))", re.I)
HINGLISH = re.compile(r"\b(?:hai|hain|nahi|nahin|nhi|bahut|bohot|kya|kyu|kyun|karo|karna|kiya|mera|meri|aap|apka|aapka|achha|accha|bekar|bakwas|paisa|paise|wala|wale|toh|kaam|abhi|aur|lekin|mujhe|hum|ho|gaya|gayi|raha|rahi|tha|thi|ka|ki|ke)\b", re.I)

SENT_SPLIT = re.compile(r"(?<=[\.\!\?\n])\s+|\s*;\s*|\s+(?=but\b|however\b|although\b|though\b|unfortunately\b)", re.I)


def _score(s):
    c = _an.polarity_scores(s)["compound"]
    if NEG_NO_SHOW.search(s): c = min(c, 0) - 0.55
    if NEG_PHRASES.search(s): c -= 0.6
    if POS_PHRASES.search(s): c += 0.30
    return max(-1.0, min(1.0, c))


def _nonenglish(t):
    letters = re.findall(r"[^\W\d_]", t)
    if not letters: return True
    nonlatin = sum(1 for ch in letters if ord(ch) > 0x024F)
    if nonlatin / len(letters) > 0.3: return True
    words = re.findall(r"[A-Za-z']+", t.lower())
    return len(words) >= 4 and sum(1 for w in words if HINGLISH.fullmatch(w)) / len(words) > 0.22


def label(title, text, rating):
    """Return (label, method, score). rating may be None/NaN."""
    full = ((title or "") + ". " + (text or "")).strip()
    r = None if rating is None or rating != rating else float(rating)
    if not re.search(r"[A-Za-zऀ-ॿ]", full):
        return "Uncertain", "text has no readable words (emoji/symbols only)", 0.0
    if _nonenglish(full):
        return "Uncertain", "text mostly non-English/Hinglish - English lexicon unreliable; needs human/LLM read", 0.0
    parts = [p.strip() for p in SENT_SPLIT.split(full) if p and len(p.strip()) > 2]
    scores = [_score(p) for p in parts] or [0.0]
    overall = _score(full)
    avg = sum(scores) / len(scores)
    pos = [s for s in scores if s >= 0.35]; neg = [s for s in scores if s <= -0.35]
    strong_pos = max(scores) if scores else 0; strong_neg = min(scores) if scores else 0
    polarity = 0.5 * overall + 0.5 * avg
    if pos and neg and strong_pos >= 0.5 and strong_neg <= -0.5 and abs(polarity) < 0.45:
        lab, m = "Mixed", "text: positive and negative statements both present"
    elif polarity >= 0.25 and not (neg and strong_neg <= -0.55):
        lab, m = "Positive", "text lexicon"
    elif polarity <= -0.25 and not (pos and strong_pos >= 0.55):
        lab, m = "Negative", "text lexicon"
    elif neg and pos and abs(polarity) < 0.25:
        lab, m = "Mixed", "text: weaker positive and negative statements both present"
    else:
        # text carries no clear polarity
        if r is not None and not QUESTION.search(full) and len(re.findall(r"\w+", full)) <= 14:
            if r >= 4: lab, m = "Positive", "rating tie-break (text neutral)"
            elif r <= 2: lab, m = "Negative", "rating tie-break (text neutral)"
            else: lab, m = "Neutral", "text neutral; 3-star rating"
        elif r is not None and r <= 1 and not QUESTION.search(full):
            lab, m = "Negative", "rating tie-break (text neutral)"
        else:
            lab, m = "Neutral", "text: no clear polarity (enquiry/factual)"
    # contradiction with rating -> do not force a label
    if r is not None:
        if lab == "Positive" and r <= 1.5 and "text lexicon" == m and polarity < 0.6:
            lab, m = "Uncertain", "text reads positive but rating is 1 star (possible sarcasm / mis-rating)"
        elif lab == "Negative" and r >= 4.5 and "text lexicon" == m and polarity > -0.6:
            lab, m = "Uncertain", "text reads negative but rating is 5 stars (possible mis-rating)"
    return lab, m, round(polarity, 3)
