"""Every GitHub workflow must be valid YAML: an unquoted ": " inside a step name made build.yml unparsable and
GitHub started no run at all (it failed in 0 s)."""
import glob
import os

import pytest

yaml = pytest.importorskip("yaml")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKFLOWS = sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.y*ml")))


def test_workflows_exist():
    assert WORKFLOWS


@pytest.mark.parametrize("path", WORKFLOWS, ids=os.path.basename)
def test_workflow_is_valid_yaml(path):
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    assert isinstance(doc, dict)
    assert isinstance(doc.get("jobs"), dict) and doc["jobs"]
