"""Hand-vetted evidence lists for Step 2 (record_id values in the final Master). Each list was built by reading the matched review text.
Counts from these lists are counts of VETTED EXAMPLES, not prevalence estimates."""

TRIGGERS = {
    "Appliance or equipment stops working": "CC-0064 CC-0073 CC-0163 CC-0142 PC-0050 PC-0152 PC-0127 PC-0158 RD-0074 RD-0112 RD-0144 RD-0042 RD-0207 RD-0094 RD-0050".split(),
    "Moving house, new home, tenancy change, renovation": "RD-0064 RD-0010 RD-0139 RD-0176 RD-0181 RD-0255 RD-0279 RD-0220 RD-0223 PC-0113 RD-0149 RD-0156 RD-0046 GP-1291".split(),
    "Festival, wedding or personal event": "RD-0129 RD-0214 RD-0002 RD-0094 PC-0041 PC-0087 GP-0181 RD-0174".split(),
    "Health, age or family circumstance": "RD-0074 PC-0043 PC-0107 RD-0227 RD-0179 RD-0095".split(),
    "Pests, smell or hygiene problem": "RD-0145 RD-0027 RD-0043 RD-0223 PC-0043 PC-0150".split(),
    "Leakage, seepage, drainage or water-quality problem": "RD-0108 RD-0148 RD-0047 RD-0026".split(),
    "Season or weather (heat, rain)": "RD-0074 RD-0229 RD-0148 RD-0026 CC-0039".split(),
    "Urgent or same-day need": "RD-0094 RD-0145 RD-0108 RD-0229 GP-0288 RD-0165 RD-0185 CC-0126".split(),
    "Working schedule, no time to do it themselves": "GP-0177 RD-0147 PC-0110 RD-0123".split(),
    "Planned, periodic or subscription use": "GP-1560 GP-1559 GP-1527 CC-0039 RD-0229 RD-0153 PC-0134 RD-0166".split(),
    "Considering a Native product purchase": "RD-0004 RD-0006 RD-0026 RD-0110 RD-0117 RD-0140 RD-0176 RD-0195 RD-0197 RD-0198 RD-0201 RD-0209 RD-0211 RD-0120".split(),
}
HOUSEHOLD = {
    "Lives alone": "RD-0054 RD-0116 RD-0126 RD-0174".split(),
    "Elderly, bedridden or senior family member": "RD-0074 RD-0179 RD-0227 RD-0252 RD-0164 PC-0107 PC-0150 GP-1471".split(),
    "Young children or a baby": "PC-0043 PC-0087 RD-0145".split(),
    "Pet owners": "GP-1373 RD-0229 PC-0158 RD-0145 RD-0164".split(),
    "Working professionals / time-poor households": "GP-0177 PC-0110 RD-0123 RD-0147".split(),
    "Renters, tenants and landlords": "CC-0039 RD-0112 RD-0166 RD-0139 RD-0223 RD-0125 PC-0086 RD-0010".split(),
    "Newcomers or recently relocated": "GP-1291 RD-0064 RD-0181 RD-0220 PC-0113 RD-0162".split(),
    "Booking from abroad / for family elsewhere": "PC-0131 PC-0161 GP-0234 GP-1476 RD-0215 GP-1356".split(),
    "Women's safety or female-professional preference": "RD-0051 RD-0054 RD-0091 PC-0104".split(),
    "Single-bathroom / small-home package mismatch": "GP-0636 GP-0727 GP-0840 GP-1467 GP-0431".split(),
}
DISCOVERY = {
    "Referral from friends, family or colleagues": "GP-1341 PC-0171 PC-0172 RD-0120 RD-0092".split(),
    "Advertising, YouTube or social media": "RD-0173 RD-0201 RD-0053 GP-1644 RD-0026".split(),
    "Online research: Reddit, Google, reviews": "RD-0086 RD-0117 RD-0209 RD-0211 RD-0011 RD-0195".split(),
    "Marketplace purchase of a Native product (Amazon / Flipkart)": "CC-0011 CC-0016 CC-0032 CC-0044 CC-0045 CC-0053 GP-0296 RD-0161 RD-0175 RD-0196".split(),
    "Offers, discounts or membership": "GP-0766 RD-0221 GP-1080 CC-0096 GP-1650 GP-1536".split(),
    "On-ground promoter in a society": "GP-1362".split(),
}
# alternatives: vetted records where the reviewer actually names the alternative as something they use, consider or compare
ALT_VETTED = {
    "Snabbit / Pronto (instant home-help apps)": "GP-0477 GP-0643 GP-0781 GP-0842 GP-0911 GP-0944 GP-1002 GP-1116 GP-1366".split(),
    "Yes Madam (salon / massage at home)": "GP-1436 RD-0014 RD-0025 RD-0080 RD-0130 RD-0236 RD-0241".split(),
    "NoBroker / Housejoy / Justdial / other platforms (consideration set)": "RD-0045 RD-0064 RD-0105 RD-0115 RD-0121 RD-0139 RD-0142 RD-0143 RD-0144 RD-0146 RD-0147 RD-0148 RD-0153 RD-0166 RD-0184 RD-0238 RD-0096 RD-0124 GP-0370 PC-0054".split(),
    "Local / independent professionals": "GP-0340 GP-0341 GP-0342 GP-0374 GP-0396 GP-0426 GP-0473 GP-0793 GP-1126 GP-1423 GP-1428 GP-1529 GP-1605 PC-0026 PC-0126 PC-0156 PC-0173 RD-0035 RD-0053 RD-0125 RD-0169 RD-0171 RD-0204 RD-0228 RD-0044 RD-0107 RD-0123 RD-0152 RD-0158 RD-0235 RD-0237".split(),
    "Brand service centres and brand technicians": "GP-0241 RD-0050 RD-0171 RD-0204 RD-0205 RD-0188 RD-0006 PC-0076".split(),
    "Friends, neighbours and family": "CC-0145 RD-0107 RD-0105 RD-0120 PC-0171 GP-1341".split(),
}

# quote specification: slot -> list of (record_id, code-or-regex). The text is extracted verbatim from the master at build time.
Q = {
 "T1": [("GP-1238", "cancelled"), ("CC-0106", "cancelled"), ("GP-0480", "no_show"), ("GP-0893", "slot_unavailable"), ("RD-0097", "slot_unavailable"), ("GP-0720", "late")],
 "T2": [("GP-1632", "price_high"), ("GP-1584", "fees_charges"), ("GP-0551", "fees_charges"), ("GP-1126", "overcharge_upsell"), ("GP-0766", "fees_charges")],
 "T3": [("GP-0541", "support_unreachable"), ("GP-0437", "unresolved"), ("PC-0092", "refund_payment"), ("GP-0621", "warranty_rework"), ("GP-0451", "native_after_sales"), ("CC-0024", "unresolved")],
 "T4neg": [("GP-0481", "damage_theft"), ("PC-0061", "damage_theft"), ("GP-0238", "conduct_safety"), ("RD-0112", "trust_fraud"), ("GP-0462", "trust_fraud"), ("GP-0517", "poor_quality")],
 "T4pos": [("GP-0273", "pos_quality_pro"), ("GP-0042", "pos_punctual"), ("GP-0993", "pos_punctual"), ("RD-0053", "pos_support_resolution"), ("GP-0567", "pos_convenience"), ("GP-1229", "pos_quality_pro")],
 "T5": [("GP-0556", "coverage_gap"), ("GP-1558", r"professionals were not available in my area"), ("GP-0394", r"No custom request section"), ("GP-0534", "app_friction"), ("RD-0189", "app_friction")],
 "Q1": [("GP-0477", r"Customers expect reliable service after making a booking"), ("GP-0245", r"2 way confirmation"), ("GP-1191", r"if cannot service dont promise the slots"),
        ("GP-0129", r"professionals arrived without the necessary deep-cleaning equipment"), ("PC-0100", r"Your App says 6 months warrantee"), ("PC-0072", r"I expect Urban Clap to take full responsibility"),
        ("GP-0403", r"One thing we expect from our cleaning experts is transparency and honesty"), ("PC-0155", r"if I had not agreed to share the OTP"), ("GP-1649", r"expected professionalism"),
        ("RD-0118", r"a huge gap between the polished promise and the chaotic execution"), ("GP-1235", r"exceeded my expectations"), ("GP-0226", r"gives the customer full support")],
 "Q4return": [("GP-1004", r"every time I need to use their service"), ("GP-1044", r"My go to app"), ("GP-0616", r"always my first option"), ("GP-0942", r"Since last 4 years"), ("GP-0609", r"Will definitely book again"),
              ("GP-0085", r"Will definitely call her again"), ("GP-0564", r"I would certainly prefer asking for Reshma again"), ("GP-0830", r"I would definitely prefer him for any future plumbing work"),
              ("GP-1309", r"I rebooked the service today"), ("RD-0053", r"I’ve been getting my ACs serviced from UC for the past 6–7 years")],
 "Q4nonreturn": [("CC-0064", r"I will no longer use Urban Company"), ("GP-0621", r"I'm never using UC ever again"), ("PC-0116", r"This is the last time I am taking service"), ("PC-0071", r"Will not book any service"),
                 ("PC-0161", r"I am not going to use UC never in my life"), ("GP-0435", r"I shifted to other apps"), ("GP-0370", r"Shifting to NoBroker"), ("GP-1319", r"Uninstalling"),
                 ("PC-0122", r"decide not to use URBAN COMPANY hereafter"), ("RD-0125", r"Having had two bad experiences I hired guys from society"), ("PC-0126", r"I am surely done with them")],
 "Q4atrisk": [("GP-0329", r"A loyal customer for 5–6 years, but my trust is now broken"), ("GP-1233", r"I have used Urban Company for nearly 10 years"), ("GP-0588", r"I have been a regular customer of UC"),
              ("GP-1276", r"I am using UC for more than 8\+years"), ("CC-0113", r"Im a loyal customer"), ("GP-1198", r"You are sure to lose out on loyal customers")],
 "Q5": [("GP-0340", r"4X than the local service provider"), ("GP-0473", r"visiting a local market and hiring a local technician"), ("GP-1126", r"local electrician charges 150"), ("GP-0396", r"Go for a local person"),
        ("PC-0156", r"local vendors are more effective"), ("RD-0171", r"he runs his own shop"), ("RD-0035", r"Spent 300 and got it fixed from a local technician"), ("RD-0169", r"Local technicians refill gas in Rs. 2,200"),
        ("RD-0123", r"it feels super risky"), ("RD-0228", r"they even damaged it further"), ("GP-1151", r"We used to be very orthodox to use local service providers"), ("CC-0145", r"my neighbor call hitachi guy")],
 "Q8": [("GP-1457", r"No way to speak to customer service"), ("GP-0231", r"Before booking, it should be much clearer what is actually included"), ("GP-0394", r"No custom request section"), ("GP-1323", r"can introduce home cleaning in smaller chunks"),
        ("GP-0048", r"Add a service for just floor cleaning"), ("GP-1130", r"The pay after service option should be there"), ("GP-0245", r"2 way confirmation"), ("GP-1310", r"Please add support for home organizing"),
        ("RD-0051", r"Why there are no, none, AC women technicians"), ("GP-1373", r"As a pet owner"), ("GP-1544", r"add blender or mixer grinder repair service"), ("RD-0059", r"per-fan or small job cleaning")],
}
