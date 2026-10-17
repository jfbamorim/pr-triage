import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from openai import OpenAI

from pr_triage.domain.schemas import WorkflowResult
from pr_triage.workflow import run_workflow

CASES_PATH = Path("data/eval/cases.jsonl")


def load_cases(split: str, group: str | None) -> list[dict]:
    lines = CASES_PATH.read_text(encoding="utf-8").splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    if split != "all":
        cases = [c for c in cases if c["split"] == split]
    if group:
        cases = [c for c in cases if c["group"] == group]
    return cases


def actual_values(result: WorkflowResult) -> dict:
    return {
        "status": result.status.value,
        "reason": result.reason.value if result.reason else None,
        "band": result.band.value if result.band else None,
        "escalation": result.escalation.value if result.escalation else None,
        "missing": result.missing,
        "invalid": result.invalid,
    }


def check(expected: dict, result: WorkflowResult) -> tuple[list[str], float | None]:
    actual = actual_values(result)
    failures = []

    for field in ("status", "reason", "band", "escalation"):
        if field in expected and actual[field] != expected[field]:
            failures.append(
                f"{field}: esperado {expected[field]}, obtido {actual[field]}"
            )

    for field in ("missing", "invalid"):
        if field in expected and sorted(actual[field]) != sorted(expected[field]):
            failures.append(
                f"{field}: esperado {expected[field]}, obtido {actual[field]}"
            )

    required = expected.get("evidence_must_include", [])
    found_ids = {e.chunk_id for e in result.evidence}
    absent = [chunk_id for chunk_id in required if chunk_id not in found_ids]
    if absent:
        failures.append("evidência em falta: " + ", ".join(absent))

    recall = (len(required) - len(absent)) / len(required) if required else None
    return failures, recall


def run_case(case: dict, client: OpenAI) -> dict:
    base = {"id": case["id"], "group": case["group"], "split": case["split"]}
    start = time.perf_counter()
    try:
        result = run_workflow(case["text"], client)
    except Exception as error:
        return {
            **base,
            "passed": False,
            "failures": [f"erro: {error}"],
            "recall": None,
            "latency": time.perf_counter() - start,
            "actual": None,
            "evidence": [],
        }
    latency = time.perf_counter() - start
    failures, recall = check(case["expected"], result)
    return {
        **base,
        "passed": not failures,
        "failures": failures,
        "recall": recall,
        "latency": latency,
        "actual": actual_values(result),
        "evidence": [
            {"chunk_id": e.chunk_id, "score": e.score} for e in result.evidence
        ],
    }


def print_summary(results: list[dict]) -> None:
    by_group = defaultdict(list)
    for r in results:
        by_group[r["group"]].append(r)

    print("\nPor grupo")
    for group, items in by_group.items():
        passed = sum(r["passed"] for r in items)
        print(f"  {group:16} {passed}/{len(items)}")

    total = sum(r["passed"] for r in results)
    print(f"\nTotal: {total}/{len(results)}")

    recalls = [r["recall"] for r in results if r["recall"] is not None]
    if recalls:
        print(f"Source recall médio: {sum(recalls) / len(recalls):.2f}")
    mean_latency = sum(r["latency"] for r in results) / len(results)
    print(f"Latência média: {mean_latency:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="dev")
    parser.add_argument("--group")
    parser.add_argument("--out")
    args = parser.parse_args()

    cases = load_cases(args.split, args.group)
    if not cases:
        print("Nenhum caso encontrado.")
        return

    client = OpenAI()
    results = []
    for case in cases:
        outcome = run_case(case, client)
        results.append(outcome)
        label = "PASS" if outcome["passed"] else "FAIL"
        print(f"{label}  {outcome['id']}  ({outcome['latency']:.1f}s)")
        for failure in outcome["failures"]:
            print(f"      {failure}")

    print_summary(results)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()