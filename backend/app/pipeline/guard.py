from app.schemas import Flag, GuardVerdict


def evaluate_guard(flags: list[Flag], verdict: GuardVerdict | None) -> tuple[bool, list[Flag]]:
    combined = list(flags)
    if verdict:
        for reason in verdict.reasons:
            severity = "high" if verdict.verdict == "malicious" else "medium"
            combined.append(
                Flag(
                    code=reason.code,
                    severity=severity,
                    detail_en=reason.detail_en,
                    detail_zh=reason.detail_zh,
                )
            )
    if verdict and verdict.verdict == "malicious":
        combined.append(
            Flag(
                code="MALICIOUS_INSTRUCTIONS",
                severity="high",
                detail_en="The guard detected malicious instructions.",
                detail_zh="审查发现恶意指令。",
            )
        )
    refused = any(flag.severity == "high" for flag in combined)
    refused = refused or bool(verdict and verdict.verdict != "ok" and verdict.risk >= 0.5)
    return refused, combined
