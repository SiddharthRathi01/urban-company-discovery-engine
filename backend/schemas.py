"""Structured-output contracts. Every LLM response is validated against these models; invalid output is retried, then logged as a failure -
it is never repaired by inventing values."""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

ReturnClass = Literal["Explicit Return", "Explicit Non-Return", "Behavioural Signal", "Insufficient Evidence"]
ReturnBasis = Literal["reported_repeat_use", "stated_intent_to_return", "stated_will_not_return", "switched_or_stopped",
                      "advice_to_others", "switching_intent", "trust_or_satisfaction", "dissatisfaction", "none"]
AltType = Literal["competing_platform", "local_independent", "brand_service_centre", "friends_family_neighbours",
                  "community_group_or_whatsapp", "directory_or_search", "other"]
Channel = Literal["friend_family_referral", "advertising_social_youtube", "online_research_reviews", "marketplace_purchase",
                  "offer_or_membership", "on_ground_promoter", "other"]
Urgency = Literal["urgent", "planned", "unclear"]


class Alt(BaseModel):
    name: str
    type: AltType
    relation: Literal["uses", "used_before", "considering", "recommends_against", "compares", "other"] = "other"
    reason: Optional[str] = None
    quote: Optional[str] = None


class ReviewExtraction(BaseModel):
    review_id: str
    is_customer_experience: bool
    problem_phrase: Optional[str] = None       # <= 12 words, the customer's main problem in plain words
    positive_phrase: Optional[str] = None      # <= 12 words, what the customer valued
    expectation_summary: Optional[str] = None  # what the customer expected after booking, if stated
    expectation_quote: Optional[str] = None
    return_class: ReturnClass
    return_basis: ReturnBasis
    return_quote: Optional[str] = None         # verbatim; REQUIRED for the two Explicit classes (enforced in code)
    booking_trigger: Optional[str] = None
    trigger_quote: Optional[str] = None
    urgency: Urgency = "unclear"
    household_cue: Optional[str] = None
    household_quote: Optional[str] = None
    discovery_channel: Optional[Channel] = None
    discovery_quote: Optional[str] = None
    alternatives: List[Alt] = Field(default_factory=list)
    unmet_need: Optional[str] = None           # <= 12 words
    unmet_need_quote: Optional[str] = None
    key_quote: Optional[str] = None            # most informative verbatim sentence (<= 220 chars)


class ExtractionBatch(BaseModel):
    results: List[ReviewExtraction]


# ---- clustering / themes
class ClusterAssign(BaseModel):
    label: str
    definition: str
    ids: List[str]


class ClusterChunk(BaseModel):
    clusters: List[ClusterAssign]


class MergedType(BaseModel):
    name: str
    definition: str
    merged_from: List[str]


class MergeResult(BaseModel):
    types: List[MergedType]


class ThemeDef(BaseModel):
    theme_id: str
    name: str
    description: str
    issue_types: List[str]


class ThemeResult(BaseModel):
    themes: List[ThemeDef] = Field(max_length=5)


class ThemeNarrative(BaseModel):
    theme_id: str
    description: str
    main_customer_problems: List[str]
    representative_review_ids: List[str]


class ThemeNarrativeResult(BaseModel):
    narratives: List[ThemeNarrative]


# ---- cited answers
class Cite(BaseModel):
    review_id: str
    quote: str


class Finding(BaseModel):
    finding: str
    supporting: List[Cite]


class QuestionAnswer(BaseModel):
    question_id: str
    summary: str
    findings: List[Finding]
    evidence_strength: Literal["strong", "moderate", "weak", "insufficient"]
    evidence_gaps: List[str]


class AlternativeInsight(BaseModel):
    name: str
    type: AltType
    used_for: str
    why_customers_prefer_it: List[str]
    advantages: List[str]
    disadvantages: List[str]
    service_categories: List[str]
    supporting: List[Cite]


class AlternativesAnswer(BaseModel):
    alternatives: List[AlternativeInsight]
    summary: str


class Opportunity(BaseModel):
    name: str
    customer_problem: str
    supporting_segment: Optional[str] = None
    why_it_matters_to_customers: str
    repeat_booking_link_hypothesis: str   # explicitly a hypothesis
    suggested_improvement_hypothesis: str  # explicitly a hypothesis
    impact_score_1_to_5: int = Field(ge=1, le=5)
    related_clusters: List[str]
    supporting: List[Cite]


class OpportunityResult(BaseModel):
    opportunities: List[Opportunity]
