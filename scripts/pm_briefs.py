"""Product-manager briefs for the nine opportunities. Written as a PM would: problem, why it happens, what to build, why it should lift
90-day repeat booking, how we would know, what to watch out for, and a size-of-work judgement.

HONESTY RULES: customer evidence (counts, quotes) comes from the data. Everything in this file is a hypothesis or recommendation: root causes are
hypotheses to test, 'effort' is a PM judgement (S/M/L), and no number is stated here. Numbers are attached at build time from the dataset."""

PM = {
    "O1": {
        "problem": "A confirmed booking is cancelled, rescheduled, late or never attended, and the customer has already arranged their day around the slot. Recovery is manual: they rebook from scratch, sometimes after paying a fee.",
        "who": "Customers booking time-bound services (AC, cleaning, salon at home), especially first-time customers who have no history with the platform.",
        "why_it_happens": ["A booking is accepted before a professional has actually committed to the slot.", "Professionals can cancel late at little cost, and there is no live arrival status.", "When a provider cancels there is no automatic replacement; the customer has to start again."],
        "proposal": [
            {"title": "Confirm before you charge", "what": "Show the named professional and arrival window at confirmation; treat a booking as confirmed only when a professional has accepted."},
            {"title": "Two-way confirmation and live ETA", "what": "Professional confirms the morning of the job; the customer sees live status and gets a proactive alert on any delay (a customer asked for exactly this)."},
            {"title": "Automatic recovery", "what": "If a professional cancels or is late beyond a threshold, auto-offer the next available professional or a priority reschedule, plus a goodwill credit that applies to the next booking."},
            {"title": "No customer penalty for provider failure", "what": "Waive every fee when the cancellation is not the customer's; add reliability to professional scoring and assignment."}],
        "repeat_mechanism": "A failed first booking is the earliest and cheapest point to lose a customer. A fast, visible recovery turns a failure into a reason to trust the platform, which should raise the chance of a second booking (hypothesis: compare 90-day repeat for first bookings that were late or cancelled and recovered vs not recovered).",
        "success": "More bookings fulfilled on the first scheduled slot, faster replacement after a provider cancellation, and a smaller repeat-rate gap between customers whose first booking failed and those whose first booking went well.",
        "watch_out": "Professional supply and earnings: stricter cancellation rules can push professionals away; credits add cost.",
        "effort": "M", "effort_note": "Product plus operations; the confirm-first and ETA changes are the core build.",
    },
    "O2": {
        "problem": "When something goes wrong, customers cannot reach a person. The bot repeats itself, there is no phone number, tickets are closed without a reply, and nobody owns the problem, so customers chase for days.",
        "who": "Any customer after a failed or disputed booking; most acute for high-value services and Native purifier owners.",
        "why_it_happens": ["Support is designed bot-first to deflect volume, with no easy exit to a human.", "Tickets are closed by timers rather than by the customer confirming resolution.", "First-line agents lack authority to refund or arrange a redo, so cases bounce between teams."],
        "proposal": [
            {"title": "A person on request", "what": "After one bot exchange, or at once for a paid booking issue, offer a callback within a stated time. Show the phone or chat option in the booking screen."},
            {"title": "One case, one owner", "what": "A single case ID with a named owner, visible status and deadline in the app; a case closes only when the customer confirms or a clear resolution is recorded."},
            {"title": "Empowered first contact", "what": "Let first-line agents approve refunds, redos and goodwill credits up to a cap so most problems end in one contact."},
            {"title": "Reach out first", "what": "After a cancelled, late or very low-rated job, contact the customer proactively before they complain, and check back after resolution."}],
        "repeat_mechanism": "The experience of getting a problem fixed seems to decide whether customers stay, more than the original failure itself. Fast, human resolution should keep customers who would otherwise leave after a single failure (hypothesis: compare repeat rate of customers who complained and were resolved at first contact vs those who were not).",
        "success": "Customers reach a human quickly, most complaints end in one contact, few cases are reopened, and customers who complained rebook at a rate close to those who did not.",
        "watch_out": "Support cost per ticket rises; authority limits need fraud controls.",
        "effort": "L", "effort_note": "Operating-model change as much as product: staffing, tooling and agent authority.",
    },
    "O3": {
        "problem": "Money is deducted without a booking, refunds arrive late or partially, and customers who paid in advance feel they cannot get it back.",
        "who": "Customers who pay online, especially when a booking is cancelled by the company or a payment fails.",
        "why_it_happens": ["Payments and bookings are not reconciled in real time, so a paid-but-not-booked state can persist.", "Refunds follow bank timelines and manual approval rather than automatic rules.", "Customers cannot see where their refund is."],
        "proposal": [
            {"title": "Automatic refund to source", "what": "Refund automatically, with a visible tracker and expected date, whenever the company or professional cancels or a payment succeeds without a booking."},
            {"title": "Instant credit option", "what": "Offer an immediate in-app credit as an alternative to a 5-7 day bank refund, so the customer can rebook straight away."},
            {"title": "Reconcile within minutes", "what": "If money is taken and no booking exists, create the booking or reverse the charge automatically and tell the customer."},
            {"title": "Pay after service for small jobs", "what": "Test pay-after-service for low-value jobs, which several customers asked for."}],
        "repeat_mechanism": "A refund that takes weeks turns a one-off failure into a grievance about paying in the app at all. Instant, visible refunds should remove a common reason for not coming back (hypothesis).",
        "success": "Refunds reach the customer in hours instead of weeks, almost no case is stuck in 'paid but not booked', and customers who received a refund rebook at a normal rate.",
        "watch_out": "Instant credit can be abused; finance reconciliation effort rises.",
        "effort": "M", "effort_note": "Mostly payments and finance plumbing, clearly scoped.",
    },
    "O4": {
        "problem": "The price changes between the quote, the app and the bill. Fees stack up on small jobs, and on-site professionals quote parts or extra work at rates customers find far above local providers.",
        "who": "Repair and small-ticket customers (AC, appliance, plumbing, electrical) and cost-conscious households comparing with local providers.",
        "why_it_happens": ["Platform, visit, surge and tax charges are added late in the flow.", "Parts and extra work are priced on site at the professional's discretion, with no visible rate card.", "Customers cannot verify whether the extra work is needed."],
        "proposal": [
            {"title": "One all-in price, locked", "what": "Show the full price including fees and taxes before payment and honour it; if it changes, explain why in one line."},
            {"title": "In-app approval for extras", "what": "Any additional part or work is quoted in the app with a price cap, and the customer approves it before work starts."},
            {"title": "Public rate card for common parts", "what": "Publish typical prices so customers can see an upsell is not out of line with local rates."},
            {"title": "Small-job pricing", "what": "Review fee structure for small jobs, where fees weigh most and customers compare with local providers."}],
        "repeat_mechanism": "Price surprises damage trust, and customers who feel overcharged compare with local providers. A predictable bill makes the next booking a known quantity (hypothesis: repeat rate of customers whose final bill matched the quote vs those whose bill rose).",
        "success": "The final bill matches the booked price for almost every job, extras are approved in the app, and price complaints fall, particularly for small-ticket repeat categories.",
        "watch_out": "Revenue per booking may fall and professionals may lose upsell income; measure margin alongside repeat.",
        "effort": "M", "effort_note": "Pricing and checkout changes plus a professional-side approval flow.",
    },
    "O5": {
        "problem": "Work fails soon after the visit, and customers meet a refusal: warranty has 'expired', or rework needs repeated requests. Native purifier owners also report installation and after-sales delays.",
        "who": "Repair customers (AC, appliance, plumbing) and owners of Native products.",
        "why_it_happens": ["Warranty terms are short and unclear, so customers are surprised by the limits.", "Rework competes in the same dispatch queue as new bookings.", "Native installation and service depend on a chain of parties with no single status."],
        "proposal": [
            {"title": "One-tap 'problem after service'", "what": "Inside the warranty window, one tap reschedules the same or another professional within a stated time."},
            {"title": "Warranty visible per job", "what": "Show what is covered and the end date on the booking, and consider longer cover on high-value repairs."},
            {"title": "Native after-sales tracker", "what": "Installation and service status with a promised date, a dedicated support line and proactive delay updates."},
            {"title": "Hand-off when out of scope", "what": "If a fault is outside the service, say so plainly and point to the brand or a recommended option instead of leaving the customer stranded."}],
        "repeat_mechanism": "A repair that fails soon after is a strong reason to switch providers, and Native owners are long-term customers by design. Fixing it without a fight should protect the next booking (hypothesis).",
        "success": "Rework requests are completed quickly, warranty disputes fall, Native installations meet the promised date, and customers who needed rework still rebook.",
        "watch_out": "Warranty cost rises; abuse of rework needs light checks.",
        "effort": "M", "effort_note": "Rework flow and warranty display are contained; Native logistics is the harder part.",
    },
    "O6": {
        "problem": "Quality is inconsistent: incomplete or poor work, damage or theft, rude or unsafe conduct, pressure to give five stars, and doubts about honesty. People living alone feel the risk most in salon and massage at home.",
        "who": "All categories; salon, massage and home-alone customers for safety; AC and appliance customers for damage.",
        "why_it_happens": ["Assignment is not matched to skill and category experience.", "There is no customer-visible proof of completed work.", "Damage claims are slow, and in-person rating requests create pressure."],
        "proposal": [
            {"title": "Skill-matched assignment", "what": "Match professionals to jobs by verified skill and past results, with refreshers where quality slips."},
            {"title": "Proof of work", "what": "A short checklist and before/after photos the customer approves before the job closes."},
            {"title": "Damage cover that works", "what": "Visible cover with a fast claim path and a stated settlement time."},
            {"title": "Safety by design", "what": "Verified identity, shareable job status, a female-professional option, and ratings and tips requested in the app, not in person."}],
        "repeat_mechanism": "Customers who say they will return mostly praise the individual professional. Making that quality consistent, and making it easy to rebook the good one, should convert more first bookings into repeat bookings (hypothesis).",
        "success": "A higher share of jobs rated well without a complaint, faster damage settlement, fewer safety complaints, and more rebooking of the same professional.",
        "watch_out": "Training and checks add cost and time per job; strict scoring can reduce supply.",
        "effort": "L", "effort_note": "Largest operational scope; start with proof-of-work and damage claims.",
    },
    "O7": {
        "problem": "Customers who need a small or specific job hit minimum-order rules, find no single-bathroom or per-task option, cannot extend time, or ask for services that do not exist.",
        "who": "Small households, single-room needs and customers with one-off tasks; people asking for new categories.",
        "why_it_happens": ["Packages are sized for larger jobs, and a minimum order protects margin on small ones.", "There is no lightweight way to add time or customise a job.", "Demand for missing services is not captured."],
        "proposal": [
            {"title": "Per-task and single-unit options", "what": "Single-bathroom cleaning and similar small units with clear scope."},
            {"title": "Add-on and time extension", "what": "Let the customer extend the visit or add a task in the app, at a stated price."},
            {"title": "Capture missing demand", "what": "A custom request form that records requested services, and test the most requested categories."}],
        "repeat_mechanism": "Small jobs are where customers turn to local providers. Serving them should keep customers booking between larger jobs (hypothesis).",
        "success": "Fewer abandoned carts at the minimum-order step, more small-job bookings, and a repeat rate for small-job customers closer to the average.",
        "watch_out": "Small jobs have lower margin per visit; test price points before wide launch.",
        "effort": "S", "effort_note": "Packaging and catalogue work; no new infrastructure.",
    },
    "O8": {
        "problem": "In some areas and smaller cities customers open the app and find no service, or a category that is unavailable, with no sign of when it will arrive.",
        "who": "Customers in unserved pincodes and tier-2/3 cities.",
        "why_it_happens": ["Supply has not been built in low-density areas.", "Customers who cannot book leave no record of their demand."],
        "proposal": [
            {"title": "Pincode waitlist", "what": "Let customers join a waitlist by pincode and see nearby available categories."},
            {"title": "Use demand to decide expansion", "what": "Rank areas by waitlist demand to prioritise partner onboarding."}],
        "repeat_mechanism": "Customers who cannot book cannot return. A waitlist keeps the relationship alive until service arrives (hypothesis; the evidence here is thin).",
        "success": "Waitlist sign-ups by pincode, and bookings from waitlisted customers soon after launch.",
        "watch_out": "A waitlist raises expectations; communicate timelines honestly.",
        "effort": "S", "effort_note": "Small build; the expansion itself is a business decision.",
    },
    "O9": {
        "problem": "Customers who had a good job want the same professional again, but cannot easily rebook them, may pay extra to do so, and may be reassigned the professional they complained about.",
        "who": "Customers of recurring services (cleaning, salon, massage, plumbing) who found someone they trust.",
        "why_it_happens": ["Assignment is optimised for supply, not preference.", "Rebooking a specific person is not a first-class action.", "Complaints do not reliably block a professional for that customer."],
        "proposal": [
            {"title": "Book again with the same professional", "what": "A prominent action on the completion screen and in booking history, at no extra charge."},
            {"title": "Honour dislikes", "what": "After a complaint, never reassign that professional to that customer."},
            {"title": "Suggest favourites", "what": "Recommend the customer's well-rated professionals for the next category they need."}],
        "repeat_mechanism": "Several customers say outright they will call the same professional again. Making that one tap should convert a good job directly into a repeat booking (hypothesis; the most direct link to the metric).",
        "success": "More bookings rebooked with the same professional, and a higher 90-day repeat rate after a five-star job when the rebook prompt is shown.",
        "watch_out": "Popular professionals become overloaded; protect availability and fairness.",
        "effort": "S", "effort_note": "Contained product change using existing data.",
    },
}
