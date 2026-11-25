"""Quote specs (record_id, regex) for triggers, household types, discovery channels and alternatives. Apostrophes are matched with '.' so
curly/straight quotes both work. All IDs were read individually."""

TRIGGER_Q = {
    "Appliance or equipment stops working": [("RD-0074", r"My dad.s AC was not working properly"), ("CC-0073", r"the tv which i have is not working"), ("PC-0152", r"My TV is not working on Sunday"), ("RD-0144", r"my AC stopped cooling properly")],
    "Moving house, new home, tenancy change, renovation": [("RD-0064", r"moving into a new"), ("RD-0139", r"giving out my flat on rent soon"), ("RD-0181", r"recently shifted from Indore to Bhopal"), ("RD-0255", r"panelling for my new home")],
    "Festival, wedding or personal event": [("RD-0129", r"deep cleaned for Diwali"), ("RD-0214", r"cleaned before Diwali"), ("RD-0002", r"getting married in few weeks"), ("RD-0174", r"major life event coming up")],
    "Health, age or family circumstance": [("RD-0074", r"since he is bed ridden"), ("PC-0043", r"4-month-old baby"), ("RD-0227", r"my father who is about 70")],
    "Pests, smell or hygiene problem": [("RD-0145", r"Urgent Pest Control Needed"), ("RD-0223", r"small cockroaches"), ("RD-0027", r"termite control done")],
    "Leakage, seepage, drainage or water-quality problem": [("RD-0108", r"flush water in the washroom takes time to drain"), ("RD-0148", r"paint peeling off and seepage"), ("RD-0026", r"foul smelling water supply")],
    "Season or weather (heat, rain)": [("RD-0074", r"given the hot weather"), ("RD-0148", r"because of the rains"), ("CC-0039", r"before using it in summer")],
    "Urgent or same-day need": [("RD-0094", r"because of Holi"), ("RD-0185", r"wrap it all up tomorrow"), ("RD-0165", r"when I need someone urgently")],
    "Working schedule, no time to do it themselves": [("PC-0110", r"we are working people"), ("RD-0147", r"As a working professional"), ("GP-0177", r"jobs done around the house quickly during downtime")],
    "Planned, periodic or subscription use": [("GP-1560", r"bathroom cleaning plan for 16 weeks"), ("PC-0134", r"periodical service"), ("RD-0229", r"since April 2024 for AC servicing")],
    "Considering a Native product purchase": [("RD-0026", r"thinking about getting a water purifier"), ("RD-0140", r"thinking of buying the Urban Company"), ("RD-0201", r"Decided on Urban Company")],
}
HOUSEHOLD_Q = {
    "Lives alone": [("RD-0054", r"23 yo female living alone"), ("RD-0116", r"living alone in a 1bhk"), ("RD-0126", r"I live alone and home gets"), ("RD-0174", r"safe for someone living alone")],
    "Elderly, bedridden or senior family member": [("RD-0074", r"since he is bed ridden"), ("RD-0179", r"They both are senior citizens"), ("RD-0227", r"my father who is about 70"), ("RD-0252", r"harassed my parents who are old")],
    "Young children or a baby": [("PC-0043", r"4-month-old baby"), ("PC-0087", r"my daughter.s 7 B.day"), ("RD-0145", r"safe for kids/pets")],
    "Pet owners": [("GP-1373", r"As a pet owner"), ("RD-0229", r"I have 2 dogs"), ("PC-0158", r"I have PETS in the house")],
    "Working professionals / time-poor households": [("GP-0177", r"young office goers"), ("PC-0110", r"we are working people"), ("RD-0123", r"tech professional"), ("RD-0147", r"As a working professional")],
    "Renters, tenants and landlords": [("CC-0039", r"rented apartment"), ("RD-0112", r"I live in a rented accommodation"), ("RD-0139", r"giving out my flat on rent"), ("PC-0086", r"landlord.s decision")],
    "Newcomers or recently relocated": [("GP-1291", r"Moving to a new city can be difficult"), ("RD-0064", r"moving into a new"), ("RD-0181", r"recently shifted from Indore to Bhopal"), ("PC-0113", r"recently shifted home in August")],
    "Booking from abroad / for family elsewhere": [("PC-0131", r"I reside in the UK"), ("PC-0161", r"I am in the UK now"), ("GP-0234", r"booking for my mother"), ("GP-1476", r"I need to book for my mother")],
    "Women's safety or female-professional preference": [("RD-0051", r"no, none, AC women technicians"), ("RD-0054", r"as a 23 yo female living alone i was scared"), ("PC-0104", r"extremely unsafe for women")],
    "Single-bathroom / small-home package mismatch": [("GP-0636", r"no option for 1 bathroom cleaning"), ("GP-0727", r"no option for single bathroom cleaning"), ("GP-0431", r"1 bathroom is not available")],
}
DISCOVERY_Q = {
    "Referral from friends, family or colleagues": [("GP-1341", r"came to know from my friend"), ("PC-0171", r"friends and collegues suggested your app"), ("RD-0120", r"A friend told me to check out Urban Company"), ("RD-0092", r"my mom suggested")],
    "Advertising, YouTube or social media": [("RD-0173", r"youtubers praising"), ("RD-0201", r"great marketing"), ("GP-1644", r"your ads promise a class service"), ("RD-0053", r"came across \[?this video")],
    "Online research: Reddit, Google, reviews": [("RD-0086", r"saw on reddit about how it.s scamming people"), ("RD-0117", r"negative reviews on reddit"), ("RD-0209", r"everyone is recommending the UC M1/2 model"), ("RD-0011", r"reviews on Reddit")],
    "Marketplace purchase of a Native product (Amazon / Flipkart)": [("CC-0016", r"via Amazon on 18 May 2026"), ("CC-0053", r"from Flipkart"), ("RD-0161", r"from amazon on 14th july"), ("GP-0296", r"from Flipkart")],
    "Offers, discounts or membership": [("GP-0766", r"attractive offers and discounts mainly to new users"), ("RD-0221", r"rate difference for old and new customers"), ("GP-1650", r"even with plus membership")],
    "On-ground promoter in a society": [("GP-1362", r"rep came in society for offer")],
}
# alternatives: tier = what the reviewer actually says. reported_use = says they used/hired/switched/ compared from experience;
# considering = actively deciding; general = advice to others, hypothetical, or a generic comparison claim.
ALT_TIER = {
    "reported_use": "GP-1116 GP-0842 GP-0477 GP-1366 GP-0370 PC-0054 RD-0184 RD-0130 GP-0342 GP-1529 GP-0426 GP-1111 GP-1151 RD-0035 RD-0171 RD-0169 RD-0125 RD-0228 RD-0181 RD-0144 RD-0053 CC-0145 GP-1488 RD-0204 RD-0107 RD-0115".split(),
    "considering": "RD-0044 RD-0158 RD-0235 RD-0237 RD-0123 RD-0148 RD-0096 RD-0152 RD-0105 RD-0014 RD-0025 RD-0080 RD-0241 RD-0236 RD-0045 RD-0064 RD-0139 RD-0142 RD-0143 RD-0146 RD-0147 RD-0166 RD-0124 RD-0238 RD-0205 RD-0188 RD-0006".split(),
    "general": "GP-0340 GP-0341 GP-0374 GP-0396 GP-0473 GP-0793 GP-0643 GP-0911 GP-1002 GP-0781 GP-0944 GP-1126 GP-1423 GP-1428 GP-1605 PC-0026 PC-0126 PC-0156 PC-0173 GP-1436 RD-0121 GP-0241 PC-0076".split(),
}
ALT_GROUP = {   # record -> alternative group (one primary group per vetted record)
    "Competing platforms (Snabbit, Pronto, Yes Madam, NoBroker, Housejoy, Justdial and similar)": "GP-1116 GP-0842 GP-0477 GP-1366 GP-0370 PC-0054 RD-0184 RD-0130 GP-0643 GP-0911 GP-1002 GP-0781 GP-0944 GP-1436 RD-0014 RD-0025 RD-0080 RD-0241 RD-0236 RD-0045 RD-0064 RD-0105 RD-0139 RD-0142 RD-0143 RD-0146 RD-0147 RD-0148 RD-0166 RD-0124 RD-0238 RD-0121 RD-0096".split(),
    "Local / independent professionals and shops": "GP-0342 GP-1529 GP-0426 GP-1111 GP-1151 RD-0035 RD-0171 RD-0169 RD-0125 RD-0228 RD-0181 RD-0144 RD-0053 RD-0107 RD-0115 RD-0044 RD-0158 RD-0235 RD-0237 RD-0123 RD-0152 GP-0340 GP-0341 GP-0374 GP-0396 GP-0473 GP-0793 GP-1126 GP-1423 GP-1428 GP-1605 PC-0026 PC-0126 PC-0156 PC-0173".split(),
    "Brand service centres and brand technicians": "GP-1488 RD-0204 RD-0205 RD-0188 RD-0006 GP-0241 PC-0076".split(),
    "Friends, neighbours and family": "CC-0145".split(),
}
ALT_Q = {
    "Competing platforms (Snabbit, Pronto, Yes Madam, NoBroker, Housejoy, Justdial and similar)": [("GP-0477", r"Snabbit provides much better service"), ("GP-1116", r"after continuously failing bookins from snabit"), ("GP-1366", r"a little bit more than pronto"), ("GP-0370", r"Shifting to NoBroker"), ("RD-0184", r"Booked NoBroker service"), ("RD-0130", r"might not be as professional as urban company")],
    "Local / independent professionals and shops": [("GP-0340", r"4X than the local service provider"), ("GP-0342", r"a local repairer did it for 1500"), ("RD-0035", r"Spent 300 and got it fixed from a local technician"), ("RD-0169", r"Local technicians refill gas in Rs. 2,200"), ("PC-0156", r"local vendors are more effective"), ("RD-0123", r"it feels super risky"), ("RD-0228", r"they even damaged it further"), ("RD-0125", r"I hired guys from society")],
    "Brand service centres and brand technicians": [("GP-1488", r"now having to call LG"), ("GP-0241", r"Samsung charges 350"), ("RD-0204", r"service center wale to ine se bhi jyada corrupt")],
    "Friends, neighbours and family": [("CC-0145", r"my neighbor call hitachi guy"), ("PC-0171", r"friends and collegues suggested your app"), ("RD-0107", r"friend-recommended painter")],
}
