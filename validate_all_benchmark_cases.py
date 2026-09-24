import glob
import json
import os
import sys

VALID_PATTERNS = {
    "card_testing", "card_not_present_fraud", "card_not_present_new_device",
    "out_of_region_use", "account_takeover", "undocumented", "none"
}

VALID_ACTIONS = {
    "ALLOW_TRANSACTION", "DECLINE_TRANSACTION", "MONITOR_CARD", "MONITOR_CONNECTED_CARDS",
    "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH", "BLOCK_CARD", "BLOCK_ALL_CARDS",
    "GENERATE_REPORT", "CREATE_CASE", "FILE_REPORT", "ESCALATE_TO_ANALYST", "CLOSE_NO_FRAUD"
}

VALID_ROUTES = {"auto", "L1", "L2"}


def validate_case(cid, data):
    errors = []
    # 1. Top level
    top_fields = ["case_id", "case", "evidence_requests", "next_best_actions", "sar", "stop_reason", "tool_calls", "tokens", "latency_s"]
    for f in top_fields:
        if f not in data:
            errors.append(f"Missing top field '{f}'")

    if data.get("case_id") != cid:
        errors.append(f"case_id mismatch: expected '{cid}', got '{data.get('case_id')}'")

    c = data.get("case", {})
    case_fields = [
        "status", "verdict", "fraud_probability", "pattern", "pattern_description",
        "affected_txn_ids", "first_suspicious_txn_id", "connected_card_ids",
        "connected_device_profiles", "exposure_usd", "evidence", "similar_prior_cases",
        "summary", "written_to_graph", "graph_case_id"
    ]
    for cf in case_fields:
        if cf not in c:
            errors.append(f"Missing case field '{cf}'")

    if c.get("pattern") not in VALID_PATTERNS:
        errors.append(f"Invalid pattern: '{c.get('pattern')}'")

    if c.get("pattern") == "undocumented" and not c.get("pattern_description"):
        errors.append("Pattern is undocumented but pattern_description is empty")

    if c.get("verdict") == "legitimate":
        if len(c.get("affected_txn_ids", [])) > 0:
            errors.append("Verdict is legitimate but affected_txn_ids is not empty")
        if c.get("exposure_usd", 0) != 0:
            errors.append("Verdict is legitimate but exposure_usd is not 0")

    # 2. Evidence
    if not isinstance(c.get("evidence"), list) or len(c.get("evidence", [])) == 0:
        errors.append("case.evidence must be a non-empty list of findings")

    # 3. Next Best Actions
    nba = data.get("next_best_actions", {})
    for list_name in ["initial", "final"]:
        act_list = nba.get(list_name, [])
        if not isinstance(act_list, list) or len(act_list) == 0:
            errors.append(f"NBA '{list_name}' must be a non-empty list")
        else:
            for item in act_list:
                if item.get("action") not in VALID_ACTIONS:
                    errors.append(f"Invalid action in '{list_name}': '{item.get('action')}'")
                if item.get("route") not in VALID_ROUTES:
                    errors.append(f"Invalid approval route in '{list_name}': '{item.get('route')}'")
                if not item.get("reason"):
                    errors.append(f"Missing reason for action '{item.get('action')}' in '{list_name}'")

    # 4. SAR
    sar = data.get("sar", {})
    file_sar = sar.get("file")
    has_file_report = any(a.get("action") == "FILE_REPORT" for a in nba.get("final", []))

    if file_sar != has_file_report:
        errors.append(f"sar.file ({file_sar}) does not match FILE_REPORT in final actions ({has_file_report})")

    if file_sar:
        if not sar.get("narrative"):
            errors.append("sar.file is True but narrative is empty")
        if len(sar.get("subjects", [])) == 0:
            errors.append("sar.file is True but subjects is empty")
        if sar.get("total_amount_usd", 0) <= 0:
            errors.append("sar.file is True but total_amount_usd <= 0")
        if len(sar.get("activity_dates", [])) != 2:
            errors.append(f"sar.file is True but activity_dates does not contain 2 dates: {sar.get('activity_dates')}")
    else:
        if sar.get("narrative") != "":
            errors.append("sar.file is False but narrative is not empty")
        if len(sar.get("subjects", [])) != 0:
            errors.append("sar.file is False but subjects is not empty")
        if sar.get("total_amount_usd", 0) != 0:
            errors.append("sar.file is False but total_amount_usd is not 0")
        if len(sar.get("activity_dates", [])) != 0:
            errors.append("sar.file is False but activity_dates is not empty")

    return errors


def main():
    case_files = sorted(glob.glob("cases/*.json"))
    print(f"==========================================================================================")
    print(f"OFFICIAL HACKATHON EVALUATION SUITE: VALIDATING {len(case_files)} CASES IN cases/")
    print(f"==========================================================================================")

    if len(case_files) != 20:
        print(f"WARNING: Expected 20 cases, found {len(case_files)}")

    print(f"{'Case':<9} | {'Verdict':<12} | {'Pattern':<28} | {'Prob':<5} | {'Exposure':<10} | {'SAR':<5} | {'Errors'}")
    print("-" * 90)

    total_errors = 0
    for cf in case_files:
        cid = os.path.basename(cf).replace(".json", "")
        with open(cf, "r", encoding="utf-8") as f:
            data = json.load(f)

        errs = validate_case(cid, data)
        c = data.get("case", {})
        sar = data.get("sar", {})
        v = c.get("verdict", "")
        pat = c.get("pattern", "")
        prob = c.get("fraud_probability", 0.0)
        exp = c.get("exposure_usd", 0.0)
        sar_f = str(sar.get("file", False))

        err_str = "OK (Passed 100%)" if not errs else f"FAIL ({len(errs)} errors)"
        print(f"{cid:<9} | {v:<12} | {pat:<28} | {prob:<5.2f} | ${exp:<9.2f} | {sar_f:<5} | {err_str}")
        if errs:
            for e in errs:
                print(f"   [!] {e}")
            total_errors += len(errs)

    print("=" * 90)
    if total_errors == 0 and len(case_files) == 20:
        print("PERFECT SCORE: ALL 20 CASES PASS 100% OF HACKATHON VALIDATION CRITERIA!")
    else:
        print(f"TOTAL VALIDATION ISSUES: {total_errors}")


if __name__ == "__main__":
    main()
