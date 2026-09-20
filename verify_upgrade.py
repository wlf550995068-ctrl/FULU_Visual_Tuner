"""Run the independent tool regression suite and write an honest machine-readable report."""
from pathlib import Path
import json
import os
import sys
import unittest

ROOT = Path(__file__).resolve().parent
cache = ROOT / '.cache' / 'tmp'
cache.mkdir(parents=True, exist_ok=True)
os.environ['TMP'] = os.environ['TEMP'] = str(cache)
os.chdir(ROOT)

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = dict(tests=result.testsRun, passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
                  failures=[(str(t), error) for t, error in result.failures],
                  errors=[(str(t), error) for t, error in result.errors],
                  skipped=[(str(t), reason) for t, reason in result.skipped],
                  successful=result.wasSuccessful(), python=sys.version,
                  executable=sys.executable, project=str(ROOT))
    output = ROOT / 'test_output' / 'upgrade'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'tests.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
