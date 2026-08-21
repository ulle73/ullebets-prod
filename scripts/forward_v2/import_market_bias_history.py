from __future__ import annotations
import argparse, json, sys
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
from ullebets_v2.config import V2Config
from ullebets_v2.market_bias.bootstrap import build_bootstrap_candidates
from ullebets_v2.market_bias.service import run_market_bias_refresh
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--repo-root",type=Path,default=Path.cwd()); p.add_argument("--as-of",required=True); p.add_argument("--report-path",type=Path,required=True); p.add_argument("--dry-run",action="store_true"); p.add_argument("--write",action="store_true"); a=p.parse_args()
    if a.write and a.dry_run: raise RuntimeError("--write and --dry-run are mutually exclusive")
    config=V2Config.from_env(a.repo_root)
    if a.write: ensure_v2_database(config)
    read_database=get_database(config)
    support={"teams": list(read_database["support_teams"].find({})), "leagues": list(read_database["support_leagues"].find({}))}
    candidates,audit=build_bootstrap_candidates(a.repo_root / "data" / "derived" / "offline_v1" / "normalized", support_docs=support, as_of=datetime.fromisoformat(a.as_of.replace("Z","+00:00")), run_id="bootstrap")
    summary=run_market_bias_refresh(source_workflow="import_market_bias_history.py",source_kind="offline_v1_bootstrap",candidates=candidates,as_of=datetime.fromisoformat(a.as_of.replace("Z","+00:00")),profile_date=a.as_of[:10],database=read_database if a.write else None,dry_run=not a.write); summary["bootstrap_audit"]=audit; a.report_path.parent.mkdir(parents=True,exist_ok=True); a.report_path.write_text(json.dumps(summary,default=str,indent=2)); print(json.dumps(summary,default=str)); return 0
if __name__ == "__main__": raise SystemExit(main())
