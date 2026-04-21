"""
The 5 compliance questions from the assignment specification (Table 1).
Each question has a list of sub-criteria that must ALL be evidenced for Fully Compliant.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SubCriterion:
    id: str
    description: str
    keywords: List[str]  # hint terms for retrieval targeting


@dataclass
class ComplianceQuestion:
    id: int
    title: str
    full_text: str
    sub_criteria: List[SubCriterion]
    likely_sections: List[str]  # hints for section-targeted retrieval


COMPLIANCE_QUESTIONS: List[ComplianceQuestion] = [
    ComplianceQuestion(
        id=1,
        title="Password Management",
        full_text=(
            "The contract must require a documented password standard covering password "
            "length/strength, prohibition of default and known-compromised passwords, "
            "secure storage (no plaintext; salted hashing if stored), brute-force protections "
            "(lockout/rate limiting), prohibition on password sharing, vaulting of privileged "
            "credentials/recovery codes, and time-based rotation for break-glass credentials. "
            "Based on the contract language and exhibits, what is the compliance state for "
            "Password Management?"
        ),
        sub_criteria=[
            SubCriterion(
                id="PWD-01",
                description="Password length/strength requirements documented (min 12 chars for regular, 14 for admin)",
                keywords=["password length", "characters", "passphrase", "strength", "minimum"],
            ),
            SubCriterion(
                id="PWD-02",
                description="Prohibition of default and known-compromised passwords",
                keywords=["default password", "known-compromised", "screening", "hibp", "blacklist"],
            ),
            SubCriterion(
                id="PWD-03",
                description="Secure storage — no plaintext; salted hashing required",
                keywords=["plaintext", "salted hash", "hashing", "bcrypt", "storage", "encrypted"],
            ),
            SubCriterion(
                id="PWD-04",
                description="Brute-force protections: account lockout or rate limiting",
                keywords=["lockout", "rate limiting", "brute force", "account lockout", "throttle"],
            ),
            SubCriterion(
                id="PWD-05",
                description="Prohibition on password sharing",
                keywords=["password sharing", "shared password", "shared account", "shared credentials"],
            ),
            SubCriterion(
                id="PWD-06",
                description="Vaulting of privileged credentials and recovery codes",
                keywords=["vault", "vaulting", "privileged credentials", "recovery codes", "secrets vault", "KMS"],
            ),
            SubCriterion(
                id="PWD-07",
                description="Time-based rotation for break-glass credentials (at least every 90 days)",
                keywords=["break-glass", "rotation", "90 days", "rotate", "emergency access"],
            ),
        ],
        likely_sections=[
            # Generic domain terms only — these work across any contract structure
            "Password Management", "Password Standard", "Password Policy",
            "Authentication", "Credentials", "Account Management",
            "Identity", "Access Control", "Break-glass",
        ],
    ),

    ComplianceQuestion(
        id=2,
        title="IT Asset Management",
        full_text=(
            "The contract must require an in-scope asset inventory (including cloud "
            "accounts/subscriptions, workloads, databases, security tooling), define minimum "
            "inventory fields, require at least quarterly reconciliation/review, and require "
            "secure configuration baselines with drift remediation and prohibition of insecure "
            "defaults. Based on the contract language and exhibits, what is the compliance state "
            "for IT Asset Management?"
        ),
        sub_criteria=[
            SubCriterion(
                id="ASSET-01",
                description="In-scope asset inventory required (cloud accounts, workloads, databases, security tooling)",
                keywords=["asset inventory", "inventory", "in-scope", "cloud accounts", "workloads", "databases"],
            ),
            SubCriterion(
                id="ASSET-02",
                description="Minimum inventory fields defined (asset ID, type, environment, owner, criticality)",
                keywords=["inventory fields", "asset ID", "owner", "criticality", "environment", "minimum fields"],
            ),
            SubCriterion(
                id="ASSET-03",
                description="At least quarterly inventory reconciliation/review",
                keywords=["quarterly", "reconciliation", "review", "quarterly review", "inventory review"],
            ),
            SubCriterion(
                id="ASSET-04",
                description="Secure configuration baselines maintained (CIS benchmarks or equivalent)",
                keywords=["configuration baseline", "CIS", "secure configuration", "hardening", "benchmark"],
            ),
            SubCriterion(
                id="ASSET-05",
                description="Drift remediation and prohibition of insecure defaults",
                keywords=["drift", "remediation", "insecure defaults", "default passwords", "configuration drift"],
            ),
        ],
        likely_sections=[
            "Asset Management", "Asset Inventory", "IT Asset",
            "Configuration Management", "Configuration Baseline",
            "Inventory", "Cloud Assets", "Infrastructure",
        ],
    ),

    ComplianceQuestion(
        id=3,
        title="Security Training and Background Checks",
        full_text=(
            "The contract must require security awareness training on hire and at least annually, "
            "and background screening for personnel with access to Company Data to the extent "
            "permitted by law, including maintaining a screening policy and attestation/evidence. "
            "Based on the contract language and exhibits, what is the compliance state for "
            "Security Training and Background Checks?"
        ),
        sub_criteria=[
            SubCriterion(
                id="TRAIN-01",
                description="Security awareness training required on hire",
                keywords=["security training", "awareness training", "on hire", "onboarding", "new hire"],
            ),
            SubCriterion(
                id="TRAIN-02",
                description="Security awareness training required at least annually",
                keywords=["annual training", "annually", "yearly", "refresher", "annual refresh"],
            ),
            SubCriterion(
                id="BG-01",
                description="Background screening required for personnel with access to Company Data",
                keywords=["background check", "background screening", "screening", "criminal", "personnel screening"],
            ),
            SubCriterion(
                id="BG-02",
                description="Screening policy maintained and attestation/evidence kept",
                keywords=["screening policy", "attestation", "evidence", "completion records", "policy"],
            ),
        ],
        likely_sections=[
            "Security Training", "Awareness Training", "Training",
            "Background Check", "Background Screening", "Personnel Screening",
            "Governance", "Human Resources", "Personnel",
        ],
    ),

    ComplianceQuestion(
        id=4,
        title="Data in Transit Encryption",
        full_text=(
            "The contract must require encryption of Company Data in transit using TLS 1.2+ "
            "(preferably TLS 1.3 where feasible) for Company-to-Service traffic, administrative "
            "access pathways, and applicable Service-to-Subprocessor transfers, with certificate "
            "management and avoidance of insecure cipher suites. Based on the contract language "
            "and exhibits, what is the compliance state for Data in Transit Encryption?"
        ),
        sub_criteria=[
            SubCriterion(
                id="TLS-01",
                description="TLS 1.2+ required for Company-to-Service connections",
                keywords=["TLS 1.2", "TLS 1.3", "encryption in transit", "HTTPS", "transport layer"],
            ),
            SubCriterion(
                id="TLS-02",
                description="TLS 1.3 preferred where feasible",
                keywords=["TLS 1.3", "prefer 1.3", "where feasible", "preferred"],
            ),
            SubCriterion(
                id="TLS-03",
                description="Encryption required for administrative access pathways",
                keywords=["administrative access", "admin pathway", "bastion", "management plane", "admin connection"],
            ),
            SubCriterion(
                id="TLS-04",
                description="Encryption for Service-to-Subprocessor transfers carrying Company Data",
                keywords=["subprocessor", "third party", "service-to-service", "transfer", "subprocessor transfer"],
            ),
            SubCriterion(
                id="TLS-05",
                description="Certificate management documented and insecure cipher suites prohibited",
                keywords=["certificate", "cipher suite", "cipher", "certificate management", "insecure cipher"],
            ),
        ],
        likely_sections=[
            "Encryption", "Data in Transit", "TLS", "Transport Security",
            "Cryptography", "Key Management", "Network Security",
            "Data Protection", "Communications Security",
        ],
    ),

    ComplianceQuestion(
        id=5,
        title="Network Authentication and Authorization Protocols",
        full_text=(
            "The contract must specify the authentication mechanisms (e.g., SAML SSO for users, "
            "OAuth/token-based for APIs), require MFA for privileged/production access, require "
            "secure admin pathways (bastion/secure gateway) with session logging, and require "
            "RBAC authorization. Based on the contract language and exhibits, what is the "
            "compliance state for Network Authentication and Authorization Protocols?"
        ),
        sub_criteria=[
            SubCriterion(
                id="AUTH-01",
                description="Authentication mechanisms specified (SAML SSO for users, OAuth/token for APIs)",
                keywords=["SAML", "SSO", "OAuth", "token", "authentication mechanism", "SAML 2.0"],
            ),
            SubCriterion(
                id="AUTH-02",
                description="MFA required for privileged/production access",
                keywords=["MFA", "multi-factor", "two-factor", "2FA", "privileged access", "production access"],
            ),
            SubCriterion(
                id="AUTH-03",
                description="Secure admin pathways required (bastion/secure gateway)",
                keywords=["bastion", "jump host", "secure gateway", "ZTNA", "jump box", "admin pathway"],
            ),
            SubCriterion(
                id="AUTH-04",
                description="Session logging for admin pathways",
                keywords=["session logging", "session log", "admin session", "audit log", "privileged session"],
            ),
            SubCriterion(
                id="AUTH-05",
                description="RBAC authorization required",
                keywords=["RBAC", "role-based", "role based access", "least privilege", "roles", "authorization"],
            ),
        ],
        likely_sections=[
            "Authentication", "Authorization", "Identity",
            "Access Control", "MFA", "Multi-factor",
            "Network Security", "Remote Access", "Privileged Access",
            "Single Sign-On", "SSO", "RBAC",
        ],
    ),
]


def get_question_by_id(question_id: int) -> ComplianceQuestion:
    for q in COMPLIANCE_QUESTIONS:
        if q.id == question_id:
            return q
    raise ValueError(f"No compliance question with id={question_id}")


def get_all_question_ids() -> List[int]:
    return [q.id for q in COMPLIANCE_QUESTIONS]
