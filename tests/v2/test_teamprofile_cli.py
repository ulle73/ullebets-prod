from scripts.forward_v2.build_teamprofiles import _log_summary


def test_teamprofile_cli_does_not_emit_full_profile_documents() -> None:
    summary = {
        "job": "build_teamprofiles",
        "teamprofiles": 2,
        "profile_docs": [{"statistics": {"very": "large"}}],
    }

    assert _log_summary(summary) == {
        "job": "build_teamprofiles",
        "teamprofiles": 2,
    }
