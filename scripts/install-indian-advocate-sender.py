#!/usr/bin/env python3
"""Install a PAUSED workbook campaign on the existing VPS. Never sends mail."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
import zipfile


REMOTE_INSTALL = r'''
import hashlib,io,json,os,shlex,shutil,subprocess,sys,tempfile,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
os.umask(0o077)
base=Path.home()/"lhc"
data=base/"indian_advocates"
script=base/"indian_advocate_emailer.py"
monitor=Path.home()/".local/lib/lhc-mail-health/check-gmail-health.py"
python=base/"venv/bin/python3"
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_atomic(path,content):
    if path.is_symlink():raise ValueError("unsafe_install_path")
    path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=".install-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:f.write(content);f.flush();os.fsync(f.fileno())
        os.chmod(name,0o600);os.replace(name,str(path))
    finally:
        if os.path.exists(name):os.unlink(name)
def invoke(*args):
    r=subprocess.run([str(python),str(script),"--root",str(data)]+list(args),capture_output=True,universal_newlines=True,timeout=240)
    result=json.loads(r.stdout)
    if r.returncode:raise ValueError(result.get("error","campaign_setup_failed"))
    return result
try:
    if not base.is_dir() or not python.is_file() or not monitor.is_file():raise ValueError("existing_runtime_missing")
    if data.is_symlink():raise ValueError("unsafe_data_path")
    data.mkdir(mode=0o700,exist_ok=True);os.chmod(str(data),0o700)
    config=data/"config.json"
    if config.exists() and json.loads(config.read_text()).get("enabled") is not False:
        raise ValueError("pause_existing_directory_campaign_before_install")
    if getattr(time.localtime(),"tm_gmtoff",None)!=19800:raise ValueError("cron_timezone_not_IST")
    payload=zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read()))
    if set(payload.namelist())!={"sender.py","health.py","workbook.xlsx","manifest.json"}:raise ValueError("unexpected_install_bundle")
    manifest=json.loads(payload.read("manifest.json"))
    for name in ["sender.py","health.py","workbook.xlsx"]:
        if hashlib.sha256(payload.read(name)).hexdigest()!=manifest[name]:raise ValueError("install_bundle_checksum_mismatch")
    for name in ["sender.py","health.py"]:compile(payload.read(name).decode(),name,"exec")
    protected=[base/n for n in ["allahabad_emailer.py","calcutta_emailer.py","lhc_emailer.py",
               "Allahabad_HC_Advocates.xlsx","Calcutta_HC_Advocates.xlsx","LHC_Advocate_CRM.xlsx",
               "allahabad_sent_state.json","sent_state.json","blacklist.txt","token.json","credentials.json"]]
    before={p.name:digest(p) for p in protected}
    cron_result=subprocess.run(["crontab","-l"],capture_output=True,universal_newlines=True,check=True)
    original_cron=cron_result.stdout
    backup=data/"backups"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup.mkdir(parents=True,mode=0o700)
    for p in [script,monitor,data/"indian-advocate-directories.xlsx"]:
        if p.exists():shutil.copy2(str(p),str(backup/p.name))
    (backup/"crontab.txt").write_text(original_cron)
    write_atomic(script,payload.read("sender.py"))
    workbook=data/"indian-advocate-directories.xlsx"
    write_atomic(workbook,payload.read("workbook.xlsx"))
    imported=invoke("import","--workbook",str(workbook))
    preview=invoke("preview")
    status=invoke("status")
    if status["enabled"] is not False:raise ValueError("installation_must_remain_paused")
    exported=invoke("export")
    # A scheduled invocation cannot send while the persistent enabled flag is false.
    marker="# lhc-indian-advocates"
    job="10 9-17 * * 1-5 {} {} --root {} run --send --cron >> {} 2>&1 {}".format(
        shlex.quote(str(python)),shlex.quote(str(script)),shlex.quote(str(data)),shlex.quote(str(data/"cron.log")),marker)
    unrelated=[line for line in original_cron.splitlines() if marker not in line]
    desired="\n".join(unrelated+[job])+"\n"
    current=subprocess.check_output(["crontab","-l"],universal_newlines=True)
    if current!=original_cron:raise ValueError("crontab_changed_during_setup")
    subprocess.run(["crontab","-"],input=desired,universal_newlines=True,check=True,capture_output=True)
    write_atomic(monitor,payload.read("health.py"))
    # Read the new status parser directly. This does not run authentication checks.
    import runpy
    health=runpy.run_path(str(monitor))
    monitor_status=health["directory_campaign_snapshot"](data,datetime.now())
    after={p.name:digest(p) for p in protected}
    print(json.dumps({"installed":True,"enabled":False,"data_directory":str(data),"script":str(script),
          "import":imported,"dry_run":preview,"status":status,"export":exported,
          "schedule_installed":True,"schedule":"10 9-17 * * 1-5 IST",
          "existing_cron_entries_preserved":unrelated==[line for line in desired.splitlines() if marker not in line],
          "legacy_files_unchanged_during_setup":before==after,
          "monitor_campaign_status":monitor_status["status"],"source_sha256":digest(workbook),
          "backup_directory":str(backup)}))
except Exception:
    print(json.dumps({"error":"paused_campaign_install_failed; inspect setup without running a batch"}))
    sys.exit(3)
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workbook",type=Path,required=True)
    args=p.parse_args()
    root=Path(__file__).resolve().parent
    parts={"sender.py":(root/"indian-advocate-emailer.py").read_bytes(),
           "health.py":(root/"check-gmail-health.py").read_bytes(),"workbook.xlsx":args.workbook.read_bytes()}
    for name in ["sender.py","health.py"]:compile(parts[name],name,"exec")
    parts["manifest.json"]=json.dumps({name:hashlib.sha256(data).hexdigest() for name,data in parts.items()}).encode()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)
    try:
        result=subprocess.run(["ssh","-o","BatchMode=yes","-o","ConnectTimeout=10","-o","LogLevel=ERROR",
                               "cedrf","python3 -c "+shlex.quote(REMOTE_INSTALL)],input=buffer.getvalue(),
                              capture_output=True,timeout=480)
        data=json.loads(result.stdout)
        print(json.dumps(data))
        return result.returncode
    except (OSError,ValueError,subprocess.SubprocessError):
        print(json.dumps({"error":"VPS setup unavailable; no credentials displayed"}))
        return 3


if __name__=="__main__":sys.exit(main())
