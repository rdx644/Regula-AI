"""Generate predictions from application components after explicit model approval.

This is component evaluation, not API/queue E2E evidence. It never reads expected
answers. Dataset label review is still required before any reliability claim.
"""
import argparse
import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid5, NAMESPACE_URL
from app.agents.extraction import process_chunk
from app.agents.mapping import map_obligation_to_controls
from app.core import ai_provider
from app.services.parser import DocumentChunk
from app.services.compliance import landscape_gap
from app.services.governance import risk
from app.services.execution import usage_context


def fixture_id(value):
    return uuid5(NAMESPACE_URL, 'regulaai:synthetic-golden:' + value)


async def predict(inputs, task, identifier):
    """Only input fields cross this boundary; expected labels are inaccessible."""
    if task == 'obligation_extraction':
        chunk = DocumentChunk(inputs['text'], inputs.get('source_page', 1), inputs.get('source_section'))
        state = {'version_id': fixture_id(identifier), 'organization_id': fixture_id('evaluation'),
            'chunks': [chunk], 'current_chunk_index': 0, 'extracted_obligations': [], 'errors': [],
            'tokens_used': 0, 'model_used': '', 'provider': ''}
        state = await process_chunk(state)
        if state['errors']:
            raise RuntimeError('Extraction failed citation/schema validation')
        return {'obligations': [o.model_dump(mode='json') for o in state['extracted_obligations']]}
    if task == 'mapping':
        obligation = SimpleNamespace(id=fixture_id(identifier), condition=None, frequency=None, **inputs['obligation'])
        controls = [SimpleNamespace(id=fixture_id(c['id']), control_id_code=c['code'], objective=c['objective'],
            description=c['description'], procedure=c.get('procedure', 'Not supplied'), frequency=c.get('frequency'), business_unit=None)
            for c in inputs['controls']]
        decision = await map_obligation_to_controls(obligation, controls)
        mapping = decision.model_dump(mode='json')
        reverse = {str(fixture_id(c['id'])): c['id'] for c in inputs['controls']}
        mapping['control_id'] = reverse.get(mapping['control_id'])
        return {'mapping': mapping, 'retrieved_control_ids': [c['id'] for c in inputs['controls']],
                'retrieval_component': 'provided candidates; retrieval quality not measured'}
    if task == 'gap_identification':
        def dated(record):
            values = dict(record)
            for key in ['coverage_end', 'coverage_start', 'tested_at', 'created_at']:
                values[key] = datetime.fromisoformat(values[key]).replace(tzinfo=timezone.utc) if values.get(key) else None
            return SimpleNamespace(**values)
        # Historical fixtures are a Q3-2024 snapshot. The reviewed-mapping
        # prerequisite is explicit in the adapter rather than inferred by a model.
        at = datetime.fromisoformat(inputs.get('as_of', '2024-09-30T00:00:00+00:00'))
        gap = landscape_gap(SimpleNamespace(mapping_status='mapped', approved_by=fixture_id('reviewer')),
            SimpleNamespace(**inputs['control']) if inputs.get('control') else None,
            [dated(e) for e in inputs.get('evidence', [])], [dated(t) for t in inputs.get('tests', [])], at)
        return {'gap': gap, 'assumptions': {'as_of': at.isoformat(), 'mapping_reviewed': True}}
    if task == 'risk_assessment':
        likelihood = inputs.get('likelihood', .8 if inputs['gap']['severity'] in {'high', 'critical'} else .5)
        impact = inputs.get('impact', .9 if inputs['gap']['severity'] in {'high', 'critical'} else .6)
        likelihood, impact, score, level = risk(likelihood, impact)
        return {'likelihood': likelihood, 'impact': impact, 'risk_score': score, 'risk_level': level,
                'method': 'deterministic landscape assumptions; not a model risk judgment'}
    raise ValueError('Unsupported task')


async def main(args):
    if not args.execute_openai:
        raise SystemExit('No requests made. Supply --execute-openai only after owner budget approval.')
    if not 1 <= args.max_requests <= 20:
        raise SystemExit('Maximum request cap must be 1..20')
    ai_provider.settings.MODEL_EXECUTION_ENABLED = True
    # This counted wrapper caps actual SDK calls, including retries. Token
    # reservations use a byte upper bound for input and declared output maximum.
    import httpx
    state = {'requests': 0, 'reserved_tokens': 0}
    class BudgetClient(httpx.AsyncClient):
        async def send(self, request, **kwargs):
            body = json.loads(request.content)
            reserve = len(request.content) + body.get('max_tokens', 0)
            if state['requests'] >= args.max_requests or state['reserved_tokens'] + reserve > args.max_reserved_tokens:
                raise RuntimeError('Evaluation request/token cap reached')
            state['requests'] += 1
            state['reserved_tokens'] += reserve
            return await super().send(request, **kwargs)
    from openai import AsyncOpenAI
    original = ai_provider.OpenAIProvider
    class BoundedProvider(original):
        def __init__(self):
            self.client = AsyncOpenAI(api_key=ai_provider.settings.OPENAI_API_KEY, http_client=BudgetClient(), max_retries=0)
    ai_provider.OpenAIProvider = BoundedProvider
    for task in ['extraction', 'mapping']:
        ai_provider.DEFAULT_CONFIGS[task] = replace(ai_provider.DEFAULT_CONFIGS[task], model=args.model, max_tokens=2048, temperature=0)
    dataset_bytes = Path(args.dataset).read_bytes()
    rows = [json.loads(line) for line in dataset_bytes.decode('utf-8').splitlines() if line.strip()]
    provenance = {'provider': 'openai', 'configured_model': args.model, 'prompt_version': '2026-10-v2',
        'timestamp': datetime.now(timezone.utc).isoformat(), 'dataset_sha256': hashlib.sha256(dataset_bytes).hexdigest(),
        'scope': 'actual application extraction/mapping components; deterministic gap/risk; no queue/persistence',
        'synthetic': True, 'label_review': 'pending', 'limits': vars(args)}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as saved:
        for row in rows:
            usage = []
            context = usage_context.set(usage)
            try:
                prediction = await predict(row['input'], row['task'], row['id'])
                record = {'id': row['id'], 'prediction': prediction, 'model_calls': usage}
            except Exception as exc:
                record = {'id': row['id'], 'prediction': {'failed': True}, 'error_type': type(exc).__name__, 'model_calls': usage}
            finally:
                usage_context.reset(context)
            saved.write(json.dumps(record) + '\n')
            saved.flush()
    provenance['usage'] = state
    output.with_suffix('.provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'cases': len(rows), **state}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute-openai', action='store_true')
    parser.add_argument('--model', choices=['gpt-4o-mini'], default='gpt-4o-mini')
    parser.add_argument('--max-requests', type=int, default=20)
    parser.add_argument('--max-reserved-tokens', type=int, default=80000)
    parser.add_argument('--dataset', default='evaluation/golden_dataset.jsonl')
    parser.add_argument('--output', default='../output/evaluation/predictions.jsonl')
    asyncio.run(main(parser.parse_args()))
