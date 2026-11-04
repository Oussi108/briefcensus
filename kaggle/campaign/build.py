"""Builds a private, CPU-only Kaggle kernel for protocol v2: python build.py debug | confirm | test2 | holdout | extras | forecast | coverage | forecast2 | clean | second | followup"""
import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
FILES = ['src/campaign.py', 'src/ukpv.py', 'src/run_campaign.py', 'src/kill_test.py', 'src/kill_test2.py', 'src/ausgrid.py', 'src/extras.py', 'src/forecast.py', 'src/sensitivity.py', 'src/clean_run.py', 'src/clean_followup.py', 'RUN_LOG.md']
LIMITS = {'debug': 2, 'confirm': 8, 'test2': 2, 'holdout': 3, 'extras': 4, 'forecast': 8, 'coverage': 4, 'forecast2': 8, 'clean': 4, 'second': 4, 'followup': 6}
DATASETS = ['oussielhoucine/p3-solar-fleets']


def main():
    mode = sys.argv[1]
    if mode not in LIMITS:
        sys.exit(__doc__)
    sources = {name: base64.b64encode((PROJECT / name).read_bytes()).decode() for name in FILES}
    text = (HERE / 'kernel_template.py').read_text(encoding='utf-8')
    text = text.replace('__MODE__', mode).replace('__LIMIT_HOURS__', str(LIMITS[mode])).replace('__SOURCES__', repr(sources))
    out = HERE / mode
    out.mkdir(exist_ok=True)
    (out / 'run_kaggle.py').write_text(text, encoding='utf-8')
    (out / 'kernel-metadata.json').write_text(json.dumps({
        'id': f'oussielhoucine/p3-campaign-{mode}', 'title': f'p3-campaign-{mode}', 'code_file': 'run_kaggle.py', 'language': 'python', 'kernel_type': 'script',
        'is_private': True, 'enable_gpu': False, 'enable_tpu': False, 'enable_internet': False, 'dataset_sources': DATASETS + (['oussielhoucine/p3-ausgrid-y3'] if mode == 'holdout' else []),
        'competition_sources': [], 'kernel_sources': [], 'model_sources': []}, indent=2))
    print('built', out, 'time limit hours', LIMITS[mode])


if __name__ == '__main__':
    main()
