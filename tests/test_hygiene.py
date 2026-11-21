"""Static hygiene: determinism bans, detector independence, truth only from MutationRecords."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
FIN = SRC / "fin_env"


def py_files(root):
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def test_banned_nondeterminism_in_src():
    banned = re.compile(r"datetime\.now|datetime\.utcnow|time\.time\(|uuid4|os\.urandom|\bsecrets\b|"
                        r"(?<![\w.])random\.(random|randint|choice|shuffle|sample|seed)\(|(?<![\w.])hash\(")
    offenders = [str(p.relative_to(SRC)) for p in py_files(SRC)
                 if p.name != "inject.py"  # deliberately broken code for --inject-bug
                 and banned.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


def test_no_float_calls_in_src():
    offenders = [str(p.relative_to(SRC)) for p in py_files(SRC) if re.search(r"(?<![\w.])float\(", p.read_text(encoding="utf-8"))]
    assert offenders == []


def test_no_clock_in_the_generator():
    """time.monotonic is allowed only for the 60 s timeout in env.py and for run/benchmark timing."""
    generator_side = [FIN / "books", FIN / "mutations", FIN / "selfcheck" / "detectors.py",
                      FIN / "selfcheck" / "invariants.py", FIN / "generator.py", FIN / "serialize.py",
                      FIN / "publicio.py", FIN / "canon.py", FIN / "rng.py", FIN / "money.py", FIN / "timeutil.py"]
    files = []
    for g in generator_side:
        files += py_files(g) if g.is_dir() else [g]
    assert [f.name for f in files if "monotonic" in f.read_text(encoding="utf-8")] == []


def test_detectors_do_not_import_mutations():
    import ast
    tree = ast.parse((FIN / "selfcheck" / "detectors.py").read_text(encoding="utf-8"))
    mods = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    mods += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in mods if "mutations" in m]


def test_truth_files_are_written_only_by_generator():
    writers = [p.name for p in py_files(SRC) if re.search(r"write_json\([^)]*truth", p.read_text(encoding="utf-8"))]
    assert sorted(writers) == ["generator.py", "transforms.py"]  # transforms only re-maps ids of an existing truth


def test_env_does_not_import_generator_at_module_level_or_truth():
    text = (FIN / "env.py").read_text(encoding="utf-8")
    assert not re.search(r"^from \.generator|^import .*generator|truth\.json", text, re.M)


def test_viz_not_imported_by_environment():
    import subprocess
    import sys
    code = "import fin_env.env, sys; assert 'viz' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True, env={"PYTHONPATH": str(SRC), "SYSTEMROOT": "C:\\Windows"})
