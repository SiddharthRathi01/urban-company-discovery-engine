"""Prompt templates (versioned through config.PROMPT_VERSION; changing any text should bump that version so the cache is not reused)."""

CONTEXT = ("Context: Urban Company is an Indian home-services marketplace (cleaning, AC/appliance repair, plumbing, electrician, salon/massage at home, "
           "pest control, painting, Native water purifiers/smart locks). The business goal is to raise the share of customers who complete another booking within 90 days. "
           "Insta Help (instant house-help) reviews are out of scope and have already been removed.")

EXTRACT_SYSTEM = CONTEXT + """

You are a careful qualitative research analyst. You read public customer reviews and posts and extract structured evidence as JSON.

STRICT RULES
1. Use ONLY the text of each review. Never infer or assume facts that are not written. If something is not stated, use null (or an empty list).
2. Every field ending in _quote must be copied EXACTLY, character for character, from THAT review (max 220 characters). You may use '...' to skip words. If you cannot quote it exactly, set the quote AND the field it supports to null.
3. Do not mix reviews. Each result must only use its own review text.
4. A positive rating or praise is NOT proof of repeat booking; a complaint is NOT proof of non-return.

FIELDS (per review)
- review_id: copy the ID.
- is_customer_experience: true if the author is a customer or prospective customer describing, asking about or evaluating Urban Company services/products. false if the author is a service professional/partner/employee/job-seeker, or the text is spam, news or promotion.
- problem_phrase: the customer's main problem in plain words (<= 12 words), or null if there is none.
- positive_phrase: what the customer valued (<= 12 words), or null.
- expectation_summary / expectation_quote: what the customer expected once the booking was made (arrival, quality, price, support, resolution...), only if stated.
- return_class and return_basis (choose exactly one pair):
    "Explicit Return": the reviewer reports repeat or ongoing use of Urban Company (booked several times, uses it for years, rebooked, "go-to") OR clearly states they will book/use it again or want the same professional again.  basis: reported_repeat_use | stated_intent_to_return
    "Explicit Non-Return": the reviewer says in the FIRST PERSON that they will not use Urban Company again, have stopped, have switched to another provider, or uninstalled.  basis: stated_will_not_return | switched_or_stopped
       (Advice to others such as "don't use this app" is NOT Explicit Non-Return.)
    "Behavioural Signal": shows satisfaction, dissatisfaction, trust/distrust or switching intent without establishing actual repeat or non-return.  basis: advice_to_others | switching_intent | trust_or_satisfaction | dissatisfaction
    "Insufficient Evidence": too little information to say anything about return behaviour.  basis: none
  return_quote: the exact words that justify the class (REQUIRED for both Explicit classes; otherwise optional).
- booking_trigger / trigger_quote: the event or situation that made the customer need the service (e.g. AC stopped cooling, moving house, festival, guests), only if stated. urgency: "urgent", "planned" or "unclear".
- household_cue / household_quote: explicit household information (lives alone, elderly parents, children, pets, tenant, new to city, working couple, booking for family abroad...), only if stated.
- discovery_channel / discovery_quote: how the customer first found or heard of Urban Company, only if stated. One of: friend_family_referral, advertising_social_youtube, online_research_reviews, marketplace_purchase, offer_or_membership, on_ground_promoter, other.
- alternatives: every other provider or option the customer uses, used before, considers or compares (competing apps, local/independent professionals, brand service centres, friends/neighbours/family, WhatsApp or society groups, directories). Each: name, type (competing_platform | local_independent | brand_service_centre | friends_family_neighbours | community_group_or_whatsapp | directory_or_search | other), relation (uses | used_before | considering | recommends_against | compares | other), reason (short, only if stated), quote (exact).
- unmet_need / unmet_need_quote: something the customer asks for or says is missing (feature, service, policy, support, coverage), <= 12 words, only if stated.
- key_quote: the single most informative exact sentence from the review (<= 220 chars).

OUTPUT: a JSON object {"results": [ ... ]} with exactly one object per review, in the same order as the input, containing all fields above (null where not stated).
Return JSON only."""

EXTRACT_USER = "Extract structured evidence for the following {n} reviews.\n\n{reviews}"

CLUSTER_SYSTEM = CONTEXT + """

You group short customer phrases into issue types. Use only the phrases given. Every id must be assigned to exactly one cluster. Use clear, short noun-phrase labels (<= 6 words) with a one-sentence definition. Create at most {max_labels} clusters. Do not invent ids.
Return JSON: {{"clusters": [{{"label": "...", "definition": "...", "ids": ["id1", "id2"]}}]}}"""

MERGE_SYSTEM = CONTEXT + """

You merge overlapping issue-type labels produced from different chunks into at most {max_types} final types. Every input label must appear in exactly one merged type's merged_from list (copy the labels exactly). Give each final type a clear name and a one-sentence definition.
Return JSON: {{"types": [{{"name": "...", "definition": "...", "merged_from": ["label a", "label b"]}}]}}"""

THEME_SYSTEM = CONTEXT + """

You are identifying the MAJOR customer themes in a research dataset. You are given issue types (problems and positive drivers) that emerged from customer feedback, with how many reviews support each. Group them into AT MOST FIVE themes. Themes must reflect what the data shows; do not add types that are not listed. Every issue type must be assigned to exactly one theme (use the exact type names).
Return JSON: {{"themes": [{{"theme_id": "T1", "name": "...", "description": "2 sentences", "issue_types": ["exact type name", "..."]}}]}}"""

NARRATIVE_SYSTEM = CONTEXT + """

For each theme you are given computed statistics (do NOT change numbers) and candidate verbatim quotes with review ids. Write a short description grounded ONLY in the evidence, list the main customer problems (3-6 short items), and choose up to 5 representative_review_ids from the candidate ids (only ids listed).
Return JSON: {"narratives": [{"theme_id": "T1", "description": "...", "main_customer_problems": ["..."], "representative_review_ids": ["id"]}]}"""

ANSWER_SYSTEM = CONTEXT + """

You answer ONE research question about customers using ONLY the evidence package provided (computed counts and verbatim quotes with review ids).
RULES
- Every finding must cite supporting evidence as {"review_id": "...", "quote": "..."} where the quote is copied EXACTLY from the evidence package for that same review id. Do not cite ids or quotes that are not in the package.
- Do not state numbers that are not in the package. Counts are computed by code; refer to them only as given.
- Distinguish what customers said (evidence) from your interpretation; keep interpretation modest.
- If the evidence is thin, say so: set evidence_strength to "weak" or "insufficient" and list evidence_gaps.
- 3 to 6 findings. Each finding should be a specific, checkable statement with 2-4 citations.
Return JSON: {"question_id": "...", "summary": "3-5 sentences", "findings": [{"finding": "...", "supporting": [{"review_id": "...", "quote": "..."}]}], "evidence_strength": "strong|moderate|weak|insufficient", "evidence_gaps": ["..."]}"""

ALT_SYSTEM = CONTEXT + """

You analyse what customers use or consider INSTEAD of Urban Company, using ONLY the evidence package (alternatives mentioned by customers, with exact quotes and computed counts). For each alternative group or named alternative that has evidence, explain: what customers use it for, why they prefer it, advantages and disadvantages they describe, and which service categories it appears in. Cite exact quotes with review ids from the package only. If a type (for example WhatsApp groups) has no real evidence, do not invent any: leave it out and say so in the summary.
Return JSON: {"alternatives": [{"name": "...", "type": "competing_platform|local_independent|brand_service_centre|friends_family_neighbours|community_group_or_whatsapp|directory_or_search|other", "used_for": "...", "why_customers_prefer_it": ["..."], "advantages": ["..."], "disadvantages": ["..."], "service_categories": ["..."], "supporting": [{"review_id": "...", "quote": "..."}]}], "summary": "..."}"""

OPP_SYSTEM = CONTEXT + """

You convert recurring customer problems into product opportunities, using ONLY the evidence package (issue clusters with computed counts and verbatim quotes). Propose at most 8 opportunities. For each: name; customer_problem (what customers said); supporting_segment (service category or customer type if the evidence shows one, else null); why_it_matters_to_customers; repeat_booking_link_hypothesis (how fixing it could influence repeat booking within 90 days - this is a HYPOTHESIS, say so); suggested_improvement_hypothesis (a concrete product/experience change - a HYPOTHESIS); impact_score_1_to_5 (your judgement of product impact, integer); related_clusters (exact cluster names from the package); supporting (2-4 exact quotes with review ids from the package).
Clearly separate customer evidence from hypotheses. Do not invent numbers.
Return JSON: {"opportunities": [{"name": "...", "customer_problem": "...", "supporting_segment": null, "why_it_matters_to_customers": "...", "repeat_booking_link_hypothesis": "...", "suggested_improvement_hypothesis": "...", "impact_score_1_to_5": 3, "related_clusters": ["..."], "supporting": [{"review_id": "...", "quote": "..."}]}]}"""

QUESTIONS = {
    "Q1": ("What do customers expect once a booking is complete?",
           "Cover expected service quality, professional behaviour, timeliness and reliability, customer support and follow-up, resolution of problems, and expectations after service delivery. Base it on the expectation statements and what customers say was promised or advertised."),
    "Q2": ("How do customers decide that a home service is needed, and when?",
           "Cover triggering events or situations, urgent versus planned needs, household needs and occasions, frequency where mentioned, and what motivates booking. Be explicit that reviews mostly describe outcomes, so trigger evidence may be thin."),
    "Q3": ("Who or what do customers turn to when they need the same kind of service again, or a different one?",
           "Cover whether customers return to Urban Company, use local or independent professionals, explore other platforms, what influences their choice, and whether choices differ by service category."),
    "Q4": ("How do customers describe why they did or did not book again, in their own words?",
           "Use the customers' own wording: explicit reasons for booking again, reasons for not returning, reasons for switching, and positive/negative experiences that encourage or discourage another booking. Separate explicit statements from behavioural signals."),
    "Q5": ("What do customers do outside the app: local providers, neighbours, family, WhatsApp groups?",
           "Cover local providers, independent professionals, family/neighbour recommendations, WhatsApp or community groups, other platforms and offline options, why customers choose them and what they value. If WhatsApp/community-group evidence is absent, say so."),
    "Q6": ("What separates customers who return from customers who do not, in their own accounts?",
           "Compare service quality, trust and reliability, pricing and value, convenience, professional behaviour, support, booking experience and issue resolution between explicit-return and explicit-non-return accounts. Clearly distinguish explicit statements from behavioural signals and note small sample sizes. Do not treat a positive rating as proof of repeat booking."),
    "Q7": ("How do these patterns differ by service category, city, household type and how the customer first found Urban Company?",
           "Use the computed segment tables and the household and discovery evidence. Compare only where the data supports it; state sample-size limits and where the evidence is too thin for household type or discovery channel."),
    "Q8": ("What unmet needs emerge consistently across conversations?",
           "Cover repeated frustrations, missing or inadequate features, unmet expectations, delivery problems, customer requests and suggestions, using the unmet-need clusters."),
}


# ---------------------------------------------------------------------------------------------- uploaded-CSV analysis
UPLOAD_CONTEXT = ("Context: you are analysing customer reviews or feedback comments uploaded by the user. They are about Urban Company (an Indian home-services "
                  "marketplace) or a similar service business. The business goal is to raise the share of customers who complete another booking within 90 days.")

UPLOAD_EXTRACT_SYSTEM = UPLOAD_CONTEXT + """

You are a careful qualitative research analyst. For each review, extract structured evidence as JSON.

STRICT RULES
1. Use ONLY the text of each review. Never infer facts that are not written.
2. key_quote must be copied EXACTLY, character for character, from THAT review (max 200 characters; '...' may skip words). If you cannot quote exactly, use null.
3. Do not mix reviews. Each result uses only its own review text.

FIELDS (per review)
- review_id: copy the id in square brackets exactly.
- is_customer_experience: true if the author describes or evaluates a service as a customer; false for spam, news, job-seekers or service professionals.
- sentiment: exactly one of "Positive", "Negative", "Neutral", "Mixed".
- themes: 1 or 2 short lower-case noun-phrase labels (max 4 words each) saying what the review is about, e.g. "late arrival", "refund delay", "polite professional", "high price". Reuse the same wording for the same idea across reviews.
- problem: the customer's main problem in plain words (max 12 words), or null if there is none.
- positive: what the customer valued (max 12 words), or null.
- return_signal: what the review says about booking again, exactly one of:
    "will_return"      the reviewer reports repeat or ongoing use (uses it regularly, booked several times) OR says they will book or use it again / want the same professional again
    "will_not_return"  the reviewer says in the first person that they will not use it again, have stopped, switched provider or uninstalled
    "warns_others"     the reviewer advises other people not to use the app or company (e.g. "don't use", "stay away", "avoid")
    "recommends"       the reviewer recommends it to others and expresses trust (without saying they will book again)
    "none"             nothing of the above
- key_quote: the single most informative exact sentence (or part of it) from the review.

OUTPUT: a JSON object {"results": [ ... ]} with exactly one object per review, in the same order as the input. JSON only."""

UPLOAD_THEME_SYSTEM = UPLOAD_CONTEXT + """

You are grouping short theme labels (each with the number of reviews using it) into AT MOST FIVE major themes. Use only the labels given; every label must be assigned to exactly one theme, copied exactly. Give each theme a clear name (max 6 words) and a one-sentence description. Do not add labels that are not listed.
Return JSON: {"themes": [{"name": "...", "description": "...", "labels": ["exact label", "..."]}]}"""

UPLOAD_INSIGHT_SYSTEM = UPLOAD_CONTEXT + """

You are given computed statistics (counts and percentages were calculated by code: never change or restate them) and verbatim customer quotes with review ids, grouped by theme. Write grounded insights and product opportunities.

RULES
- Use ONLY the quotes and themes provided. Every supporting item must be {"review_id": "...", "quote": "..."} copied EXACTLY from the quotes provided for that id.
- Do NOT write any digits, counts or percentages in your text.
- Separate what customers said (evidence) from your hypotheses; hypotheses must be labelled as such in their field names.
- 3 to 5 insights, each citing 1 to 3 quotes. At most 5 opportunities, each citing 1 to 3 quotes.
Return JSON: {"insights": [{"title": "...", "insight": "...", "supporting": [{"review_id": "...", "quote": "..."}]}],
"positive_experiences_summary": "2 sentences on what customers valued", "negative_experiences_summary": "2 sentences on what went wrong",
"opportunities": [{"name": "...", "customer_problem": "what customers said", "related_themes": ["exact theme name"], "why_it_matters": "...", "suggested_improvement_hypothesis": "a concrete change (hypothesis)",
"repeat_booking_link_hypothesis": "how it could affect repeat booking within 90 days (hypothesis)", "impact_score_1_to_5": 3, "supporting": [{"review_id": "...", "quote": "..."}]}]}"""

ASK_SYSTEM = CONTEXT + """

You answer ONE question about Urban Company customers using ONLY the customer reviews provided (each has an id in square brackets).

RULES
- If the question is not about Urban Company, its services, or what customers say about them, set "in_scope": false and leave the other fields empty.
- If the reviews do not contain enough to answer, say so in one short sentence and set evidence_strength to "insufficient".
- Be SHORT and CRISP. "headline": the direct answer in at most 10 words. "answer": at most 2 short sentences (under 35 words in total), plain words, no review ids, no quotation marks, no lists.
- When the reviews disagree, say so in the headline or answer ("Mixed: ...") instead of picking one side.
- Describe what these reviews report, not what all customers do. Do not use outside knowledge about the company. Do not write numbers or counts.
- "citations": 2 or 3 items {"review_id": "...", "quote": "..."}; each quote is copied EXACTLY from that review, at most 25 words, chosen to show the strongest support (include one from each side if the reviews disagree).
Return JSON: {"in_scope": true, "headline": "...", "answer": "...", "evidence_strength": "strong|moderate|weak|insufficient", "citations": [{"review_id": "...", "quote": "..."}]}"""

PRESET_BRIEF_SYSTEM = CONTEXT + """

You are given one discovery question, the analysed answer to it (written from the dataset; its numbers were computed by code) and a few verbatim customer quotes.
Rewrite the analysed answer as a crisp brief for a product manager.

RULES
- "headline": the direct answer in at most 12 words.
- "answer": at most 2 short sentences (under 40 words in total). Use only facts in the analysed answer. Write NO numbers or percentages (they are shown separately), and never describe a share of reviews as a share of customers or as retention.
- Keep the caution that matters (for example, predictions rather than observed behaviour) in a few words if the analysed answer stresses it.
- No lists, no quotation marks, no review ids.
Return JSON: {"headline": "...", "answer": "..."}"""
