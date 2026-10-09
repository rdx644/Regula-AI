import asyncio
import json
from evaluation.evaluate import run_evaluation
from evaluation.predict import predict


def test_missing_predictions_never_claim_evaluation_complete():
    result = asyncio.run(run_evaluation())
    assert result['status'] == 'not_run' and result['evaluated'] == 0


def test_untrusted_citation_and_failed_prediction_count_as_failures(tmp_path):
    dataset = tmp_path / 'dataset.jsonl'
    predictions = tmp_path / 'predictions.jsonl'
    dataset.write_text(json.dumps({'id': 'one', 'task': 'obligation_extraction', 'input': {'text': 'Banks shall review daily.'},
        'expected': {'obligations': [{'obligation_text': 'Banks shall review daily.'}]}})+'\n', encoding='utf-8')
    predictions.write_text(json.dumps({'id': 'one', 'prediction': {'obligations': [{'obligation_text': 'Banks shall review daily.',
        'source_text_snippet': 'Invented source', 'source_page': 1}]}})+'\n', encoding='utf-8')
    result = asyncio.run(run_evaluation(str(dataset), str(predictions)))
    assert result['details'][0]['metrics']['citation_validity'] == 0
    predictions.write_text(json.dumps({'id': 'one', 'prediction': {'failed': True}})+'\n', encoding='utf-8')
    result = asyncio.run(run_evaluation(str(dataset), str(predictions)))
    assert result['evaluated'] == 1 and result['task_success_rate'] == 0


def test_deterministic_risk_prediction_preserves_zero():
    result = asyncio.run(predict({'gap': {'severity': 'high'}, 'likelihood': 0, 'impact': 1}, 'risk_assessment', 'one'))
    assert result['risk_score'] == 0
