import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.agents.schemas import (
    ObligationExtraction,
    ObligationExtractionBatch,
    MappingDecision,
    GapIdentification,
    RiskAssessmentOutput,
)
from app.services.parser import DocumentChunk


@dataclass
class EvaluationResult:
    task_id: str
    task_type: str
    passed: bool
    score: float
    details: Dict[str, Any]


def load_golden_dataset(path: str) -> List[Dict[str, Any]]:
    dataset = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                dataset.append(json.loads(line))
    return dataset


def evaluate_obligation_extraction(
    predicted: List[ObligationExtraction],
    expected: List[Dict[str, Any]],
) -> Dict[str, Any]:
    pred_obligations = [p.obligation_text.lower().strip() for p in predicted]
    exp_obligations = [e["obligation_text"].lower().strip() for e in expected]

    true_positives = 0
    for exp in exp_obligations:
        for pred in pred_obligations:
            if _text_similarity(exp, pred) > 0.8:
                true_positives += 1
                break

    precision = true_positives / len(pred_obligations) if pred_obligations else 0.0
    recall = true_positives / len(exp_obligations) if exp_obligations else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "true_positives": true_positives,
        "predicted_count": len(pred_obligations),
        "expected_count": len(exp_obligations),
    }


def evaluate_mapping(
    predicted: MappingDecision,
    expected: Dict[str, Any],
) -> Dict[str, Any]:
    correct_control = predicted.control_id == expected["mappings"][0]["control_id"]
    correct_status = predicted.mapping_status == expected["mappings"][0]["mapping_status"]

    return {
        "correct_control": correct_control,
        "correct_status": correct_status,
        "confidence_match": abs(predicted.confidence - expected["mappings"][0]["confidence"]) < 0.15,
        "score": 1.0 if (correct_control and correct_status) else 0.0,
    }


def evaluate_gap_identification(
    predicted: Optional[GapIdentification],
    expected: Dict[str, Any],
) -> Dict[str, Any]:
    exp_gap = expected.get("gap")

    if exp_gap is None:
        return {
            "correct": predicted is None,
            "score": 1.0 if predicted is None else 0.0,
        }

    if predicted is None:
        return {"correct": False, "score": 0.0}

    correct_type = predicted.gap_type == exp_gap["gap_type"]
    correct_severity = predicted.severity == exp_gap["severity"]

    return {
        "correct_type": correct_type,
        "correct_severity": correct_severity,
        "score": 1.0 if (correct_type and correct_severity) else 0.5 if correct_type else 0.0,
    }


def evaluate_risk_assessment(
    predicted: RiskAssessmentOutput,
    expected: Dict[str, Any],
) -> Dict[str, Any]:
    exp = expected

    likelihood_diff = abs(predicted.likelihood - exp["likelihood"])
    impact_diff = abs(predicted.impact - exp["impact"])
    risk_score_diff = abs(predicted.risk_score - exp["risk_score"])
    correct_level = predicted.risk_level == exp["risk_level"]

    return {
        "likelihood_error": round(likelihood_diff, 3),
        "impact_error": round(impact_diff, 3),
        "risk_score_error": round(risk_score_diff, 3),
        "correct_level": correct_level,
        "score": 1.0 if (correct_level and risk_score_diff < 10) else 0.5 if correct_level else 0.0,
    }


def _text_similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


async def run_evaluation(
    dataset_path: str = "evaluation/golden_dataset.jsonl",
    predictions_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Score saved agent outputs; never manufacture passes or call an external model.

    Predictions are JSONL records shaped as {"id": "gold-001", "prediction": {...}}.
    This keeps benchmark runs repeatable and separates model execution from scoring.
    """
    dataset = load_golden_dataset(dataset_path)
    task_types = ("obligation_extraction", "mapping", "gap_identification", "risk_assessment")
    if not predictions_path:
        return {
            "status": "not_run",
            "reason": "Provide predictions_path with one JSONL prediction per evaluated example.",
            "dataset_size": len(dataset),
            "evaluated": 0,
            "summary": {task: {"total": 0, "available": sum(row["task"] == task for row in dataset)} for task in task_types},
            "details": [],
        }

    predictions = {}
    with open(predictions_path, "r", encoding="utf-8") as prediction_file:
        for line_number, line in enumerate(prediction_file, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            task_id = row.get("id")
            if not task_id or task_id in predictions:
                raise ValueError(f"Prediction line {line_number} has a missing or duplicate id")
            predictions[task_id] = row.get("prediction")

    summary = {task: {"total": 0, "score_sum": 0.0} for task in task_types}
    details = []
    for item in dataset:
        task = item["task"]
        prediction = predictions.get(item["id"])
        detail = {"id": item["id"], "task": task, "evaluated": prediction is not None}
        if prediction is None:
            details.append(detail)
            continue
        if prediction.get("failed"):
            summary[task]["total"] += 1
            detail.update(score=0.0, failed=True)
            details.append(detail)
            continue

        expected = item["expected"]
        score = 0.0
        if task == "obligation_extraction":
            predicted_obligations = prediction.get("obligations", [])
            expected_obligations = expected.get("obligations", [])
            unmatched = set(range(len(predicted_obligations)))
            true_positives = 0
            for expected_row in expected_obligations:
                target = expected_row["obligation_text"].lower().strip()
                best_index = None
                best_similarity = 0.0
                for index in unmatched:
                    candidate = predicted_obligations[index]
                    candidate_text = candidate if isinstance(candidate, str) else candidate.get("obligation_text", "")
                    similarity = _text_similarity(target, candidate_text.lower().strip())
                    if similarity > best_similarity:
                        best_index, best_similarity = index, similarity
                if best_index is not None and best_similarity > 0.8:
                    true_positives += 1
                    unmatched.remove(best_index)
            precision = true_positives / len(predicted_obligations) if predicted_obligations else 0.0
            recall = true_positives / len(expected_obligations) if expected_obligations else (1.0 if not predicted_obligations else 0.0)
            score = 1.0 if not expected_obligations and not predicted_obligations else (
                2 * precision * recall / (precision + recall) if precision + recall else 0.0
            )
            detail["metrics"] = {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(score, 3)}
            grounded = [p for p in predicted_obligations if isinstance(p, dict) and p.get('source_text_snippet')
                and p['source_text_snippet'] in item['input']['text'] and p.get('source_page') == item['input'].get('source_page', 1)]
            detail['metrics']['citation_validity'] = len(grounded) / len(predicted_obligations) if predicted_obligations else None
            detail['metrics']['unsupported_citation_rate'] = 1 - len(grounded) / len(predicted_obligations) if predicted_obligations else None
        elif task == "mapping":
            predicted_mapping = prediction.get("mapping", prediction)
            expected_mapping = expected["mappings"][0]
            predicted_control = predicted_mapping.get("control_id") or predicted_mapping.get("control_code")
            control_match = predicted_control == expected_mapping["control_id"]
            status_match = predicted_mapping.get("mapping_status") == expected_mapping["mapping_status"]
            score = 1.0 if control_match and status_match else 0.0
            detail["metrics"] = {"correct_control": control_match, "correct_status": status_match,
                "precision": score, "recall": score, "f1": score}
        elif task == "gap_identification":
            predicted_gap = prediction.get("gap") if "gap" in prediction else prediction
            expected_gap = expected.get("gap")
            if expected_gap is None:
                score = 1.0 if predicted_gap is None else 0.0
            elif predicted_gap is not None:
                correct_type = predicted_gap.get("gap_type") == expected_gap["gap_type"]
                correct_severity = predicted_gap.get("severity") == expected_gap["severity"]
                score = 1.0 if correct_type and correct_severity else 0.5 if correct_type else 0.0
            detail["metrics"] = {"correct": score == 1.0, "score": score}
        elif task == "risk_assessment":
            prediction = prediction.get("risk_assessment", prediction)
            level_match = prediction.get("risk_level") == expected["risk_level"]
            score_delta = abs(float(prediction.get("risk_score", 0)) - float(expected["risk_score"]))
            score = 1.0 if level_match and score_delta < 10 else 0.5 if level_match else 0.0
            detail["metrics"] = {"correct_level": level_match, "risk_score_error": round(score_delta, 3)}

        summary[task]["total"] += 1
        summary[task]["score_sum"] += score
        detail["score"] = round(score, 3)
        detail['passed'] = score == 1 and (task != 'obligation_extraction' or detail['metrics']['citation_validity'] in {None, 1.0})
        details.append(detail)

    for task, values in summary.items():
        total = values["total"]
        values["available"] = sum(row["task"] == task for row in dataset)
        values["average_score"] = round(values["score_sum"] / total, 3) if total else None
        del values["score_sum"]

    evaluated = sum(result["evaluated"] for result in details)
    return {
        "status": "complete" if evaluated == len(dataset) else "partial",
        "dataset_size": len(dataset),
        "evaluated": evaluated,
        "summary": summary,
        "details": details,
        "task_success_rate": round(sum(d.get('passed', False) for d in details) / len(dataset), 3) if dataset else None,
        "retrieval_metrics": {"status": "not_measured", "reason": "Golden mapping cases provide candidate controls; no independent retrieval relevance labels"},
        "unsupported_claim_rate": {"status": "not_measured", "reason": "Citation-span validity is measured; broader legal assertions require reviewed claim labels"},
        "label_review": "pending; original source page/section annotations absent from input; gold-009 labels stale evidence as no_evidence",
    }


if __name__ == "__main__":
    import asyncio
    import argparse

    parser = argparse.ArgumentParser(description="Score saved RegulaAI benchmark predictions.")
    parser.add_argument("--dataset", default="evaluation/golden_dataset.jsonl")
    parser.add_argument("--predictions", help="JSONL file with id and prediction fields")
    args = parser.parse_args()
    result = asyncio.run(run_evaluation(args.dataset, args.predictions))
    print(json.dumps(result, indent=2))
