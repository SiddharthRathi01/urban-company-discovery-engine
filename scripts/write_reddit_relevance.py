"""Record the Reddit relevance decisions made by reading every collected post (title + body).
Anything not listed here was read and judged relevant (a customer/prospective customer discussing using, considering, comparing or complaining about Urban Company)."""
import json

groups = {
    "Spam: repeated 'how do I complain to UrbanClap' posts carrying phone numbers": "1tyhm50 1s5yhha 1s5ygz8 1rl5671 1qg54kh 1nbc9bo 1ji067e 1ji04r9".split(),
    "Solicitation (survey / research / recruiting), not a customer experience": "1b0e3af 1b0e2kz 1b0e15c 1b0e0l4 1b0e6ap 1m8uyv6 1y2ll90 1t7ida5 1rp2df7 1m8u8b0 1jftrph 1rkj58h".split(),
    "No content / cannot tell whether the author is a customer": "1rzkmck 14s615v 1v1eek6 1kz2mbt 1ht8ogx 12q9pyu m4mrvs 1twk7u8 1tacqs1 1tacjv5 1ozbvmq".split(),
    "News / marketing / business commentary, not a customer experience": "78fqno 6m5cjk 4ioh87 3w9pgw 2obnar 5dx1j5 1bqv7jl 1g6g89i 1kaukdd 1nmvmkn".split(),
    "Partner / employee / job-seeker post (not a customer)": ("7obb9l 1rsx5jz 1rs2jc7 1rsfomp 1y2r4kg 1gzeokd 1eiy3iv 1s0n1w6 1jcx3a3 1g8yfn6 1dvaw9o 1dslvct 1dsluvs 1xdlfbi 1xcaa83 "
                                                  "1rsfo02 yvppic 1wy4sg3 1woe1zm 1woe2pi 1wcouh3 1v5h9ab 1udo2lv 1u4nvb9 1rv15o8 1rp4jy0 1ncbv6c 1n0s6ia 1l0qamp 1kcaa3j 1jz3gkk 1itu3p1 198jo47 1tgkk58").split(),
    "Startup / product promotion": "e600vy 6dzd4m 1v7bx82".split(),
    "Incidental mention: post is not about using or considering Urban Company": ("enscm6 bselhx 5ouy3r 1ps5yvx 1pdphr1 1kf92aw 1kf91f2 okan4e 1p94i38 1nmkuah 1i49smd 1xjjydx 1xjjups 1vpyp55 1j7b4c2 1o9wsl6 rguww0 1meyq3m 1lvba9y "
                                                                                   "1slki0m 1rnuck7 1p3ou50 1kee2bv 1jjpw28 16wwisd").split(),
    "Cross-post: title-only duplicate of another post by the same author (kept once)": "1mzr3fe 1vak319 1fu6ka5 1roeach 1u87kof 1pjuhcd 1pjuje8 15b5tqk".split(),
}
out = {}
for reason, ids in groups.items():
    for i in ids: out[i] = ("Reddit relevance", reason)
json.dump(out, open("raw/reddit_relevance.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "Reddit posts excluded by the relevance read")
