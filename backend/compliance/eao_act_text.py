"""
Employment Standards Act, 2000 (S.O. 2000, c. 41) — Structured Reference Text.

This module provides structured text representations of key ESA sections
for ingestion into the ESA reference knowledge base (ChromaDB collection).

Each entry in ESA_SECTIONS is a dict with:
  - section_id:    Official section reference (e.g., "s.5")
  - title:         Section title
  - part:          Part of the Act
  - text:          Full section text (authoritative paraphrase with statutory language)

Source: Ontario e-Laws — Employment Standards Act, 2000 (S.O. 2000, c. 41)
        https://www.ontario.ca/laws/statute/00e41
"""

from __future__ import annotations
from typing import List, Dict

ESA_SECTIONS: List[Dict[str, str]] = [

    # ─────────────────────────────────────────────────────────────────────────
    # PART I — DEFINITIONS AND APPLICATION
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.1-s.4",
        "title": "Definitions and Application",
        "part": "Part I — Definitions and Application",
        "text": (
            "Employment Standards Act, 2000 — Part I — Definitions and Application\n\n"
            "Section 1 — Definitions\n"
            "'Employee' includes a person who performs work for an employer for wages, a "
            "person who supplies services to an employer for wages, a person who receives "
            "training from a person who is an employer, or a homeworker. 'Employer' means "
            "a person who employs one or more employees. 'Wages' means monetary remuneration "
            "payable by an employer to an employee under the terms of an employment contract "
            "or statute, and includes overtime pay, public holiday pay, termination pay, "
            "severance pay, and vacation pay.\n\n"
            "Section 3 — Application\n"
            "This Act applies to employees who perform work in Ontario and to their employers, "
            "subject to limited exceptions (e.g., certain professions, federal works and "
            "undertakings). Certain employees are exempt from specific provisions under "
            "Ontario Regulation 285/01 (e.g., managers and supervisors, professionals, "
            "IT professionals from overtime). The Act applies regardless of whether the "
            "employment contract specifies otherwise.\n\n"
            "Section 4 — Conflicts with other Acts\n"
            "If a provision of any other Act or a collective agreement provides a greater "
            "benefit to an employee than the corresponding provision of this Act, the other "
            "Act or collective agreement prevails."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART I — CONTRACTING OUT / WAIVER
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.5",
        "title": "Contracting Out Prohibited — ESA Rights Cannot Be Waived",
        "part": "Part I — Definitions and Application",
        "text": (
            "Employment Standards Act, 2000 — Section 5 — Contracting Out\n\n"
            "Section 5(1): Subject to subsection (2), no employer or agent of an employer "
            "and no employee or agent of an employee shall contract out of or waive an "
            "employment standard, and any such contracting out or waiver is VOID.\n\n"
            "Section 5(2): If an employment contract or collective agreement provides a "
            "greater benefit to an employee than the employment standard, the contract or "
            "agreement prevails to the extent of the greater benefit.\n\n"
            "Practical effect: Any provision in an employment contract that attempts to "
            "give the employee less than an ESA minimum — whether for termination notice, "
            "vacation pay, overtime, leaves of absence, or any other employment standard — "
            "is void and unenforceable. The ESA minimum automatically applies. This includes:\n"
            "- Termination clauses that cap pay-in-lieu below the s.57 notice schedule\n"
            "- Vacation clauses that set vacation pay below 4% (or 6% after 5 years)\n"
            "- Overtime clauses that deny overtime to non-exempt employees\n"
            "- Leave clauses that restrict or condition statutory leave entitlements\n"
            "- Salary clauses that include language like 'in lieu of all overtime pay' "
            "for non-exempt employees\n"
            "- Any 'full and final satisfaction' or 'complete payment' clause that purports "
            "to extinguish ESA entitlements\n\n"
            "A severance clause stating 'X weeks' pay in full and final satisfaction of all "
            "claims including ESA' is only valid if X weeks meets or exceeds the combined "
            "ESA termination notice AND severance pay entitlement."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART VI — INFORMATION TO EMPLOYEES
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.6",
        "title": "ESA Poster — Information to New Employees",
        "part": "Part VI — Information to Be Provided to Employees",
        "text": (
            "Employment Standards Act, 2000 — Section 6 — Employer's Duty to Post Information\n\n"
            "Section 6(1): Every employer shall post, in at least one conspicuous place in "
            "every workplace of the employer where it is likely to come to the attention "
            "of the employer's employees, a poster approved by the Director that contains "
            "information about this Act and its regulations.\n\n"
            "Section 6(2): Every employer shall provide to each employee a copy of the "
            "poster referred to in subsection (1) in the manner approved by the Director.\n\n"
            "The 'ESA Poster' (also called 'Employment Standards in Ontario') must be "
            "provided to every employee. It summarizes key rights: minimum wage, hours of "
            "work, overtime, public holidays, vacation, leaves of absence, termination, "
            "and severance. New employees should receive this poster as part of onboarding."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART VII — HOURS OF WORK
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.17",
        "title": "Maximum Hours of Work — Daily and Weekly Limits",
        "part": "Part VII — Hours of Work and Eating Periods",
        "text": (
            "Employment Standards Act, 2000 — Section 17 — Maximum Hours of Work\n\n"
            "Section 17(1): No employer shall require or permit an employee to work more "
            "than eight hours in a day or, if the employer establishes a regular work day "
            "of more than eight hours for the employee, more than the number of hours in "
            "that regular work day.\n\n"
            "Section 17(2): No employer shall require or permit an employee to work more "
            "than 48 hours in a work week.\n\n"
            "Section 17(3): An employer may require or permit an employee to work more "
            "than eight hours in a day (or more than the established regular work day) "
            "or more than 48 hours in a work week only if:\n"
            "(a) the employer and employee have agreed (in writing) to the excess hours; AND\n"
            "(b) the employee has been provided with a copy of the Director's information "
            "sheet about hours of work and overtime.\n\n"
            "Maximum working hours with an excess hours agreement: Up to 60 hours per week.\n\n"
            "Note: Certain employees are exempt from Part VII, including managers and "
            "supervisors, landscape gardeners, hunting and fishing guides, domestic "
            "workers living in the employer's residence, and others listed in "
            "O. Reg. 285/01.\n\n"
            "Contracts that state 'Employee agrees to work such hours as are required' "
            "without a specific excess-hours agreement do NOT constitute valid agreement "
            "under s.17(3). A blanket contractual term does not satisfy the requirement "
            "for a written excess-hours agreement."
        ),
    },

    {
        "section_id": "s.18",
        "title": "Eating Periods — Meal Breaks",
        "part": "Part VII — Hours of Work and Eating Periods",
        "text": (
            "Employment Standards Act, 2000 — Section 18 — Eating Periods\n\n"
            "Section 18(1): An employer shall give an employee an eating period of at least "
            "30 minutes at intervals that will result in the employee not working for more "
            "than five consecutive hours without an eating period.\n\n"
            "Section 18(2): An eating period is an unpaid period unless the employee is "
            "required by the employer to work or to be available for work during the period, "
            "in which case the period is considered time worked.\n\n"
            "Practical effect: Every employee must receive at least a 30-minute eating period "
            "for every 5 continuous hours of work. An employee working an 8-hour shift must "
            "receive at least one 30-minute break before or at the 5-hour mark. Two shorter "
            "breaks do NOT satisfy s.18 — the eating period must be at least 30 consecutive "
            "minutes. Rest breaks (shorter breaks) are separate from eating periods and are "
            "not mandated by the ESA (though many contracts provide them).\n\n"
            "A contract provision stating 'no meal break required' or 'meal break may be "
            "waived at the employee's discretion' is void under s.5 to the extent it "
            "purports to eliminate the minimum 30-minute eating period."
        ),
    },

    {
        "section_id": "s.19",
        "title": "Rest Period Between Shifts",
        "part": "Part VII — Hours of Work and Eating Periods",
        "text": (
            "Employment Standards Act, 2000 — Section 19 — Rest Period Between Shifts\n\n"
            "Section 19(1): An employer shall ensure that an employee has at least "
            "11 consecutive hours free from performing work in each day.\n\n"
            "Section 19(2): Subsection (1) does not apply if the employee's total hours "
            "of work in the day are two hours or fewer, the employee is called in to work "
            "unscheduled emergency work, or the employee is required to attend a training "
            "program authorized by the employer.\n\n"
            "Practical effect: There must be at least 11 consecutive hours between the "
            "end of one shift and the beginning of the next. For example, if an employee "
            "finishes a shift at 10 PM, the next shift cannot start until 9 AM the "
            "following day. Scheduling that does not provide 11-hour rest periods between "
            "shifts violates s.19."
        ),
    },

    {
        "section_id": "s.20",
        "title": "Weekly Rest Period",
        "part": "Part VII — Hours of Work and Eating Periods",
        "text": (
            "Employment Standards Act, 2000 — Section 20 — Weekly Rest Period\n\n"
            "Section 20(1): An employer shall give an employee a period of at least "
            "24 consecutive hours free from performing work in each work week.\n\n"
            "Section 20(3): If a period free from work of at least 48 consecutive hours "
            "is not provided in a two-week period, the employee must be given at least "
            "48 hours of rest in the following two-week period.\n\n"
            "Practical effect: Every employee is entitled to at least one full day off "
            "(24 consecutive hours) in each work week. This is a minimum — many contracts "
            "provide two consecutive days off (48 hours) per week."
        ),
    },

    {
        "section_id": "s.21.1.1",
        "title": "Right to Disconnect — Employer Policy Requirement",
        "part": "Part VII — Hours of Work and Eating Periods",
        "text": (
            "Employment Standards Act, 2000 — Section 21.1.1 — Right to Disconnect\n"
            "(Added by Working for Workers Act, 2021, S.O. 2021, c. 35)\n\n"
            "Section 21.1.1(1): An employer that employs 25 or more employees on January 1 "
            "of any year shall, before March 1 of that year, have a written policy with "
            "respect to employees disconnecting from work.\n\n"
            "Section 21.1.1(2): The policy shall include the date it was prepared and the "
            "date any changes to it were made.\n\n"
            "Section 21.1.1(3): If an employer is required to have a policy under this "
            "section, the employer shall provide a copy of the policy to each employee.\n\n"
            "'Disconnecting from work' means not engaging in work-related communications, "
            "including emails, telephone calls, video calls or the sending or reviewing "
            "of other messages, so as to be free from the performance of work.\n\n"
            "Practical effect: Employers with 25+ employees must have a written policy "
            "about when and how employees can be expected to respond to work communications "
            "outside regular hours. Employment contracts that impose mandatory after-hours "
            "availability without compensation may be inconsistent with this policy requirement "
            "and may constitute uncompensated overtime."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART VIII — OVERTIME PAY
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.22",
        "title": "Overtime Pay — Minimum 1.5× After 44 Hours per Week",
        "part": "Part VIII — Overtime Pay",
        "text": (
            "Employment Standards Act, 2000 — Section 22 — Overtime Pay\n\n"
            "Section 22(1): An employer shall pay an employee overtime pay of at least "
            "one and one-half times the employee's regular rate for each hour of work "
            "in a work week in excess of 44 hours.\n\n"
            "Section 22(2): Where an employee has two or more regular rates of pay, the "
            "overtime rate is calculated based on the weighted average of the regular rates.\n\n"
            "Section 22.1 — Overtime Averaging Agreements: Employers and employees may "
            "agree in writing to average the employee's hours of work over a period of "
            "two or more consecutive weeks for the purpose of determining overtime pay "
            "entitlement. Overtime averaging agreements must be in writing and must state "
            "the number of weeks over which overtime is averaged. They cannot reduce the "
            "employee's entitlement below what would be owed without averaging.\n\n"
            "Exemptions: Certain employees are exempt from overtime pay requirements "
            "under O. Reg. 285/01, including:\n"
            "- Managers and supervisors\n"
            "- Certain IT professionals (IT professionals who perform non-supervisory "
            "  work and earn $30/hour or more are exempt)\n"
            "- Professionals (lawyers, accountants, doctors, dentists, engineers, "
            "  architects, surveyors, veterinarians, pharmacists)\n"
            "- Certain residential care workers\n\n"
            "A contract clause stating that an employee's 'salary is inclusive of all "
            "overtime pay' does NOT exempt a non-exempt employee from overtime unless "
            "the salary exceeds the overtime entitlement. Such clauses are void under s.5 "
            "to the extent they attempt to deny overtime to non-exempt employees."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART IX — MINIMUM WAGE
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.23",
        "title": "Minimum Wage — Ontario Rates",
        "part": "Part IX — Minimum Wage",
        "text": (
            "Employment Standards Act, 2000 — Section 23 — Minimum Wage\n\n"
            "Section 23(1): An employer shall pay an employee at least the prescribed "
            "minimum wage.\n\n"
            "Section 23(2): Where the prescribed minimum wage is being increased, an "
            "employer shall continue to pay any higher wage already being paid. The "
            "minimum wage cannot be reduced.\n\n"
            "Ontario Minimum Wage Rates (under O. Reg. 285/01, as of October 2024):\n"
            "- General minimum wage: $17.20 per hour\n"
            "- Student minimum wage (under 18, ≤28 hours/week during school): $16.20 per hour\n"
            "- Liquor servers: $17.20 per hour (equalised with general rate as of January 2022)\n"
            "- Homeworkers: $18.90 per hour (110% of general minimum wage)\n\n"
            "Minimum wage applies to all wages earned — base salary, commissions, piece-rate — "
            "and cannot be reduced by deductions, charge-backs, or repayment obligations "
            "that would bring hourly effective pay below the minimum wage rate.\n\n"
            "Section 11 — Pay Periods: Employees must be paid at regular intervals not "
            "greater than semi-monthly (twice per month). Employers must provide pay "
            "statements showing details of wages earned and deductions."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART X — PUBLIC HOLIDAYS
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.26-s.32",
        "title": "Public Holidays — Ontario Statutory Holidays",
        "part": "Part X — Public Holidays",
        "text": (
            "Employment Standards Act, 2000 — Sections 26–32 — Public Holidays\n\n"
            "Section 26(1): An eligible employee is entitled to a public holiday and to "
            "be paid public holiday pay for the holiday.\n\n"
            "The 9 Ontario public holidays are:\n"
            "1. New Year's Day (January 1)\n"
            "2. Family Day (third Monday in February)\n"
            "3. Good Friday\n"
            "4. Victoria Day (Monday before May 25)\n"
            "5. Canada Day (July 1, or July 2 if July 1 is Sunday)\n"
            "6. Labour Day (first Monday in September)\n"
            "7. Thanksgiving Day (second Monday in October)\n"
            "8. Christmas Day (December 25)\n"
            "9. Boxing Day (December 26)\n\n"
            "Section 27 — Public holiday pay calculation: Public holiday pay for a "
            "given public holiday equals the amount of regular wages earned by the employee "
            "in the 4 work weeks before the work week in which the public holiday occurs, "
            "divided by 20.\n\n"
            "Section 29 — Work on a public holiday: If an employer requires an employee "
            "to work on a public holiday, the employee is entitled to either:\n"
            "(a) public holiday pay for the holiday PLUS premium pay (1.5× regular rate) "
            "for hours worked on the holiday; OR\n"
            "(b) regular wages for hours worked on the holiday PLUS a substitute day off "
            "with public holiday pay at a time agreed between employer and employee.\n\n"
            "Section 31 — Substitute holidays: Employers and employees may agree to "
            "substitute another day as a public holiday instead of the actual public holiday.\n\n"
            "Eligibility: An employee is eligible for public holiday pay if they worked "
            "their last regularly scheduled day before, and their first regularly scheduled "
            "day after, the public holiday (unless the employee has reasonable cause for "
            "not doing so).\n\n"
            "Contracts that state 'all statutory holidays included in base salary' must "
            "ensure the effective hourly rate attributable to holiday pay meets the "
            "ESA minimum calculation. Blanket 'all-inclusive' language does not satisfy "
            "s.26 unless the hourly equivalent is at least equal to the statutory minimum."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART XI — VACATION WITH PAY
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.33-s.41",
        "title": "Vacation with Pay — Time Entitlement and Pay Calculation",
        "part": "Part XI — Vacation with Pay",
        "text": (
            "Employment Standards Act, 2000 — Sections 33–41 — Vacation with Pay\n\n"
            "Section 33(1): Subject to this section, an employee is entitled to vacation "
            "time calculated in accordance with this section.\n\n"
            "Section 33(2): An employee is entitled to at least 2 weeks of vacation time "
            "after each 12-month vacation entitlement year.\n\n"
            "Section 33(3): If, at the end of a vacation entitlement year, an employee "
            "has been employed by the same employer for 5 or more years, the employee "
            "is entitled to at least 3 weeks of vacation time.\n\n"
            "Section 33 — Vacation entitlement year: This is the 12-month period beginning "
            "with the employee's start date (or a different 12-month period the employer "
            "establishes for all employees).\n\n"
            "Section 35 — Timing of vacation: The employer must give the employee their "
            "vacation time as a completed vacation within 10 months of the end of the "
            "vacation entitlement year. Vacation must be given and taken in complete weeks "
            "(or lesser periods if the employer and employee agree).\n\n"
            "Section 35.2 — Vacation pay:\n"
            "(1) Vacation pay for an employee with fewer than 5 years of service must "
            "equal at least 4 per cent of the wages (excluding vacation pay itself) earned "
            "during the entitlement period.\n"
            "(2) Vacation pay for an employee with 5 or more years of service must equal "
            "at least 6 per cent of wages earned during the entitlement period.\n\n"
            "Section 41 — Vacation pay on termination: On termination of employment, an "
            "employer must pay any vacation pay owing, including vacation pay accrued but "
            "not yet paid.\n\n"
            "'Use-it-or-lose-it' vacation policies that forfeit accrued vacation time are "
            "void under s.5 to the extent they deprive employees of their ESA vacation "
            "entitlement. While employers can implement vacation scheduling policies, they "
            "cannot eliminate the entitlement itself."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART XII — EQUAL PAY
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.42-s.43.1",
        "title": "Equal Pay for Equal Work — Sex and Employment Status",
        "part": "Part XII — Equal Pay for Equal Work",
        "text": (
            "Employment Standards Act, 2000 — Sections 42–43.1 — Equal Pay for Equal Work\n\n"
            "Section 42(1): No employer shall pay an employee of one sex at a rate of pay "
            "less than the rate paid to an employee of the other sex when:\n"
            "(a) they perform substantially the same kind of work in the same establishment;\n"
            "(b) their performance requires substantially the same skill, effort, and "
            "responsibility; and\n"
            "(c) their work is performed under similar working conditions.\n\n"
            "Section 43 — Permitted differentials: A difference in the rate of pay between "
            "employees of different sexes based on a seniority system, merit system, system "
            "that measures earnings by quantity or quality of production (piece-rate), or "
            "any factor other than sex does NOT violate s.42.\n\n"
            "Section 42.1 — Employment status: No employer shall pay an employee who is "
            "a part-time, casual, temporary, or seasonal employee at a rate of pay less "
            "than the rate paid to a full-time employee for performing substantially the "
            "same kind of work in the same establishment, requiring substantially the same "
            "skill, effort, and responsibility, under similar working conditions.\n\n"
            "Section 43.1 — Employment status differential permitted if based on seniority, "
            "merit, or piece-rate — but NOT based on employment status alone.\n\n"
            "Practical effect: A part-time employee doing the same job as a full-time employee "
            "in the same establishment must be paid the same hourly rate (or higher). "
            "Contracts cannot contain clauses setting a lower hourly rate for part-time "
            "work without justification based on seniority, merit, or piece-rate system."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART XIII — BENEFIT PLANS
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.44",
        "title": "Benefit Plans — Non-Discrimination",
        "part": "Part XIII — Benefit Plans",
        "text": (
            "Employment Standards Act, 2000 — Section 44 — Benefit Plans\n\n"
            "Section 44(1): No employer shall make a distinction, exclusion or preference "
            "as between employees in any of the following on the basis of sex (including "
            "pregnancy), marital status or same-sex partnership status:\n"
            "(a) pension plans;\n"
            "(b) group life insurance plans;\n"
            "(c) accidental death and dismemberment plans;\n"
            "(d) disability insurance or income protection plans;\n"
            "(e) medical, surgical, or hospitalization benefit plans.\n\n"
            "Section 44(2): Subsection (1) does not apply to prevent distinctions based "
            "on actuarial data that is reasonable and reliable, distinctions based on "
            "benefit claims experience, or distinctions between employees in the same "
            "category (based on length of service, employment class, etc.).\n\n"
            "Practical effect: Benefit plan provisions that provide different levels of "
            "disability insurance, life insurance, or health benefits to male vs. female "
            "employees, or to married vs. single employees, violate s.44. Employers must "
            "ensure all benefit plan descriptions in employment contracts comply with s.44."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART XIV — LEAVES OF ABSENCE
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.46-s.48",
        "title": "Pregnancy and Parental Leave — Job-Protected Leaves",
        "part": "Part XIV — Leaves of Absence",
        "text": (
            "Employment Standards Act, 2000 — Sections 46–48 — Pregnancy and Parental Leave\n\n"
            "Section 46(1) — Pregnancy Leave: An employee who is pregnant and who has been "
            "employed by her employer for at least 13 weeks before the expected birth date "
            "is entitled to a leave of absence without pay (pregnancy leave).\n\n"
            "Section 46(2) — Duration: Pregnancy leave is at least 17 weeks in total "
            "(pregnancy leave begins no earlier than 17 weeks before the expected birth "
            "date and ends no later than 17 weeks after the actual birth date, stillbirth, "
            "or miscarriage).\n\n"
            "Section 48(1) — Parental Leave: An employee who is a parent of a child is "
            "entitled to a leave of absence without pay (parental leave) if the employee "
            "has been employed by the employer for at least 13 weeks before the leave begins.\n\n"
            "Section 48(2) — Duration of parental leave:\n"
            "- An employee who took pregnancy leave: up to 61 weeks of parental leave\n"
            "- An employee who did not take pregnancy leave (e.g., adoptive parent, "
            "  non-birth parent): up to 63 weeks of parental leave\n\n"
            "Section 53 — Reinstatement: At the end of a leave under Part XIV, an "
            "employer shall reinstate the employee to the position the employee most "
            "recently held, if it still exists, or to a comparable position if it does not.\n\n"
            "Section 53.1 — Seniority and benefits during leave: An employee continues "
            "to participate in pension, life insurance, accidental death insurance, "
            "extended health plans, and dental plans during a leave under Part XIV, unless "
            "they elect in writing not to do so. Length of service continues to accumulate "
            "during leave.\n\n"
            "Prohibition: Any employment contract term that discourages pregnancy or "
            "parental leave, conditions benefits on not taking leave, or penalizes an "
            "employee for taking leave is void under s.5 and constitutes reprisal under s.74."
        ),
    },

    {
        "section_id": "s.49",
        "title": "Family Medical Leave",
        "part": "Part XIV — Leaves of Absence",
        "text": (
            "Employment Standards Act, 2000 — Section 49 — Family Medical Leave\n\n"
            "Section 49(1): An employee is entitled to a leave of absence without pay of "
            "up to 28 weeks in a 52-week period to provide care or support to a qualifying "
            "family member who has a serious medical condition with a significant risk of "
            "death within 26 weeks (as certified by a qualified health practitioner).\n\n"
            "Qualifying family members include: a parent (including step-parent, foster "
            "parent), a child (including step-child, foster child), a spouse (including "
            "same-sex spouse), and certain other relatives as defined in O. Reg. 476/06.\n\n"
            "Section 49(3): The employee is entitled to take the leave in periods of no "
            "less than 1 week, unless the employer and employee agree otherwise.\n\n"
            "Section 49(9): On the expiry of the leave, the employer shall reinstate the "
            "employee to the position most recently held, or to a comparable position.\n\n"
            "Note: Family medical leave under s.49 corresponds to federal EI compassionate "
            "care benefits under the Employment Insurance Act."
        ),
    },

    {
        "section_id": "s.49.5",
        "title": "Family Caregiver Leave",
        "part": "Part XIV — Leaves of Absence",
        "text": (
            "Employment Standards Act, 2000 — Section 49.5 — Family Caregiver Leave\n\n"
            "Section 49.5(1): An employee is entitled to a leave of absence without pay "
            "of up to 8 weeks per calendar year for each qualifying family member who "
            "has a serious medical condition.\n\n"
            "An employee may take up to 8 weeks per qualifying family member per calendar "
            "year. If an employee has multiple family members with serious medical conditions, "
            "they can take up to 8 weeks per family member (up to 8 family members per year).\n\n"
            "Qualifying family members include parents, children, spouses, and a broad "
            "range of other relatives as defined in O. Reg. 476/06.\n\n"
            "Section 49.5(9): Reinstatement rights apply on return from leave.\n\n"
            "Unlike family medical leave (s.49), a health practitioner's certificate is "
            "not required to begin family caregiver leave — the employee self-certifies "
            "the qualifying condition."
        ),
    },

    {
        "section_id": "s.49.1-s.49.6",
        "title": "Critical Illness Leave — Child and Adult",
        "part": "Part XIV — Leaves of Absence",
        "text": (
            "Employment Standards Act, 2000 — Sections 49.1 and 49.6 — Critical Illness Leave\n\n"
            "Section 49.1(1) — Critical Illness Leave (Child): An employee is entitled "
            "to a leave of absence without pay of up to 37 weeks in a 52-week period to "
            "provide care or support to a critically ill child (under 18 years old).\n\n"
            "A 'critically ill child' is defined as a child whose baseline state of health "
            "has significantly changed and whose life is at risk as a result of an illness "
            "or injury, as certified by a qualified health practitioner.\n\n"
            "Section 49.6(1) — Critical Illness Leave (Adult): An employee is entitled "
            "to a leave of absence without pay of up to 16 weeks in a 52-week period to "
            "provide care or support to a critically ill adult family member.\n\n"
            "Both leaves require a certificate from a qualified health practitioner. "
            "Both are job-protected under the reinstatement provisions of s.53. "
            "Benefit continuation under s.53.1 applies to both leaves."
        ),
    },

    {
        "section_id": "s.49.7",
        "title": "Domestic or Sexual Violence Leave",
        "part": "Part XIV — Leaves of Absence",
        "text": (
            "Employment Standards Act, 2000 — Section 49.7 — Domestic or Sexual Violence Leave\n\n"
            "Section 49.7(1): An employee who has been employed for at least 13 consecutive "
            "weeks and who has experienced or whose child has experienced domestic or sexual "
            "violence is entitled to a leave of absence.\n\n"
            "Section 49.7(2) — Short leave: Up to 10 days per calendar year:\n"
            "- The first 5 days are PAID at regular wages\n"
            "- The remaining 5 days are UNPAID\n"
            "These days may be taken as needed (not necessarily consecutively).\n\n"
            "Section 49.7(3) — Extended leave: Up to 15 additional weeks per calendar year "
            "(unpaid). This leave may be taken to: seek medical attention, obtain services "
            "from a violence-related organization, obtain psychological or other professional "
            "counselling, relocate temporarily or permanently, seek legal or law enforcement "
            "assistance, or care for a child affected by the violence.\n\n"
            "Section 49.7(7) — Confidentiality: The employer shall keep confidential all "
            "information pertaining to the leave, unless the employee consents in writing "
            "to the disclosure or the disclosure is required by law.\n\n"
            "The leave is job-protected (s.53 reinstatement applies). An employer may "
            "require evidence of the domestic or sexual violence, but must do so in a "
            "manner that is reasonable in the circumstances."
        ),
    },

    {
        "section_id": "s.50.0.1",
        "title": "Sick Leave — 3 Days Per Calendar Year",
        "part": "Part XIV — Leaves of Absence",
        "text": (
            "Employment Standards Act, 2000 — Section 50.0.1 — Sick Leave\n\n"
            "Section 50.0.1(1): An employee who has been employed by an employer for at "
            "least two consecutive weeks is entitled to a leave of absence of up to "
            "3 days per calendar year due to personal illness, injury, or medical emergency.\n\n"
            "The 3 sick days are UNPAID (the ESA sets a minimum; employers may provide "
            "paid sick leave as a greater benefit under s.5(2)).\n\n"
            "Section 50.0.1(3): The sick days may be taken as needed — they do not need "
            "to be consecutive.\n\n"
            "Section 50.0.1(5): The employer shall not penalize an employee for taking "
            "sick leave.\n\n"
            "An employer may require the employee to provide evidence reasonable in the "
            "circumstances, but cannot require a doctor's note from the first day of sick "
            "leave as a condition of entitlement to ESA sick leave. Requiring medical "
            "documentation for every sick day (including the first day) may deter employees "
            "from exercising their rights and constitute reprisal.\n\n"
            "Note: These are separate from personal emergency leave under older provisions. "
            "As of January 1, 2019, sick leave (s.50.0.1) is distinct from family "
            "responsibility leave and bereavement leave."
        ),
    },

    {
        "section_id": "s.50.0.2",
        "title": "Bereavement Leave — 2 Days",
        "part": "Part XIV — Leaves of Absence",
        "text": (
            "Employment Standards Act, 2000 — Section 50.0.2 — Bereavement Leave\n\n"
            "Section 50.0.2(1): An employee who has been employed for at least 2 consecutive "
            "weeks is entitled to a leave of absence of up to 2 days upon the death of a "
            "qualifying family member.\n\n"
            "Section 50.0.2(2): Qualifying family members include: the employee's spouse, "
            "a parent (including step-parent, foster parent, parent by adoption), a child "
            "(including step-child, foster child, child by adoption), a grandparent, "
            "a grandchild, a sibling, and the spouse's parent.\n\n"
            "The 2 bereavement leave days are UNPAID.\n\n"
            "An employer may not penalize an employee for taking bereavement leave. "
            "A contract that provides only 1 day of bereavement leave, or that limits "
            "bereavement leave to 'immediate family' defined more narrowly than ESA, "
            "violates s.5 to the extent it provides less than the ESA minimum."
        ),
    },

    {
        "section_id": "s.50.1",
        "title": "Reservist Leave",
        "part": "Part XIV — Leaves of Absence",
        "text": (
            "Employment Standards Act, 2000 — Section 50.1 — Reservist Leave\n\n"
            "Section 50.1(1): An employee who is a member of the Canadian Forces Reserve "
            "and who has been employed by an employer for at least 6 consecutive months "
            "is entitled to a leave of absence without pay when the employee is called out "
            "for active service, instructional duty, training, or any other reserve service.\n\n"
            "Section 50.1(4): The employer shall reinstate the employee to the position "
            "most recently held, or to a comparable position, on the conclusion of the "
            "reservist leave.\n\n"
            "Employment contracts that attempt to terminate employment because of reservist "
            "leave, or that require employees to choose between their job and reserve "
            "service, violate s.50.1 and s.74 (anti-reprisal)."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART XV — TERMINATION OF EMPLOYMENT
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.54-s.62",
        "title": "Termination of Employment — Notice and Termination Pay",
        "part": "Part XV — Termination of Employment",
        "text": (
            "Employment Standards Act, 2000 — Sections 54–62 — Termination of Employment\n\n"
            "Section 54(1): No employer shall terminate the employment of an employee who "
            "has been continuously employed for 3 months or more unless the employer:\n"
            "(a) has given to the employee written notice of termination in the amount "
            "required by s.57 or s.58; and\n"
            "(b) the notice period has expired; OR\n"
            "(c) the employee is guilty of wilful misconduct, disobedience, or wilful "
            "neglect of duty that is not trivial and has not been condoned by the employer.\n\n"
            "MINIMUM NOTICE PERIODS — Section 57:\n"
            "The written notice of termination must be given at least:\n"
            "  - 1 week: employed less than 1 year\n"
            "  - 2 weeks: employed 1 year or more but less than 3 years\n"
            "  - 3 weeks: employed 3 years or more but less than 4 years\n"
            "  - 4 weeks: employed 4 years or more but less than 5 years\n"
            "  - 5 weeks: employed 5 years or more but less than 6 years\n"
            "  - 6 weeks: employed 6 years or more but less than 7 years\n"
            "  - 7 weeks: employed 7 years or more but less than 8 years\n"
            "  - 8 weeks: employed 8 years or more\n\n"
            "Note: Mass termination (50 or more employees in 4 weeks) requires minimum "
            "8 weeks' notice regardless of individual service length (s.58).\n\n"
            "Section 60 — Pay in lieu of notice: An employer may choose to provide "
            "termination pay equal to the wages the employee would have earned during the "
            "notice period, instead of giving working notice. Termination pay must be paid "
            "within 7 days of the last day of employment or the next regular pay date "
            "(whichever is later) — s.61.\n\n"
            "Section 58 — Probation: No notice is required for employees in their first "
            "3 months of employment (the qualifying period). After 3 months, all ESA "
            "termination notice requirements apply.\n\n"
            "CRITICAL — Termination clause requirements:\n"
            "Any termination clause in an employment contract that purports to limit "
            "the employee's notice or pay in lieu must:\n"
            "1. Meet or exceed the ESA minimum notice period for the employee's length of service\n"
            "2. Not violate any ESA entitlement (including benefits continuation during notice)\n"
            "3. Use clear language — courts strictly construe termination clauses against employers\n\n"
            "If a termination clause is found to be void or unenforceable (e.g., because it "
            "could operate below ESA minimums), the entire clause may be void and the employee "
            "may be entitled to common law reasonable notice (which is typically much longer). "
            "Recent Ontario cases have found clauses void even if they appear to provide ESA "
            "minimums, if they do not account for benefit continuation or if they try to "
            "'cap' notice below the statutory schedule for longer-service employees."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART XVI — SEVERANCE PAY
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.63-s.66",
        "title": "Severance Pay — Entitlement and Calculation",
        "part": "Part XVI — Severance Pay",
        "text": (
            "Employment Standards Act, 2000 — Sections 63–66 — Severance Pay\n\n"
            "Section 63(1) — Severance pay entitlement: An employer who severs an "
            "employment relationship with an employee shall pay severance pay to the "
            "employee if the employee was employed by the employer for 5 years or more AND:\n"
            "(a) the severance occurred because of a permanent discontinuance of all or "
            "part of the employer's business at an establishment and the employee is one "
            "of 50 or more employees who have their employment relationship severed within "
            "a 6-month period as a result; OR\n"
            "(b) the employer has a payroll of $2.5 million or more.\n\n"
            "'Payroll' means the total wages paid by the employer in the province of "
            "Ontario in the last or second-to-last fiscal year before the date of "
            "severance (whichever is greater).\n\n"
            "Section 63(1)(c) — Exclusion for wilful misconduct: An employee is not "
            "entitled to severance pay if the employment relationship was severed because "
            "of the employee's wilful misconduct, disobedience, or wilful neglect of duty "
            "that is not trivial and has not been condoned.\n\n"
            "Section 64(1) — Amount of severance pay:\n"
            "Severance pay = (regular wages for a regular work week) × (sum of:\n"
            "  (a) number of completed years of employment; plus\n"
            "  (b) number of completed months of employment divided by 12)\n\n"
            "Maximum severance pay: 26 weeks' regular wages.\n\n"
            "Section 64(2) — Severance pay is paid in addition to termination pay under "
            "Part XV. They are separate obligations — an employer cannot satisfy both "
            "severance and termination pay with a single lump sum unless the amount "
            "equals or exceeds the combined total.\n\n"
            "Section 65 — Deemed severance: An employee is deemed to have been severed "
            "if the employee has been laid off for more than 35 weeks in a period of "
            "52 consecutive weeks (or the period of a layoff under s.56(2)(c) if longer).\n\n"
            "IMPORTANT: Contracts that state 'severance pay as required by the ESA' or "
            "'in lieu of any severance obligation' without specifying the formula may "
            "be insufficient if the lump sum provided is less than the calculated amount. "
            "Employers with $2.5M+ payroll should specifically acknowledge severance "
            "pay obligations and the correct formula."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART XVII — REPRISAL
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.74",
        "title": "Anti-Reprisal — Protection for Exercising ESA Rights",
        "part": "Part XVII — Reprisal",
        "text": (
            "Employment Standards Act, 2000 — Section 74 — Reprisal\n\n"
            "Section 74(1): No employer or person acting on behalf of an employer shall "
            "intimidate, dismiss, or otherwise penalize an employee or threaten to do so "
            "because:\n"
            "(a) the employee asked the employer to comply with this Act and the regulations;\n"
            "(b) the employee made inquiries about their rights under this Act;\n"
            "(c) the employee filed a complaint with an employment standards officer;\n"
            "(d) the employee exercised or attempted to exercise a right under this Act;\n"
            "(e) the employer was ordered to reinstate the employee or pay the employee "
            "wages under this Act.\n\n"
            "Section 74(2): No employer or person acting on behalf of an employer shall "
            "refuse to pay an employee wages or alter the employee's terms of employment "
            "because the employee exercised or attempted to exercise a right under this Act.\n\n"
            "Practical effect: Employers cannot:\n"
            "- Fire or discipline an employee for taking ESA-protected leave\n"
            "- Reduce an employee's pay or hours because they filed a complaint\n"
            "- Demote an employee who returned from pregnancy leave\n"
            "- Include contract clauses that reduce benefits if an employee takes leave\n"
            "- Use NDAs or settlement agreements to silence employees from reporting ESA violations\n"
            "- Create a chilling effect through 'at-will' type termination language that "
            "  deters employees from exercising ESA rights\n\n"
            "The burden of proof is reversed in reprisal complaints: once the employee "
            "establishes they exercised an ESA right and faced an adverse action, the "
            "employer must prove the action was not reprisal."
        ),
    },

    # ─────────────────────────────────────────────────────────────────────────
    # PART XVIII.1 — EMPLOYEE MISCLASSIFICATION
    # ─────────────────────────────────────────────────────────────────────────

    {
        "section_id": "s.83.2",
        "title": "Employee Misclassification — Prohibition and Burden of Proof",
        "part": "Part XVIII.1 — Employee Misclassification",
        "text": (
            "Employment Standards Act, 2000 — Section 83.2 — Employee Misclassification\n"
            "(Added by Working for Workers Act, 2022, S.O. 2022, c. 7, Sched. 1)\n\n"
            "Section 83.2(1): No employer or person acting on behalf of an employer shall "
            "treat or represent a person who is an employee as if the person were not an "
            "employee.\n\n"
            "Section 83.2(2): If an employer or person treats or represents a person as "
            "not being an employee, the employer or person has the burden of proving that "
            "the person is not an employee.\n\n"
            "Key factors used to determine employee vs. independent contractor status:\n"
            "1. CONTROL: Does the employer direct how, when, and where the work is done?\n"
            "2. INTEGRATION: Is the worker an integral part of the employer's business?\n"
            "3. ECONOMIC REALITY: Does the worker bear financial risk and have opportunity "
            "   for profit? Do they invest in equipment? Do they provide services to "
            "   multiple clients?\n"
            "4. TOOL OWNERSHIP: Does the worker own their tools and equipment?\n"
            "5. EXCLUSIVITY: Is the worker prohibited from working for others?\n\n"
            "Red flags for misclassification in a contract:\n"
            "- Contract labels worker 'independent contractor' but grants employer "
            "  significant control over how work is done\n"
            "- Worker cannot subcontract or delegate work\n"
            "- Worker is integrated into employer's regular operations\n"
            "- Worker is economically dependent on a single 'client'\n"
            "- Employer provides tools, equipment, or workspace\n"
            "- Fixed hours or workplace assigned by 'client'\n"
            "- Exclusive or near-exclusive services required\n\n"
            "Misclassification has serious consequences: all ESA protections apply "
            "retroactively when a worker is found to be an employee, including back pay "
            "for minimum wage shortfalls, overtime, vacation pay, and termination/severance."
        ),
    },

    {
        "section_id": "s.41.1.1",
        "title": "Electronic Monitoring Policy — Employer Disclosure Obligation",
        "part": "Part VII.0.2 — Electronic Monitoring",
        "text": (
            "Employment Standards Act, 2000 — Section 41.1.1 — Electronic Monitoring\n"
            "(Added by Working for Workers Act, 2022 / Bill 88)\n\n"
            "Section 41.1.1(1): An employer that employs 25 or more employees on January 1 "
            "of any year shall, before March 1 of that year, ensure that there is a written "
            "policy in place with respect to any electronic monitoring of employees by the "
            "employer.\n\n"
            "Section 41.1.1(2): The written policy must include:\n"
            "(a) whether the employer electronically monitors employees and, if so, a "
            "description of how and in what circumstances the employer may electronically "
            "monitor employees;\n"
            "(b) the purposes for which information obtained through electronic monitoring "
            "may be used by the employer;\n"
            "(c) the date the policy was prepared and the date any changes were made to it.\n\n"
            "Section 41.1.1(5): The employer shall provide a copy of the written policy "
            "to each employee no later than 6 months after the policy is required or "
            "30 days after the employee's first day of employment, whichever is later.\n\n"
            "'Electronic monitoring' includes monitoring by means of a computer, phone, "
            "GPS device, or any other electronic device — including tracking location, "
            "monitoring internet/email use, or productivity tracking software.\n\n"
            "The policy does not prohibit electronic monitoring — it requires disclosure "
            "of monitoring practices. However, undisclosed monitoring may raise issues "
            "under the Ontario Privacy Act and the common law of privacy."
        ),
    },
]


def get_all_sections() -> List[Dict[str, str]]:
    return ESA_SECTIONS


def get_section_texts_for_ingestion() -> List[Dict[str, str]]:
    """Return sections formatted for the ingestion pipeline."""
    return [
        {
            "section_id": s["section_id"],
            "title": s["title"],
            "part": s["part"],
            "text": s["text"],
            "chunk_id": f"eao-act-{s['section_id'].replace('.', '-').replace(' ', '-').lower()}",
        }
        for s in ESA_SECTIONS
    ]
