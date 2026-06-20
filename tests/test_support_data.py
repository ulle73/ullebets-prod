from pathlib import Path

from ullebets_v1.sources.support_data import resolve_support_source_files


def test_support_source_files_include_old_repo_jsons():
    files = resolve_support_source_files(Path(r"C:\dev\FRONTEND\ullebets-vecel"))
    assert "leagues-and-teams.json" in {path.name for path in files}
    assert "unibetLeagueUrls.json" in {path.name for path in files}
