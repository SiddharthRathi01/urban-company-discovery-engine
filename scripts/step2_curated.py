"""Curated return-behaviour classes. Every Explicit Return / Explicit Non-Return record below was read individually by the analyst
(phrase rules over-fired on 'second service' rework visits, 'uninstall' of ACs, advice like 'don't use this app', etc.).
Definitions:
  Explicit Return     = reviewer reports repeat/ongoing use of Urban Company, OR states they will book again / prefer the same professional again.
  Explicit Non-Return = reviewer states, in the first person, that they will not use UC again, have stopped, switched, or uninstalled.
  Advice to others ('don't use this app') is NOT counted as non-return; it is a Behavioural Signal (warning).
IDs are record_id values in the Master file."""
import re

ER_REPORTED = """CC-0039 CC-0113 GP-0329 GP-0468 GP-0588 GP-0746 GP-0826 GP-0844 GP-0867 GP-0942 GP-1004 GP-1043 GP-1044 GP-1233 GP-1269 GP-1273 GP-1309
GP-1404 GP-1412 GP-1427 GP-1452 GP-1511 GP-1625 GP-1092 GP-0766 PC-0006 PC-0027 PC-0040 PC-0107 PC-0108 PC-0148 PC-0151 RD-0017 RD-0165 RD-0181 RD-0229
GP-0616 GP-0775 GP-1223 GP-1276 RD-0053 PC-0150 RD-0112 RD-0251 PC-0125""".split()
ER_INTENT = "GP-0081 GP-0085 GP-0550 GP-0564 GP-0609 GP-0640 GP-0830 GP-0939 GP-1327".split()
ENR = "CC-0064 GP-0370 GP-0435 GP-0452 GP-0621 GP-1245 GP-1319 PC-0019 PC-0046 PC-0053 PC-0071 PC-0116 PC-0122 PC-0123 PC-0124 PC-0161 PC-0113 PC-0126 RD-0125".split()
# reviewers who say they had been repeat customers before leaving / or who are loyal but unhappy
ENR_PRIOR_REPEAT = set("CC-0064 GP-0435 PC-0122 PC-0123 PC-0124 PC-0113 RD-0125 PC-0046".split())

WARN = re.compile(r"(?:don[’']?t|do not|never|stay away|avoid|beware|not to|would not recommend|do not recommend|don[’']?t recommend|not recommend|think twice|be aware|careful)\b.{0,30}(?:use|book|buy|go|trust|waste|rely|call|take|purchase|recommend|before|ever)|avoid (?:at all|like)|stay away|think twice|beware|please be aware|never use|never ever", re.I)
SWITCH = re.compile(r"alternative|look(?:ing)? for (?:other|another|someone|a better)|look elsewhere|seek services elsewhere|will stop booking|forced to seek|(?:go|going|went) (?:for|with|to) (?:a )?(?:local|other|another)|local (?:provider|technician|mechanic|market|guy|vendor|expert)|other apps?|snabbit|pronto|yes ?madam|nobroker|housejoy|better than (?:uc|urban)|instead of (?:uc|urban|booking)|(?:not|never) (?:going|go) to (?:use|book)|rather (?:use|go|call|hire)|shift(?:ing)? back", re.I)
TRUST_POS = re.compile(r"recommend|trust(?:ed|worthy)?|reliable|go[- ]?to|loyal|worth|satisf|happy with|impress|appreciat|keep (?:it )?up|thank|best|excellent|great|amazing|good", re.I)
DISTRUST = re.compile(r"don[’']?t trust|not trust|no trust|distrust|scam|fraud|cheat|dishonest|liar|loot|fake|robb|mislead|theft|stole|stolen|abus|harass", re.I)


def classify_return(rid, text, sentiment):
    if rid in ENR:
        return "Explicit Non-Return", ("previously a repeat customer" if rid in ENR_PRIOR_REPEAT else "states will not return / has switched / uninstalled")
    if rid in ER_REPORTED:
        return "Explicit Return", "reports repeat or ongoing use"
    if rid in ER_INTENT:
        return "Explicit Return", "states intent to book again / prefers same professional"
    wc = len(re.findall(r"\w+", text))
    if WARN.search(text): return "Behavioural Signal", "warns others / advises against using"
    if SWITCH.search(text): return "Behavioural Signal", "switching intent or comparison with alternatives"
    if wc >= 8 and DISTRUST.search(text): return "Behavioural Signal", "distrust / safety or honesty concern"
    if wc >= 8 and sentiment == "Positive" and TRUST_POS.search(text): return "Behavioural Signal", "satisfaction / trust / recommendation (no repeat stated)"
    if wc >= 8 and sentiment in ("Negative", "Mixed"): return "Behavioural Signal", "dissatisfaction (no non-return or switching stated)"
    return "Insufficient Evidence", "no repeat or non-return information"


# ---- round 2 (new Play Store positive reviews, each read by hand): first-person repeat use / intent to book again -------------------
ER_REPORTED.extend(f"GP-{n}" for n in "1729 1742 1745 1784 1794 1862 1907 1975 1980 1988 2021 2033 2038 2052 2060 2065 2079 2114 2128 2139 1932 1828 2037 1844".split())
ER_INTENT.extend(f"GP-{n}" for n in "1746 1753 1837 1874 1827 2012 1774 1668 1853 1895 1910 1921 2049 2072 2140".split())
