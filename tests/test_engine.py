import asyncio
import json
from pathlib import Path

from code_archaeologist.analysis.engine import ExcavationEngine
from code_archaeologist.core.nebius_client import extract_json
from code_archaeologist.parsers import get_parser_for_file

SAMPLE = Path(__file__).resolve().parent.parent / "test_project"


def test_extract_json_handles_fences_and_think_blocks():
    assert extract_json('<think>x</think>```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": [1, 2]} done') == {"a": [1, 2]}


def test_parser_handles_non_ascii_and_decorated_methods():
    src = "# ünï\nclass A:\n    @property\n    def x(self):\n        return 1\n"
    parsed = get_parser_for_file("a.py").parse(src, "a.py")
    assert parsed.comments[0]["text"] == "# ünï"
    assert [m["name"] for m in parsed.classes[0]["methods"]] == ["x"]


def test_excavate_sample_project():
    engine = ExcavationEngine(None)
    report = asyncio.run(engine.excavate(SAMPLE))
    json.dumps(report)  # must be serialisable
    assert report["summary"]["total_files_analyzed"] == 2
    assert any(r["name"] == "God Class: UserService" for r in report["ruins"])
    assert any("legacy_function" in f["name"] for f in report["fossils"])
    assert ("api.py", "service.py") in engine.file_graph.edges
    # IDs are stable between runs so `explain <id>` works
    again = ExcavationEngine(None)
    asyncio.run(again.excavate(SAMPLE))
    assert [r.id for r in engine.ruins] == [r.id for r in again.ruins]
