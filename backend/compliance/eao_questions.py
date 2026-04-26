"""
Employment Standards Act of Ontario (ESA) — Comprehensive Compliance Question Bank.

All questions are grounded in the Employment Standards Act, 2000 (S.O. 2000, c. 41)
with specific section references.

Questions are classified as:
  always_applicable: True  — checked against every employment contract
  always_applicable: False — only checked when contract signals relevance
                             (applicability_note describes the trigger)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class SubCriterion:
    id: str
    description: str
    keywords: List[str]
    esa_section: str = ""


@dataclass
class ESAComplianceQuestion:
    id: str                      # e.g. "ESA-TERM-01"
    title: str
    esa_parts: List[str]         # e.g. ["Part XV", "Part XVI"]
    esa_sections: List[str]      # e.g. ["s.54", "s.57"]
    full_text: str               # the compliance question to answer
    sub_criteria: List[SubCriterion]
    likely_sections: List[str]   # contract section name hints
    always_applicable: bool
    applicability_note: str      # when this question is triggered


# Alias for backward-compat imports
ComplianceQuestion = ESAComplianceQuestion


ESA_COMPLIANCE_QUESTIONS: List[ESAComplianceQuestion] = [

    # ─────────────────────────────────────────────────────────────────────────
    # DOMAIN: CONTRACT BASICS
    # ─────────────────────────────────────────────────────────────────────────

    ESAComplianceQuestion(
        id="ESA-BASIC-01",
        title="Prohibition on Contracting Out of ESA (s.5)",
        esa_parts=["Part I"],
        esa_sections=["s.5"],
        full_text=(
            "Under ESA s.5(1), no employer or employee may contract out of or waive any "
            "employment standard — any such attempt is void. Does the employment contract "
            "contain any clause that explicitly waives ESA rights, purports to limit "
            "entitlements below the ESA minimum, or includes language such as 'common law "
            "only' that could exclude statutory protections? Any termination clause that "
            "caps pay-in-lieu below the s.57 notice schedule is void by s.5."
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-BASIC-01-SC1",
                description="No explicit waiver of ESA rights or minimum standards",
                keywords=["waive", "waiver", "forego", "relinquish", "common law only"],
                esa_section="s.5(1)",
            ),
            SubCriterion(
                id="ESA-BASIC-01-SC2",
                description="Termination provisions do not cap liability below ESA minimums",
                keywords=["termination", "notice", "severance", "maximum", "cap", "limit"],
                esa_section="s.5(1), s.57",
            ),
            SubCriterion(
                id="ESA-BASIC-01-SC3",
                description="No clause that removes or limits statutory leave entitlements",
                keywords=["leave", "entitlement", "waive leave", "forfeit", "not entitled"],
                esa_section="s.5(1), Part XIV",
            ),
        ],
        likely_sections=[
            "General Provisions", "Entire Agreement", "Governing Law", "Termination",
            "Notice", "Severance", "Acknowledgement", "Representations",
        ],
        always_applicable=True,
        applicability_note="Always applicable — every employment contract is subject to s.5.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # DOMAIN: HOURS OF WORK
    # ─────────────────────────────────────────────────────────────────────────

    ESAComplianceQuestion(
        id="ESA-HOURS-01",
        title="Maximum Hours of Work — Daily and Weekly Limits (s.17)",
        esa_parts=["Part VII"],
        esa_sections=["s.17"],
        full_text=(
            "ESA s.17(1) limits work to 8 hours per day (or a greater established regular "
            "work day) and s.17(2) limits work to 48 hours per week. Exceeding these limits "
            "requires a written excess-hours agreement between employer and employee (s.17(3)). "
            "Does the contract's hours-of-work provisions comply with these limits? Does the "
            "contract require, permit, or contemplate hours that exceed the ESA daily or weekly "
            "maximum without an excess-hours agreement?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-HOURS-01-SC1",
                description="Contract does not require more than 8 hours/day without agreement",
                keywords=["hours per day", "daily hours", "8 hours", "work day", "shift"],
                esa_section="s.17(1)",
            ),
            SubCriterion(
                id="ESA-HOURS-01-SC2",
                description="Contract does not require more than 48 hours/week without agreement",
                keywords=["hours per week", "weekly hours", "48 hours", "work week"],
                esa_section="s.17(2)",
            ),
            SubCriterion(
                id="ESA-HOURS-01-SC3",
                description="Excess hours agreement present if contract contemplates >8/day or >48/week",
                keywords=["excess hours", "overtime hours", "extended hours", "written agreement"],
                esa_section="s.17(3)",
            ),
        ],
        likely_sections=[
            "Hours of Work", "Working Hours", "Schedule", "Duties", "Work Week",
            "Employment Terms", "Compensation", "Time and Attendance",
        ],
        always_applicable=True,
        applicability_note="Always applicable — applies to all employees covered by ESA.",
    ),

    ESAComplianceQuestion(
        id="ESA-HOURS-02",
        title="Eating Periods / Meal Breaks (s.18)",
        esa_parts=["Part VII"],
        esa_sections=["s.18"],
        full_text=(
            "ESA s.18(1) requires employers to provide an eating period of at least 30 minutes "
            "at intervals that ensure no employee works more than 5 consecutive hours without "
            "an eating period. The eating period is unpaid unless the employer requires the "
            "employee to remain available for work during it. Does the contract address meal "
            "breaks in compliance with s.18, or does it include any clause that eliminates or "
            "reduces the employee's entitlement to meal breaks?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-HOURS-02-SC1",
                description="At least 30 minutes eating period provided after every 5 consecutive hours",
                keywords=["meal break", "lunch break", "eating period", "30 minutes", "5 hours"],
                esa_section="s.18(1)",
            ),
            SubCriterion(
                id="ESA-HOURS-02-SC2",
                description="No clause eliminating or reducing the eating period below 30 minutes",
                keywords=["no break", "waive break", "forfeit break", "shorter break"],
                esa_section="s.18(1)",
            ),
        ],
        likely_sections=[
            "Hours of Work", "Meal Breaks", "Rest Breaks", "Schedule", "Break Policy",
            "Work Terms",
        ],
        always_applicable=True,
        applicability_note="Always applicable — mandatory minimum for all employees.",
    ),

    ESAComplianceQuestion(
        id="ESA-HOURS-03",
        title="Rest Periods Between Shifts and Weekly Rest (s.19–s.20)",
        esa_parts=["Part VII"],
        esa_sections=["s.19", "s.20"],
        full_text=(
            "ESA s.19(1) requires at least 11 consecutive hours free from work between shifts. "
            "ESA s.20(1) requires at least 24 consecutive hours free from work in each work week. "
            "Does the contract address rest periods between shifts and weekly rest requirements? "
            "Does the contract contemplate scheduling practices that would deny these minimum "
            "rest periods without lawful exceptions?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-HOURS-03-SC1",
                description="At least 11 consecutive hours off between shifts (s.19)",
                keywords=["hours between shifts", "rest period", "11 hours", "consecutive hours off"],
                esa_section="s.19(1)",
            ),
            SubCriterion(
                id="ESA-HOURS-03-SC2",
                description="At least 24 consecutive hours off per work week (s.20)",
                keywords=["day off", "weekly rest", "24 hours", "consecutive hours", "rest day"],
                esa_section="s.20(1)",
            ),
        ],
        likely_sections=[
            "Hours of Work", "Scheduling", "Rest Periods", "Shift Work", "Work Schedule",
        ],
        always_applicable=True,
        applicability_note="Always applicable — mandatory minimums for all employees.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # DOMAIN: PAY
    # ─────────────────────────────────────────────────────────────────────────

    ESAComplianceQuestion(
        id="ESA-PAY-01",
        title="Minimum Wage Compliance (Part IX, s.23)",
        esa_parts=["Part IX"],
        esa_sections=["s.23", "s.23.1"],
        full_text=(
            "ESA Part IX (s.23) requires employers to pay at least the applicable Ontario "
            "minimum wage. The general minimum wage is set by regulation (as of October 2024, "
            "$17.20/hour; student rate $16.20/hour). No deductions, fees, or repayment "
            "obligations may reduce the effective hourly rate below minimum wage. Does the "
            "compensation in the contract meet or exceed the applicable Ontario minimum wage? "
            "Are there any deductions or repayment clauses that could bring effective pay below "
            "minimum wage?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-PAY-01-SC1",
                description="Rate of pay meets or exceeds applicable Ontario minimum wage",
                keywords=["hourly rate", "wage", "pay", "salary", "compensation", "minimum wage"],
                esa_section="s.23(1)",
            ),
            SubCriterion(
                id="ESA-PAY-01-SC2",
                description="No deductions or repayment clauses that reduce net pay below minimum wage",
                keywords=["deduction", "repayment", "clawback", "training repayment", "uniform cost"],
                esa_section="s.23, s.12",
            ),
            SubCriterion(
                id="ESA-PAY-01-SC3",
                description="Method and frequency of pay stated (s.11 — pay periods required)",
                keywords=["pay period", "bi-weekly", "semi-monthly", "monthly pay", "payment frequency"],
                esa_section="s.11",
            ),
        ],
        likely_sections=[
            "Compensation", "Salary", "Wages", "Pay", "Remuneration",
            "Benefits and Compensation", "Employment Terms",
        ],
        always_applicable=True,
        applicability_note="Always applicable — every employment contract must meet minimum wage.",
    ),

    ESAComplianceQuestion(
        id="ESA-PAY-02",
        title="Overtime Pay (Part VIII, s.22)",
        esa_parts=["Part VIII"],
        esa_sections=["s.22", "s.22.1"],
        full_text=(
            "ESA s.22(1) requires employers to pay overtime at a rate of at least 1.5 times "
            "the employee's regular rate for each hour worked over 44 hours in a work week. "
            "Overtime averaging agreements are permitted under s.22.1 but must be in writing "
            "and signed. Certain employees are exempt from overtime (e.g., managers, supervisors, "
            "IT professionals under O. Reg. 285/01). Does the contract address overtime pay "
            "at the correct rate? Does it attempt to eliminate overtime entitlement for a "
            "non-exempt employee? Is any overtime averaging agreement properly documented?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-PAY-02-SC1",
                description="Overtime rate is at least 1.5× regular rate for hours over 44/week",
                keywords=["overtime", "1.5x", "time and a half", "overtime rate", "44 hours"],
                esa_section="s.22(1)",
            ),
            SubCriterion(
                id="ESA-PAY-02-SC2",
                description="Overtime threshold correctly stated as 44 hours per week",
                keywords=["overtime threshold", "44 hours", "overtime hours", "overtime eligibility"],
                esa_section="s.22(1)",
            ),
            SubCriterion(
                id="ESA-PAY-02-SC3",
                description="No elimination of overtime for employees who are not ESA-exempt",
                keywords=["no overtime", "exempt", "all-in salary", "salary includes overtime"],
                esa_section="s.22, O.Reg. 285/01",
            ),
            SubCriterion(
                id="ESA-PAY-02-SC4",
                description="Overtime averaging agreement in writing and signed (if used)",
                keywords=["overtime averaging", "averaging agreement", "averaged over", "bi-weekly averaging"],
                esa_section="s.22.1",
            ),
        ],
        likely_sections=[
            "Overtime", "Compensation", "Hours of Work", "Pay", "Salary",
            "Employment Terms", "Working Hours",
        ],
        always_applicable=True,
        applicability_note="Always applicable — check for overtime exclusion or incorrect rate.",
    ),

    ESAComplianceQuestion(
        id="ESA-PAY-03",
        title="Public Holiday Entitlements (Part X, s.26–s.32)",
        esa_parts=["Part X"],
        esa_sections=["s.26", "s.27", "s.28", "s.29", "s.30", "s.31"],
        full_text=(
            "ESA Part X entitles eligible employees to 9 Ontario public holidays off with public "
            "holiday pay. If an employee is required to work on a public holiday, they are "
            "entitled to either (a) public holiday pay plus premium pay (1.5×) for hours worked, "
            "or (b) regular wages for hours worked on the holiday plus a substitute day off with "
            "public holiday pay. Public holiday pay equals the employee's regular wages earned "
            "in the 4 weeks before the holiday divided by 20. Does the contract address public "
            "holidays in compliance with Part X? Are there any clauses that attempt to eliminate "
            "or reduce the statutory holiday entitlement?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-PAY-03-SC1",
                description="Entitlement to 9 public holidays off with public holiday pay",
                keywords=["public holiday", "statutory holiday", "holiday pay", "paid holiday"],
                esa_section="s.26, s.27",
            ),
            SubCriterion(
                id="ESA-PAY-03-SC2",
                description="Premium pay (1.5×) or substitute day when required to work on a public holiday",
                keywords=["premium pay", "work on holiday", "holiday worked", "substitute day"],
                esa_section="s.29, s.31",
            ),
            SubCriterion(
                id="ESA-PAY-03-SC3",
                description="No clause reducing or eliminating statutory holiday entitlement",
                keywords=["no holiday pay", "holiday excluded", "waive holiday", "holiday forfeit"],
                esa_section="s.26, s.5",
            ),
        ],
        likely_sections=[
            "Public Holidays", "Statutory Holidays", "Holidays", "Time Off",
            "Compensation", "Benefits", "Leave",
        ],
        always_applicable=True,
        applicability_note="Always applicable — all employees (with qualifying period) are entitled.",
    ),

    ESAComplianceQuestion(
        id="ESA-PAY-04",
        title="Equal Pay for Equal Work — Sex (Part XII, s.42)",
        esa_parts=["Part XII"],
        esa_sections=["s.42", "s.43"],
        full_text=(
            "ESA s.42(1) prohibits employers from paying an employee of one sex less than "
            "an employee of the other sex when they perform substantially the same kind of "
            "work in the same establishment, where the performance of the work requires "
            "substantially the same skill, effort, and responsibility, and the work is "
            "performed under similar working conditions. Differences in pay are permitted "
            "only if based on a seniority system, merit system, piece-rate system, or any "
            "factor other than sex (s.43). Does the contract include any compensation "
            "provisions that could create or reflect a sex-based pay differential?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-PAY-04-SC1",
                description="No sex-based differential in pay for substantially similar work",
                keywords=["equal pay", "sex", "gender", "male", "female", "pay equity", "same pay"],
                esa_section="s.42(1)",
            ),
            SubCriterion(
                id="ESA-PAY-04-SC2",
                description="Any pay differential is based only on seniority, merit, or piece-rate — not sex",
                keywords=["seniority", "merit", "piece-rate", "pay difference", "compensation differential"],
                esa_section="s.43",
            ),
        ],
        likely_sections=[
            "Compensation", "Salary", "Pay Equity", "Equal Pay", "Wages", "Benefits",
        ],
        always_applicable=True,
        applicability_note="Always applicable — sex-based pay discrimination is prohibited.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # DOMAIN: VACATION
    # ─────────────────────────────────────────────────────────────────────────

    ESAComplianceQuestion(
        id="ESA-VAC-01",
        title="Vacation Time Entitlement (Part XI, s.33)",
        esa_parts=["Part XI"],
        esa_sections=["s.33", "s.34", "s.35"],
        full_text=(
            "ESA s.33 entitles employees to vacation time of at least 2 weeks after each "
            "12-month vacation entitlement year (s.33(2)). After 5 or more years of employment "
            "with the same employer, the entitlement increases to at least 3 weeks (s.33(3)). "
            "The employer must schedule and grant all vacation time. Does the contract provide "
            "vacation time entitlements that meet or exceed these minimums? Does the contract "
            "include any provisions that reduce vacation time below the ESA minimum or that "
            "allow vacation time to be forfeited?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-VAC-01-SC1",
                description="Minimum 2 weeks vacation time per vacation entitlement year",
                keywords=["vacation", "holiday", "annual leave", "2 weeks", "10 days", "vacation time"],
                esa_section="s.33(2)",
            ),
            SubCriterion(
                id="ESA-VAC-01-SC2",
                description="Minimum 3 weeks vacation after 5 years of employment",
                keywords=["3 weeks", "15 days", "five years", "5 years", "vacation entitlement"],
                esa_section="s.33(3)",
            ),
            SubCriterion(
                id="ESA-VAC-01-SC3",
                description="No provision forfeiting or reducing vacation below ESA minimum",
                keywords=["forfeit vacation", "vacation unused", "use-it-or-lose-it", "vacation cap"],
                esa_section="s.33, s.5",
            ),
        ],
        likely_sections=[
            "Vacation", "Annual Leave", "Time Off", "Paid Leave", "Holidays", "Benefits",
        ],
        always_applicable=True,
        applicability_note="Always applicable — all employees with 12+ months are entitled.",
    ),

    ESAComplianceQuestion(
        id="ESA-VAC-02",
        title="Vacation Pay (Part XI, s.35.2)",
        esa_parts=["Part XI"],
        esa_sections=["s.35.2", "s.41"],
        full_text=(
            "ESA s.35.2 requires vacation pay equal to at least 4% of wages (excluding "
            "vacation pay) earned in the entitlement period for employees with fewer than "
            "5 years of service. For employees with 5 or more years of service, the rate "
            "is at least 6% (s.35.2(2)). On termination, any outstanding vacation pay "
            "must be paid out (s.41). Does the contract state a vacation pay rate that "
            "meets or exceeds the applicable ESA percentage? Is the vacation pay correctly "
            "calculated on all eligible wages?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-VAC-02-SC1",
                description="Vacation pay rate is at least 4% of wages",
                keywords=["4%", "vacation pay", "vacation percentage", "four percent"],
                esa_section="s.35.2(1)",
            ),
            SubCriterion(
                id="ESA-VAC-02-SC2",
                description="Vacation pay rate increases to at least 6% after 5 years",
                keywords=["6%", "six percent", "five years", "5 years", "vacation pay increase"],
                esa_section="s.35.2(2)",
            ),
            SubCriterion(
                id="ESA-VAC-02-SC3",
                description="Outstanding vacation pay paid out on termination",
                keywords=["vacation payout", "vacation on termination", "accrued vacation", "pay out vacation"],
                esa_section="s.41",
            ),
        ],
        likely_sections=[
            "Vacation Pay", "Vacation", "Compensation", "Termination", "Benefits",
        ],
        always_applicable=True,
        applicability_note="Always applicable — vacation pay is a mandatory ESA entitlement.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # DOMAIN: LEAVES OF ABSENCE
    # ─────────────────────────────────────────────────────────────────────────

    ESAComplianceQuestion(
        id="ESA-LEAVE-01",
        title="Pregnancy and Parental Leave (Part XIV, s.46–s.48)",
        esa_parts=["Part XIV"],
        esa_sections=["s.46", "s.47", "s.48", "s.53"],
        full_text=(
            "ESA s.46 entitles eligible employees to up to 17 weeks of job-protected "
            "pregnancy leave. ESA s.48 entitles employees to parental leave of up to "
            "61 weeks (birth parent) or 63 weeks (non-birth parent). Job reinstatement "
            "is required under s.53 — the employee must be reinstated to the same or a "
            "comparable position. Benefits continuation and seniority accumulation continue "
            "during leave (s.53.1). No employer may penalize an employee for taking leave. "
            "Does the contract acknowledge these rights? Does any contract term restrict, "
            "discourage, or place conditions on the exercise of pregnancy or parental leave?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-LEAVE-01-SC1",
                description="Pregnancy leave entitlement of up to 17 weeks acknowledged",
                keywords=["pregnancy leave", "maternity leave", "pregnancy", "17 weeks", "prenatal"],
                esa_section="s.46",
            ),
            SubCriterion(
                id="ESA-LEAVE-01-SC2",
                description="Parental leave entitlement of up to 61/63 weeks acknowledged",
                keywords=["parental leave", "paternity leave", "parent", "61 weeks", "63 weeks", "child"],
                esa_section="s.48",
            ),
            SubCriterion(
                id="ESA-LEAVE-01-SC3",
                description="Job reinstatement guaranteed upon return from leave",
                keywords=["return to work", "reinstatement", "same position", "comparable position"],
                esa_section="s.53",
            ),
            SubCriterion(
                id="ESA-LEAVE-01-SC4",
                description="No clause discouraging, penalizing, or conditioning leave entitlement",
                keywords=["penalize", "condition", "discourage", "restrict leave", "forfeit on leave"],
                esa_section="s.53.1, s.74",
            ),
        ],
        likely_sections=[
            "Leaves of Absence", "Maternity Leave", "Parental Leave", "Leave Policy",
            "Family Leave", "Benefits", "Employment Terms",
        ],
        always_applicable=True,
        applicability_note="Always applicable — fundamental employee right regardless of tenure.",
    ),

    ESAComplianceQuestion(
        id="ESA-LEAVE-02",
        title="Sick Leave (s.50.0.1)",
        esa_parts=["Part XIV"],
        esa_sections=["s.50.0.1"],
        full_text=(
            "ESA s.50.0.1 entitles employees who have been employed for at least 2 consecutive "
            "weeks to up to 3 days of unpaid sick leave per calendar year for personal illness, "
            "injury, or medical emergency. Job protection applies — no employer may penalize "
            "an employee for taking sick leave. Does the contract provide sick leave entitlement "
            "consistent with s.50.0.1? Does the contract include any sick-leave provisions that "
            "are more restrictive than the ESA minimum (e.g., fewer days, requiring medical "
            "notes for all instances, or tying sick leave to probationary periods)?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-LEAVE-02-SC1",
                description="At least 3 days unpaid sick leave per calendar year",
                keywords=["sick leave", "sick days", "illness leave", "personal illness", "3 days"],
                esa_section="s.50.0.1",
            ),
            SubCriterion(
                id="ESA-LEAVE-02-SC2",
                description="Job protection during sick leave — no penalization",
                keywords=["sick leave protection", "job protected", "disciplinary action", "sick day penalize"],
                esa_section="s.50.0.1(5), s.74",
            ),
        ],
        likely_sections=[
            "Sick Leave", "Leaves of Absence", "Absence Policy", "Medical Leave",
            "Leave Policy", "Benefits", "Time Off",
        ],
        always_applicable=True,
        applicability_note="Always applicable — all employees after 2 consecutive weeks are entitled.",
    ),

    ESAComplianceQuestion(
        id="ESA-LEAVE-03",
        title="Family Medical Leave (s.49)",
        esa_parts=["Part XIV"],
        esa_sections=["s.49"],
        full_text=(
            "ESA s.49 entitles eligible employees to up to 28 weeks of unpaid, job-protected "
            "family medical leave in a 52-week period to provide care to a family member with "
            "a serious medical condition with a significant risk of death within 26 weeks. "
            "The employee is entitled to reinstatement to the same or comparable position. "
            "Does the contract acknowledge family medical leave entitlement? Does any contract "
            "term restrict or eliminate this right?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-LEAVE-03-SC1",
                description="Up to 28 weeks unpaid family medical leave in a 52-week period",
                keywords=["family medical leave", "compassionate care", "serious illness", "28 weeks"],
                esa_section="s.49",
            ),
            SubCriterion(
                id="ESA-LEAVE-03-SC2",
                description="Job protection and reinstatement rights during family medical leave",
                keywords=["reinstatement", "job protection", "return from leave", "position held"],
                esa_section="s.49(9), s.53",
            ),
        ],
        likely_sections=[
            "Leaves of Absence", "Family Leave", "Medical Leave", "Leave Policy",
            "Employment Terms", "Compassionate Care",
        ],
        always_applicable=True,
        applicability_note="Always applicable — all employees are entitled to family medical leave.",
    ),

    ESAComplianceQuestion(
        id="ESA-LEAVE-04",
        title="Bereavement Leave (s.50.0.2)",
        esa_parts=["Part XIV"],
        esa_sections=["s.50.0.2"],
        full_text=(
            "ESA s.50.0.2 entitles employees who have been employed for at least 2 consecutive "
            "weeks to up to 2 days of unpaid bereavement leave upon the death of certain "
            "qualifying family members (as defined in the Act). Job protection applies. "
            "Does the contract provide bereavement leave consistent with s.50.0.2? Does the "
            "contract restrict bereavement leave below the ESA minimum (e.g., only 1 day, "
            "only for immediate family narrower than ESA's definition, or tied to "
            "probationary completion)?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-LEAVE-04-SC1",
                description="At least 2 days unpaid bereavement leave on death of qualifying family member",
                keywords=["bereavement", "death", "funeral", "bereavement leave", "mourning leave"],
                esa_section="s.50.0.2",
            ),
            SubCriterion(
                id="ESA-LEAVE-04-SC2",
                description="Qualifying family members not defined more narrowly than ESA",
                keywords=["family member", "immediate family", "qualifying relative", "next of kin"],
                esa_section="s.50.0.2(1)",
            ),
        ],
        likely_sections=[
            "Bereavement Leave", "Leaves of Absence", "Leave Policy", "Time Off",
            "Absence", "Personal Leave",
        ],
        always_applicable=True,
        applicability_note="Always applicable — all employees after 2 consecutive weeks are entitled.",
    ),

    ESAComplianceQuestion(
        id="ESA-LEAVE-05",
        title="Domestic or Sexual Violence Leave (s.49.7)",
        esa_parts=["Part XIV"],
        esa_sections=["s.49.7"],
        full_text=(
            "ESA s.49.7 entitles employees who have been employed for at least 13 consecutive "
            "weeks and who have experienced or whose child has experienced domestic or sexual "
            "violence to: (a) up to 10 days per calendar year — the first 5 days are paid at "
            "regular wages, the remaining 5 days are unpaid; and (b) up to 15 additional weeks "
            "per calendar year (unpaid). Job protection and confidentiality obligations apply. "
            "Does the contract acknowledge this leave? Are there any provisions that could "
            "penalize or identify employees exercising this leave?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-LEAVE-05-SC1",
                description="Up to 10 days per year (first 5 paid, last 5 unpaid) for domestic/sexual violence",
                keywords=["domestic violence", "sexual violence", "gender-based violence", "10 days"],
                esa_section="s.49.7(2)",
            ),
            SubCriterion(
                id="ESA-LEAVE-05-SC2",
                description="Up to 15 additional weeks unpaid leave available",
                keywords=["domestic violence leave", "15 weeks", "extended leave", "violence leave"],
                esa_section="s.49.7(3)",
            ),
            SubCriterion(
                id="ESA-LEAVE-05-SC3",
                description="Confidentiality maintained — employer cannot require disclosure of reasons",
                keywords=["confidentiality", "disclosure", "reason for leave", "private", "personal"],
                esa_section="s.49.7(7)",
            ),
        ],
        likely_sections=[
            "Leaves of Absence", "Leave Policy", "Domestic Violence", "Personal Leave",
            "Time Off", "Employment Terms",
        ],
        always_applicable=True,
        applicability_note="Always applicable — fundamental job-protected leave right.",
    ),

    ESAComplianceQuestion(
        id="ESA-LEAVE-06",
        title="Family Caregiver Leave (s.49.5)",
        esa_parts=["Part XIV"],
        esa_sections=["s.49.5"],
        full_text=(
            "ESA s.49.5 entitles eligible employees to up to 8 weeks of unpaid, job-protected "
            "family caregiver leave per calendar year for each qualifying family member who "
            "has a serious medical condition (up to 8 different qualifying family members). "
            "Job reinstatement and benefit continuation provisions apply (s.53, s.53.1). "
            "Does the contract acknowledge family caregiver leave? Does any contract term "
            "restrict or condition this entitlement below the ESA minimum?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-LEAVE-06-SC1",
                description="Up to 8 weeks unpaid family caregiver leave per qualifying family member",
                keywords=["caregiver leave", "family caregiver", "care leave", "8 weeks", "dependent"],
                esa_section="s.49.5",
            ),
            SubCriterion(
                id="ESA-LEAVE-06-SC2",
                description="Job protection and reinstatement upon return from caregiver leave",
                keywords=["reinstatement", "job protection", "return to work", "caregiver reinstatement"],
                esa_section="s.49.5(9), s.53",
            ),
        ],
        likely_sections=[
            "Leaves of Absence", "Family Leave", "Caregiver Leave", "Leave Policy",
            "Employment Terms",
        ],
        always_applicable=True,
        applicability_note="Always applicable — available to all eligible employees.",
    ),

    ESAComplianceQuestion(
        id="ESA-LEAVE-07",
        title="Critical Illness Leave — Child and Adult (s.49.1, s.49.6)",
        esa_parts=["Part XIV"],
        esa_sections=["s.49.1", "s.49.6"],
        full_text=(
            "ESA s.49.1 provides up to 37 weeks of unpaid, job-protected critical illness leave "
            "to care for a critically ill child. ESA s.49.6 provides up to 16 weeks to care for "
            "a critically ill adult family member. Both require a certificate from a qualified "
            "health practitioner. Does the contract acknowledge critical illness leave? Does any "
            "provision restrict or reduce the entitlement below the ESA minimum?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-LEAVE-07-SC1",
                description="Up to 37 weeks to care for a critically ill child",
                keywords=["critically ill child", "critical illness", "child illness leave", "37 weeks"],
                esa_section="s.49.1",
            ),
            SubCriterion(
                id="ESA-LEAVE-07-SC2",
                description="Up to 16 weeks to care for a critically ill adult",
                keywords=["critically ill adult", "adult critical illness", "16 weeks", "critical care"],
                esa_section="s.49.6",
            ),
        ],
        likely_sections=[
            "Leaves of Absence", "Critical Illness Leave", "Medical Leave", "Leave Policy",
        ],
        always_applicable=True,
        applicability_note="Always applicable — available to eligible employees caring for critically ill family.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # DOMAIN: TERMINATION
    # ─────────────────────────────────────────────────────────────────────────

    ESAComplianceQuestion(
        id="ESA-TERM-01",
        title="Termination Notice Requirements (Part XV, s.54–s.57)",
        esa_parts=["Part XV"],
        esa_sections=["s.54", "s.55", "s.56", "s.57", "s.58", "s.61"],
        full_text=(
            "ESA Part XV requires employers to give written notice of termination based on "
            "length of service (s.57): fewer than 1 year = 1 week; 1–<3 years = 2 weeks; "
            "3–<4 years = 3 weeks; 4–<5 years = 4 weeks; 5–<6 years = 5 weeks; 6–<7 years = "
            "6 weeks; 7–<8 years = 7 weeks; 8+ years = 8 weeks. Pay in lieu of notice is "
            "permitted (s.60). Termination pay must be paid within 7 days of last day worked "
            "or next regular pay date (s.61). No notice is required for the first 3 months of "
            "employment (s.54(1)(b)). Does the contract's termination notice provision meet "
            "or exceed the ESA schedule? Is any attempt made to limit notice below ESA minimums?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-TERM-01-SC1",
                description="Termination notice schedule meets or exceeds ESA s.57 minimums",
                keywords=["notice period", "termination notice", "weeks notice", "notice of termination"],
                esa_section="s.57",
            ),
            SubCriterion(
                id="ESA-TERM-01-SC2",
                description="Pay in lieu of notice option acknowledged at full ESA entitlement",
                keywords=["pay in lieu", "termination pay", "notice pay", "pay instead of notice"],
                esa_section="s.60",
            ),
            SubCriterion(
                id="ESA-TERM-01-SC3",
                description="No clause capping, limiting, or waiving termination notice below ESA",
                keywords=["maximum notice", "capped at", "no more than", "waive notice", "only notice"],
                esa_section="s.5, s.57",
            ),
            SubCriterion(
                id="ESA-TERM-01-SC4",
                description="Probationary exclusion (if any) limited to first 3 months of employment",
                keywords=["probation", "probationary period", "3 months", "first 90 days"],
                esa_section="s.54(1)(b)",
            ),
        ],
        likely_sections=[
            "Termination", "Notice of Termination", "Termination of Employment",
            "Employment Period", "Resignation", "Dismissal", "End of Employment",
        ],
        always_applicable=True,
        applicability_note="Always applicable — every employment relationship subject to Part XV.",
    ),

    ESAComplianceQuestion(
        id="ESA-TERM-02",
        title="Severance Pay (Part XVI, s.63–s.64)",
        esa_parts=["Part XVI"],
        esa_sections=["s.63", "s.64", "s.65"],
        full_text=(
            "ESA s.63 entitles employees to severance pay if they have 5 or more years of "
            "service AND the employer's Ontario payroll is $2.5 million or more, OR the "
            "termination is part of a mass termination of 50 or more employees in a "
            "6-month period. Severance pay under s.64 equals 1 regular week's wages per "
            "completed year of service, plus a prorated amount for any part year, up to a "
            "maximum of 26 weeks. Severance pay is in addition to termination pay under "
            "Part XV. Does the contract address severance pay obligations consistent with "
            "Part XVI? Is there any attempt to contract out of or limit severance entitlement?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-TERM-02-SC1",
                description="Severance pay formula meets ESA (1 week per year, max 26 weeks)",
                keywords=["severance", "severance pay", "one week per year", "26 weeks maximum"],
                esa_section="s.64",
            ),
            SubCriterion(
                id="ESA-TERM-02-SC2",
                description="Severance correctly stated as additional to termination pay — not merged",
                keywords=["severance additional", "separate from notice", "in addition to", "plus severance"],
                esa_section="s.64, s.57",
            ),
            SubCriterion(
                id="ESA-TERM-02-SC3",
                description="No clause waiving, capping, or reducing severance below ESA entitlement",
                keywords=["waive severance", "no severance", "cap severance", "limit severance"],
                esa_section="s.5, s.63",
            ),
        ],
        likely_sections=[
            "Severance", "Termination", "Severance Pay", "End of Employment",
            "Compensation on Termination", "Separation",
        ],
        always_applicable=True,
        applicability_note="Always applicable — check for unlawful severance cap or waiver.",
    ),

    ESAComplianceQuestion(
        id="ESA-TERM-03",
        title="Termination for Cause — ESA Wilful Misconduct Standard (s.54(1)(c))",
        esa_parts=["Part XV"],
        esa_sections=["s.54(1)(c)", "s.63(1)(c)"],
        full_text=(
            "ESA s.54(1)(c) and s.63(1)(c) allow employers to terminate without notice or "
            "severance only when the employee is guilty of 'wilful misconduct, disobedience "
            "or wilful neglect of duty that is not trivial and has not been condoned by the "
            "employer.' This is a higher and stricter standard than common law just cause. "
            "Performance-related issues or non-wilful conduct generally do not meet this "
            "standard. Does any 'for cause' or 'just cause' termination clause in the contract "
            "comply with the ESA standard? Does the contract attempt to dismiss without ESA "
            "entitlements for conduct that does not meet the wilful misconduct threshold?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-TERM-03-SC1",
                description="Cause definition consistent with ESA 'wilful misconduct' standard",
                keywords=["just cause", "for cause", "cause", "misconduct", "wilful", "disobedience"],
                esa_section="s.54(1)(c)",
            ),
            SubCriterion(
                id="ESA-TERM-03-SC2",
                description="No zero-notice termination for performance issues below wilful misconduct",
                keywords=["performance", "performance issue", "poor performance", "cause termination"],
                esa_section="s.54(1)(c)",
            ),
            SubCriterion(
                id="ESA-TERM-03-SC3",
                description="Cause clause does not purport to deny ESA entitlements for common law cause",
                keywords=["common law cause", "deny severance", "without payment", "no entitlements"],
                esa_section="s.5, s.54(1)(c)",
            ),
        ],
        likely_sections=[
            "Termination for Cause", "Just Cause", "Termination", "Misconduct",
            "Grounds for Termination", "Disciplinary Provisions",
        ],
        always_applicable=True,
        applicability_note="Always applicable — must check that cause standard meets ESA.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # DOMAIN: EMPLOYEE RIGHTS & PROTECTIONS
    # ─────────────────────────────────────────────────────────────────────────

    ESAComplianceQuestion(
        id="ESA-REPRISAL-01",
        title="Anti-Reprisal Provisions (s.74)",
        esa_parts=["Part XVII"],
        esa_sections=["s.74"],
        full_text=(
            "ESA s.74 prohibits employers from intimidating, dismissing, penalizing, or "
            "threatening any employee for exercising or attempting to exercise a right under "
            "the ESA — including asking about ESA entitlements, filing a complaint, taking "
            "leave, or refusing to work illegal hours. Does the contract include any clause "
            "that could be interpreted as penalizing an employee for exercising ESA rights? "
            "Examples include 'at-will' termination language that could chill ESA complaints, "
            "contractual clauses that reduce benefits if an employee takes statutory leave, or "
            "non-disclosure agreements that prevent employees from reporting ESA violations."
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-REPRISAL-01-SC1",
                description="No clause penalizing or threatening employees for exercising ESA rights",
                keywords=["reprisal", "penalize", "retaliate", "threaten", "intimidate", "dismiss for complaint"],
                esa_section="s.74",
            ),
            SubCriterion(
                id="ESA-REPRISAL-01-SC2",
                description="No NDA or confidentiality clause preventing ESA complaint or reporting",
                keywords=["non-disclosure", "NDA", "confidentiality", "complaint", "report", "silence clause"],
                esa_section="s.74",
            ),
            SubCriterion(
                id="ESA-REPRISAL-01-SC3",
                description="No reduction in benefits or compensation tied to taking statutory leave",
                keywords=["benefit reduction", "compensation reduction", "leave penalty", "on leave benefits"],
                esa_section="s.74, s.53.1",
            ),
        ],
        likely_sections=[
            "Anti-Retaliation", "Non-Retaliation", "Employee Rights", "Confidentiality",
            "Termination", "General Provisions", "Workplace Conduct",
        ],
        always_applicable=True,
        applicability_note="Always applicable — s.74 protection is fundamental to ESA enforcement.",
    ),

    ESAComplianceQuestion(
        id="ESA-CLASS-01",
        title="Employee Misclassification (Part XVIII.1, s.83.2)",
        esa_parts=["Part XVIII.1"],
        esa_sections=["s.83.2"],
        full_text=(
            "ESA s.83.2(1) prohibits employers from treating employees as independent "
            "contractors when the nature of the work relationship is that of employment. "
            "Under s.83.2(2), if an employer disputes that a worker is an employee, the "
            "burden of proof is on the employer. Key factors include: degree of control, "
            "ownership of tools, chance of profit/risk of loss, and integration into the "
            "employer's business. Does the contract's classification of the relationship "
            "(employee vs. contractor) reflect the true economic and legal nature of the "
            "relationship? Are there any 'sham contractor' clauses that attempt to deny "
            "employee status and ESA protections to what is in substance an employment relationship?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-CLASS-01-SC1",
                description="Relationship correctly classified as employment where substance warrants it",
                keywords=["employee", "contractor", "independent contractor", "self-employed", "classification"],
                esa_section="s.83.2",
            ),
            SubCriterion(
                id="ESA-CLASS-01-SC2",
                description="No sham contractor clause purporting to deny employee ESA rights",
                keywords=["not an employee", "no employee status", "independent", "sole responsibility"],
                esa_section="s.83.2(1)",
            ),
            SubCriterion(
                id="ESA-CLASS-01-SC3",
                description="If classified as contractor, genuine indicia of independent business present",
                keywords=["invoice", "GST/HST", "own equipment", "multiple clients", "set own hours"],
                esa_section="s.83.2(2)",
            ),
        ],
        likely_sections=[
            "Nature of Relationship", "Independent Contractor", "Employment Classification",
            "Engagement", "Services Agreement", "General Provisions",
        ],
        always_applicable=True,
        applicability_note="Always applicable — misclassification nullifies all ESA protections.",
    ),

    # ─────────────────────────────────────────────────────────────────────────
    # DOMAIN: CONDITIONAL QUESTIONS
    # ─────────────────────────────────────────────────────────────────────────

    ESAComplianceQuestion(
        id="ESA-HOURS-05",
        title="Right to Disconnect Policy (s.21.1.1) [Conditional]",
        esa_parts=["Part VII"],
        esa_sections=["s.21.1.1"],
        full_text=(
            "ESA s.21.1.1 requires employers with 25 or more employees as of January 1 of "
            "any year to have a written 'right to disconnect' policy describing the employer's "
            "expectations around being contacted outside of scheduled work hours. The policy "
            "must be provided to each employee. Does the contract create expectations or "
            "obligations for the employee to be available or responsive outside of regular "
            "working hours? If the employer has 25+ employees, is a right to disconnect "
            "policy referenced, provided, or acknowledged in the contract?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-HOURS-05-SC1",
                description="Right to disconnect policy exists and is referenced for employers with 25+ employees",
                keywords=["right to disconnect", "after hours", "off hours", "availability policy", "disconnecting"],
                esa_section="s.21.1.1",
            ),
            SubCriterion(
                id="ESA-HOURS-05-SC2",
                description="Contract does not impose uncompensated mandatory after-hours availability",
                keywords=["available at all times", "24/7", "on call", "after hours response", "immediate response"],
                esa_section="s.21.1.1, s.17",
            ),
        ],
        likely_sections=[
            "Hours of Work", "Availability", "Work Schedule", "Right to Disconnect",
            "Remote Work", "Communication Policy", "Employee Obligations",
        ],
        always_applicable=False,
        applicability_note=(
            "Applicable if: (1) employer has or is likely to have 25+ employees, "
            "(2) contract mentions after-hours availability, on-call expectations, "
            "or responsiveness to communications outside work hours."
        ),
    ),

    ESAComplianceQuestion(
        id="ESA-PAY-05",
        title="Equal Pay by Employment Status — Full-Time vs. Part-Time (s.42.1) [Conditional]",
        esa_parts=["Part XII"],
        esa_sections=["s.42.1", "s.43.1"],
        full_text=(
            "ESA s.42.1 prohibits employers from paying a part-time, casual, temporary, or "
            "seasonal employee at a rate of pay less than a full-time employee for "
            "performing substantially the same kind of work in the same establishment, "
            "with the same level of skill, effort, and responsibility, under similar "
            "working conditions. Pay differences are permitted only if based on a seniority "
            "system, merit system, piece-rate system, or a factor other than employment "
            "status (s.43.1). Does the contract include any employment-status-based pay "
            "differential that may violate s.42.1?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-PAY-05-SC1",
                description="No pay differential based solely on employment status (FT vs PT)",
                keywords=["part-time rate", "full-time rate", "part-time pay", "status-based pay"],
                esa_section="s.42.1",
            ),
            SubCriterion(
                id="ESA-PAY-05-SC2",
                description="Any pay differential based on seniority, merit, or piece-rate — not status alone",
                keywords=["seniority-based", "merit-based", "same rate", "pro-rata"],
                esa_section="s.43.1",
            ),
        ],
        likely_sections=[
            "Compensation", "Part-Time Terms", "Casual Employment", "Pay Rate",
            "Equal Pay", "Employment Type",
        ],
        always_applicable=False,
        applicability_note=(
            "Applicable if: contract mentions part-time, casual, temporary, or "
            "seasonal employment, or distinguishes pay rates based on employment status."
        ),
    ),

    ESAComplianceQuestion(
        id="ESA-BENEFIT-01",
        title="Benefit Plan Non-Discrimination (Part XIII, s.44) [Conditional]",
        esa_parts=["Part XIII"],
        esa_sections=["s.44"],
        full_text=(
            "ESA s.44 prohibits distinctions in group life insurance, accidental death "
            "insurance, disability insurance, health benefits plans, or pension plans "
            "based on sex, marital status, or same-sex partnership status. Does the "
            "contract or any referenced benefits plan include discriminatory provisions "
            "in group insurance or pension benefits? Are benefit entitlements identical "
            "for employees of all sexes and marital statuses in substantially similar roles?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-BENEFIT-01-SC1",
                description="No sex-based distinction in group insurance or pension benefits",
                keywords=["benefits", "group insurance", "pension", "sex discrimination", "equal benefits"],
                esa_section="s.44(1)",
            ),
            SubCriterion(
                id="ESA-BENEFIT-01-SC2",
                description="No marital status distinction in group insurance or pension benefits",
                keywords=["marital status", "married", "single", "common-law", "same-sex"],
                esa_section="s.44(1)",
            ),
        ],
        likely_sections=[
            "Benefits", "Group Insurance", "Pension", "Health Benefits", "Benefit Plan",
            "Group Life Insurance", "Employee Benefits",
        ],
        always_applicable=False,
        applicability_note=(
            "Applicable if: contract mentions group insurance, health benefits, "
            "or pension plan entitlements."
        ),
    ),

    ESAComplianceQuestion(
        id="ESA-CLASS-02",
        title="Probationary Period — ESA Termination Rights (s.54(1)(b)) [Conditional]",
        esa_parts=["Part XV"],
        esa_sections=["s.54(1)(b)"],
        full_text=(
            "ESA s.54(1)(b) excludes employees from termination notice requirements for the "
            "first 3 months of 'continuous employment'. Once an employee passes the 3-month "
            "mark, ESA termination entitlements fully apply regardless of any 'probationary' "
            "label in the contract. A contract may not extend a 'probationary period' beyond "
            "3 months to deny ESA termination rights. Does the contract include a probationary "
            "period? If so, is it used correctly (i.e., limited to 3 months for the ESA "
            "termination exclusion)? Does the contract attempt to deny ESA termination rights "
            "during or after a probationary period beyond 3 months?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-CLASS-02-SC1",
                description="Probationary period not used to extend ESA notice exclusion beyond 3 months",
                keywords=["probation", "probationary period", "trial period", "3 months", "90 days"],
                esa_section="s.54(1)(b)",
            ),
            SubCriterion(
                id="ESA-CLASS-02-SC2",
                description="ESA termination rights apply in full once 3-month mark is reached",
                keywords=["after probation", "following probation", "upon completion", "permanent employee"],
                esa_section="s.54(1)(b), s.57",
            ),
        ],
        likely_sections=[
            "Probationary Period", "Probation", "Trial Period", "Employment Terms",
            "New Employee", "Termination",
        ],
        always_applicable=False,
        applicability_note=(
            "Applicable if: contract mentions a probationary period, trial period, "
            "or initial employment period."
        ),
    ),

    ESAComplianceQuestion(
        id="ESA-MONITOR-01",
        title="Electronic Monitoring Policy (s.41.1.1 / O. Reg. 267/22) [Conditional]",
        esa_parts=["Part VII.0.2"],
        esa_sections=["s.41.1.1"],
        full_text=(
            "As of October 11, 2022, ESA s.41.1.1 requires employers with 25 or more employees "
            "as of January 1 of any year to have a written electronic monitoring policy. The "
            "policy must state whether employees are electronically monitored, the types of "
            "monitoring (if any), and the employer's purpose for collecting information. "
            "Does the contract or any referenced policy address electronic monitoring of "
            "employees in compliance with s.41.1.1? Does the contract impose monitoring "
            "obligations (e.g., location tracking, device monitoring, productivity software) "
            "without the required disclosure policy?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-MONITOR-01-SC1",
                description="Written electronic monitoring policy exists and is referenced (for 25+ employers)",
                keywords=["monitoring policy", "electronic monitoring", "tracking", "surveillance", "monitoring"],
                esa_section="s.41.1.1",
            ),
            SubCriterion(
                id="ESA-MONITOR-01-SC2",
                description="Policy discloses type of monitoring and purpose for information collection",
                keywords=["type of monitoring", "purpose of monitoring", "information use", "data collection"],
                esa_section="s.41.1.1(2)",
            ),
            SubCriterion(
                id="ESA-MONITOR-01-SC3",
                description="Employee provided a copy of the electronic monitoring policy",
                keywords=["provide policy", "policy provided", "copy to employee", "acknowledge policy"],
                esa_section="s.41.1.1(5)",
            ),
        ],
        likely_sections=[
            "Electronic Monitoring", "Monitoring Policy", "Workplace Monitoring",
            "Technology Use", "Computer Use", "Remote Work", "Privacy",
        ],
        always_applicable=False,
        applicability_note=(
            "Applicable if: contract mentions computer/device use, location tracking, "
            "productivity monitoring, or employer monitoring of employee activities; "
            "or if employer clearly has 25+ employees."
        ),
    ),

    ESAComplianceQuestion(
        id="ESA-LEAVE-08",
        title="Reservist Leave (s.50.1) [Conditional]",
        esa_parts=["Part XIV"],
        esa_sections=["s.50.1"],
        full_text=(
            "ESA s.50.1 entitles employees who have been employed for at least 6 consecutive "
            "months and are members of the Canadian Forces Reserve to unpaid, job-protected "
            "reservist leave when called out for deployment, training, or Canadian Forces "
            "service. Does the contract address or restrict reservist leave entitlements? "
            "Does any contract term conflict with the employee's rights under s.50.1?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ESA-LEAVE-08-SC1",
                description="Reservist leave acknowledged for Canadian Forces Reserve members",
                keywords=["reservist", "military", "Canadian Forces", "reserve", "deployment"],
                esa_section="s.50.1",
            ),
            SubCriterion(
                id="ESA-LEAVE-08-SC2",
                description="No clause preventing or penalizing reservist leave",
                keywords=["military leave", "reserve leave", "forces leave", "deployment leave"],
                esa_section="s.50.1, s.74",
            ),
        ],
        likely_sections=[
            "Leaves of Absence", "Military Leave", "Reservist Leave", "Leave Policy",
        ],
        always_applicable=False,
        applicability_note=(
            "Applicable if: contract mentions military service, Canadian Forces, "
            "or reservist activities."
        ),
    ),
]


def get_all_questions() -> List[ESAComplianceQuestion]:
    return ESA_COMPLIANCE_QUESTIONS


def get_question_by_id(question_id: str) -> ESAComplianceQuestion:
    for q in ESA_COMPLIANCE_QUESTIONS:
        if q.id == question_id:
            return q
    raise ValueError(f"No ESA compliance question with id='{question_id}'")


def get_always_applicable_questions() -> List[ESAComplianceQuestion]:
    return [q for q in ESA_COMPLIANCE_QUESTIONS if q.always_applicable]


def get_conditional_questions() -> List[ESAComplianceQuestion]:
    return [q for q in ESA_COMPLIANCE_QUESTIONS if not q.always_applicable]


def get_all_question_ids() -> List[str]:
    return [q.id for q in ESA_COMPLIANCE_QUESTIONS]
