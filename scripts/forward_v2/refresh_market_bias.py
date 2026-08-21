from __future__ import annotations
import argparse,json,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"src"))
from ullebets_v2.config import V2Config
from ullebets_v2.market_bias.forward import load_forward_candidates
from ullebets_v2.market_bias.service import run_market_bias_refresh
from ullebets_v2.safety import ensure_v2_database
from ullebets_v2.storage.mongo import get_database
def main() -> int:
 p=argparse.ArgumentParser();p.add_argument("--repo-root",type=Path,default=Path.cwd());p.add_argument("--from-date",required=True);p.add_argument("--to-date",required=True);p.add_argument("--as-of",required=True);p.add_argument("--source-workflow",required=True);p.add_argument("--dry-run",action="store_true");a=p.parse_args();c=V2Config.from_env(a.repo_root);ensure_v2_database(c);db=get_database(c);candidates,audit=load_forward_candidates(db,from_date=a.from_date,to_date=a.to_date,run_id="forward");summary=run_market_bias_refresh(source_workflow=a.source_workflow,source_kind="v2_forward",candidates=candidates,as_of=datetime.fromisoformat(a.as_of.replace("Z","+00:00")),profile_date=a.as_of[:10],database=None if a.dry_run else db,dry_run=a.dry_run);summary["forward_audit"]=audit;print(json.dumps(summary,default=str));return 0
if __name__=="__main__":raise SystemExit(main())
